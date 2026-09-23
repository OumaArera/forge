"""Computing standing, awarding levels and badges, building leaderboards."""

from __future__ import annotations

import logging
from datetime import date

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from forge.audit.models import AuditEvent
from forge.audit.services import record as audit
from forge.common.exceptions import DomainRuleViolation

from .models import (
    Badge,
    BadgeAward,
    Certificate,
    LeaderboardSnapshot,
    Level,
    LevelAward,
    Standing,
)

logger = logging.getLogger("forge.recognition")


@transaction.atomic
def reassess_standing(user) -> Standing:
    """
    Rebuild one member's standing from the ledger.

    Everything here is derived. Nothing is incremented in place, because an
    incremented counter drifts and a recomputed one cannot.
    """
    from forge.contributions.models import Dimension, LedgerEntry
    from forge.projects.models import Membership, Project

    entries = LedgerEntry.objects.filter(contributor=user).select_related("project")

    totals = entries.aggregate(points=Sum("points"), count=Count("id"))
    by_dimension = {
        row["dimension"]: row["points"]
        for row in entries.values("dimension").annotate(points=Sum("points"))
    }

    by_area: dict[str, int] = {}
    for entry in entries.prefetch_related("project__discipline_areas"):
        for area in entry.project.discipline_areas.all():
            by_area[area.slug] = by_area.get(area.slug, 0) + entry.points

    completed = Membership.objects.filter(
        user=user, project__status=Project.Status.COMPLETED
    ).values("project").distinct().count()
    led = Project.objects.filter(lead=user, status=Project.Status.COMPLETED).count()
    mentored = entries.filter(dimension=Dimension.MENTORSHIP).count()

    standing, _ = Standing.objects.get_or_create(user=user)
    standing.total_points = totals["points"] or 0
    standing.confirmed_contributions = totals["count"] or 0
    standing.completed_projects = completed
    standing.projects_led = led
    standing.people_mentored = mentored
    standing.points_by_dimension = by_dimension
    standing.points_by_area = by_area
    first = entries.order_by("recorded_at").first()
    last = entries.order_by("-recorded_at").first()
    standing.first_contribution_at = first.recorded_at if first else None
    standing.last_contribution_at = last.recorded_at if last else None
    standing.recomputed_at = timezone.now()

    standing.level = _level_for(standing)
    standing.save()

    _record_level_award(user, standing)
    award_automatic_badges(user, standing)
    return standing


def _level_for(standing: Standing) -> Level | None:
    """The highest level whose every condition the member meets."""
    from forge.contributions.models import Dimension

    taught = (standing.points_by_dimension or {}).get(Dimension.MENTORSHIP, 0) > 0
    best = None
    for level in Level.objects.order_by("rank"):
        if standing.total_points < level.min_points:
            continue
        if standing.confirmed_contributions < level.min_confirmed_contributions:
            continue
        if standing.completed_projects < level.min_completed_projects:
            continue
        if level.requires_teaching and not taught:
            continue
        best = level
    return best


def _record_level_award(user, standing: Standing) -> None:
    if standing.level is None:
        return
    _, created = LevelAward.objects.get_or_create(
        user=user, level=standing.level,
        defaults={"points_at_award": standing.total_points},
    )
    if created:
        from forge.notifications.services import notify

        notify(user, verb="recognition.level", target=standing.level,
               summary=f"You have reached {standing.level.name}.")


# Badges awarded automatically. Each rule is a small, readable predicate --
# if a maintainer cannot tell at a glance how a badge is earned, neither can
# the students trying to earn it.
def award_automatic_badges(user, standing: Standing) -> list[BadgeAward]:
    from forge.contributions.models import Dimension, LedgerEntry
    from forge.projects.models import Membership, Project

    awarded = []

    def give(slug: str, reason: str, project=None):
        badge = Badge.objects.filter(slug=slug, is_active=True).first()
        if badge is None:
            return
        award, created = BadgeAward.objects.get_or_create(
            user=user, badge=badge, project=project, defaults={"reason": reason}
        )
        if created:
            awarded.append(award)
            from forge.notifications.services import notify

            notify(user, verb="recognition.badge", target=badge,
                   summary=f"You earned the {badge.name} badge.")

    if standing.completed_projects >= 1:
        give("first-delivery", "Delivered a first project.")
    if standing.projects_led >= 1:
        give("led-to-delivery", "Led a project through to delivery.")
    if (standing.points_by_dimension or {}).get(Dimension.MENTORSHIP, 0) >= 20:
        give("teacher", "Sustained, confirmed mentorship of other members.")
    if (standing.points_by_dimension or {}).get(Dimension.DOCUMENTATION, 0) >= 20:
        give("writes-it-down", "Sustained, confirmed documentation work.")

    # Worked on a team drawn from more than one school.
    cross = (
        Membership.objects.filter(user=user, left_at__isnull=True)
        .select_related("project").values_list("project_id", flat=True)
    )
    for project in Project.objects.filter(id__in=list(cross)):
        if project.school_spread > 1 and LedgerEntry.objects.filter(
            contributor=user, project=project
        ).exists():
            give("crossed-the-aisle",
                 "Contributed to a team drawn from more than one school.", project)
            break

    return awarded


@transaction.atomic
def issue_certificate(*, user, kind: str, project=None, issued_by=None) -> Certificate:
    """
    Issue a verifiable certificate.

    The statement wording is generated here and is the platform's careful
    line: it records what someone did, attributes nothing academic, and says
    in terms that FORGE is not a qualification.
    """
    from forge.contributions.models import LedgerEntry

    if kind in {Certificate.Kind.PARTICIPATION, Certificate.Kind.COMPLETION}:
        if project is None:
            raise DomainRuleViolation("A project certificate needs a project.")
        entries = LedgerEntry.objects.filter(contributor=user, project=project)
        if not entries.exists():
            raise DomainRuleViolation(
                "There are no confirmed contributions from this member on this "
                "project, so there is nothing to certify.",
                code="no_evidence",
            )
        count = entries.count()
        body = (
            f"This is to record that {user.display_name} took part in the FORGE "
            f"project “{project.title}” and has {count} contribution"
            f"{'s' if count != 1 else ''} to that project confirmed on the FORGE "
            f"record by {_confirming_parties(entries)}."
        )
    elif kind == Certificate.Kind.MENTORSHIP:
        body = (f"This is to record that {user.display_name} served as a mentor on "
                f"FORGE and has confirmed mentorship contributions on the FORGE record.")
    else:
        body = (f"This is to record that {user.display_name} made confirmed "
                f"contributions to the FORGE community.")

    disclaimer = (
        " FORGE is a voluntary student initiative of the Open University of Kenya. "
        "This record carries no academic credit and is not a qualification of the "
        "University."
    )

    head = LedgerEntry.objects.order_by("-sequence").first()
    certificate = Certificate.objects.create(
        user=user, kind=kind, project=project,
        recipient_name=user.display_name,
        statement=body + disclaimer,
        verification_code=_unique_code(),
        ledger_head=head.entry_hash if head else "",
    )
    audit(AuditEvent.Action.CERTIFICATE_ISSUED, actor=issued_by, target=certificate,
          metadata={"kind": kind, "code": certificate.verification_code})
    return certificate


CAPACITY_WORDS = {
    "lead": "the project lead",
    "mentor": "the assigned mentor",
    "community_lead": "a community lead",
    "peer": "a peer reviewer",
}


def _confirming_parties(entries) -> str:
    """
    Describe who actually confirmed the work, rather than assuming.

    Usually the project lead and the assigned mentor -- but a lead cannot
    attest to their own contributions, and a community lead signs in place of
    theirs. A certificate that named the wrong parties would be a small lie on
    a document whose entire value is that it can be checked.
    """
    capacities: list[str] = []
    for entry in entries:
        for attestation in (entry.payload or {}).get("attestations", []):
            if attestation.get("decision") != "confirm":
                continue
            word = CAPACITY_WORDS.get(attestation.get("capacity", ""))
            if word and word not in capacities:
                capacities.append(word)

    if not capacities:
        return "two independent parties"
    if len(capacities) == 1:
        return capacities[0]
    return f"{', '.join(capacities[:-1])} and {capacities[-1]}"


def _unique_code() -> str:
    for _ in range(10):
        code = Certificate.new_code()
        if not Certificate.objects.filter(verification_code=code).exists():
            return code
    raise RuntimeError("Could not allocate a certificate code.")  # pragma: no cover


@transaction.atomic
def revoke_certificate(certificate: Certificate, *, actor, reason: str) -> Certificate:
    if not reason.strip():
        raise DomainRuleViolation("Give a reason for revoking a certificate.")
    certificate.revoked_at = timezone.now()
    certificate.revoked_reason = reason[:300]
    certificate.save(update_fields=["revoked_at", "revoked_reason"])
    audit(AuditEvent.Action.CERTIFICATE_REVOKED, actor=actor, target=certificate,
          metadata={"reason": reason[:200]})
    return certificate


def build_leaderboard(*, scope: str, period_start: date, period_end: date,
                      discipline_area=None, period: str = LeaderboardSnapshot.Period.TRIMESTER
                      ) -> LeaderboardSnapshot:
    """
    Compute and freeze one board.

    Note what is *not* here: no global ranking of every member of the
    platform against every other. Boards are scoped, because the purpose is
    to make good work visible within a community, not to produce a single
    number that says who the best student is.
    """
    from forge.contributions.models import Dimension, LedgerEntry

    entries = LedgerEntry.objects.filter(
        recorded_at__date__gte=period_start, recorded_at__date__lte=period_end,
        contributor__isnull=False,
    )
    if scope == LeaderboardSnapshot.Scope.DISCIPLINE and discipline_area:
        entries = entries.filter(project__discipline_areas=discipline_area)
    elif scope == LeaderboardSnapshot.Scope.COMMUNITY:
        entries = entries.filter(dimension=Dimension.COMMUNITY)
    elif scope == LeaderboardSnapshot.Scope.MENTORSHIP:
        entries = entries.filter(dimension=Dimension.MENTORSHIP)

    rows = (
        entries.values(
            "contributor_id", "contributor__full_name", "contributor__preferred_name",
            "contributor__public_slug", "contributor__portfolio_is_public",
        )
        .annotate(points=Sum("points"), contributions=Count("id"))
        .order_by("-points", "contributor__full_name")[: settings.FORGE_POLICY["LEADERBOARD_SIZE"]]
    )

    payload = []
    for index, row in enumerate(rows, start=1):
        public = row["contributor__portfolio_is_public"]
        payload.append({
            "rank": index,
            "user_id": str(row["contributor_id"]),
            "display_name": row["contributor__preferred_name"] or row["contributor__full_name"],
            # A member who has made their portfolio private is ranked but not
            # linked. Appearing on a board is not consent to be looked up.
            "public_slug": row["contributor__public_slug"] if public else None,
            "points": row["points"] or 0,
            "contributions": row["contributions"],
        })

    snapshot, _ = LeaderboardSnapshot.objects.update_or_create(
        scope=scope, discipline_area=discipline_area, period=period,
        period_start=period_start,
        defaults={"period_end": period_end, "rows": payload,
                  "computed_at": timezone.now()},
    )
    return snapshot
