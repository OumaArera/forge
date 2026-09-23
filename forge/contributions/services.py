"""
Submitting, attesting and settling contributions.

The two-party rule from section 9 of the concept proposal lives in `attest`.
It is the single most important control in the platform, so it is written
once, in one place, and tested directly.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from forge.accounts.models import RoleGrant
from forge.accounts.services import check_may_act
from forge.audit.models import AuditEvent
from forge.audit.services import record as audit
from forge.common.exceptions import DomainRuleViolation, NotEligible
from forge.projects.models import Project

from .models import Attestation, Contribution, Dimension, LedgerEntry

logger = logging.getLogger("forge.contributions")


# Recognition weight by dimension.
#
# These numbers are the most consequential in the codebase and the least
# defensible from first principles, so they are stated plainly rather than
# buried. The intent behind the spread is narrow deliberately: the gap between
# the best-rewarded and worst-rewarded dimension is under two to one, because
# a wider spread would tell students which kind of contribution the platform
# really values, and the platform's position is that it values all of them.
# The Advisory Committee should expect to tune these after the first trimester
# with real data in front of them.
DIMENSION_POINTS = {
    Dimension.DELIVERY: 10,
    Dimension.LEADERSHIP: 10,
    Dimension.RESEARCH: 9,
    Dimension.DESIGN: 8,
    Dimension.DOCUMENTATION: 8,
    Dimension.MENTORSHIP: 8,
    Dimension.REVIEW: 7,
    Dimension.COMMUNITY: 6,
}


def compute_points(contribution: Contribution) -> int:
    """
    Recognition weight for a settled contribution.

    Effort hours are capped in their influence on purpose. Hours are
    self-reported, and any scheme that pays out linearly in a self-reported
    number is a scheme that rewards whoever is least scrupulous about it.
    """
    base = DIMENSION_POINTS.get(contribution.dimension, 5)
    hours = float(contribution.effort_hours or 0)
    effort_bonus = min(int(hours // 5), 6)
    return base + effort_bonus


@transaction.atomic
def submit(contribution: Contribution, *, actor) -> Contribution:
    check_may_act(actor)
    if contribution.contributor_id != actor.id and not actor.is_superuser:
        raise NotEligible("You may only submit your own contributions.")
    if contribution.status not in {Contribution.Status.DRAFT, Contribution.Status.DISPUTED}:
        raise DomainRuleViolation("That contribution has already been submitted.")

    project = contribution.project
    is_member = project.is_member(actor) or project.lead_id == actor.id
    if not is_member:
        raise NotEligible("Log contributions against a project you are a member of.")

    contribution.status = Contribution.Status.SUBMITTED
    contribution.submitted_at = timezone.now()
    contribution.full_clean(exclude=["skills_used"])
    contribution.save(update_fields=["status", "submitted_at", "updated_at"])
    project.touch_activity()

    audit(AuditEvent.Action.CONTRIBUTION_SUBMITTED, actor=actor, target=contribution,
          metadata={"project": str(project.pk), "dimension": contribution.dimension,
                    "late": contribution.is_late})

    from forge.notifications.services import notify

    for attestor, _capacity in _expected_attestors(project, contribution):
        notify(attestor, verb="contribution.awaiting_attestation", target=contribution,
               summary=(f"{contribution.contributor.display_name} logged a contribution "
                        f"on {project.title} that needs your confirmation."))
    return contribution


def settling_capacities(project: Project, contribution: Contribution) -> set[str]:
    """
    Which two signatures settle this particular claim.

    Normally the project lead and the assigned mentor. But a lead cannot
    attest to their own work, and if the lead capacity simply stayed on the
    required list, a lead's own contributions could never reach two signatures
    at all -- they would sit unsettled forever. The person doing the most work
    on a project would accumulate nothing, which is close to the opposite of
    what the platform is for.

    So when the claimant is the lead, a community lead's signature stands in
    for theirs. The principle is unchanged: two independent people, neither of
    them the claimant, one of whom is the assigned mentor.
    """
    if project.lead_id == contribution.contributor_id:
        return {Attestation.Capacity.MENTOR, Attestation.Capacity.COMMUNITY_LEAD}
    return {Attestation.Capacity.LEAD, Attestation.Capacity.MENTOR}


def _expected_attestors(project: Project, contribution: Contribution):
    """Who is being asked to confirm. Never the claimant."""
    out = []
    required = settling_capacities(project, contribution)

    if (Attestation.Capacity.LEAD in required and project.lead_id
            and project.lead_id != contribution.contributor_id):
        out.append((project.lead, Attestation.Capacity.LEAD))

    if project.mentor_id and project.mentor_id != contribution.contributor_id:
        out.append((project.mentor, Attestation.Capacity.MENTOR))

    if Attestation.Capacity.COMMUNITY_LEAD in required:
        # The lead is claiming, so somebody outside the project has to sign.
        # Prefer a community lead for a discipline the project is tagged with.
        from forge.accounts.models import RoleGrant, User

        leads = (
            User.objects.filter(
                role_grants__role=RoleGrant.Role.COMMUNITY_LEAD,
                role_grants__revoked_at__isnull=True,
                status=User.Status.ACTIVE,
            )
            .exclude(pk=contribution.contributor_id)
            .distinct()
        )
        scoped = leads.filter(
            role_grants__discipline_area__in=project.discipline_areas.all()
        ).first()
        chosen = scoped or leads.first()
        if chosen is not None:
            out.append((chosen, Attestation.Capacity.COMMUNITY_LEAD))
    return out


def capacity_for(user, project: Project, contribution: Contribution) -> str | None:
    """
    In what capacity may this person attest to this claim?

    Returns None if they may not. The order matters: someone who is both the
    lead and a qualified mentor counts once, as the lead, because two
    signatures from the same person are one signature.
    """
    required = settling_capacities(project, contribution)

    if project.lead_id == user.id:
        return Attestation.Capacity.LEAD
    if project.mentor_id == user.id:
        return Attestation.Capacity.MENTOR

    # When the lead is the one claiming, a community lead's signature is one
    # of the two that settle it, so it must not be demoted to a peer opinion.
    if (Attestation.Capacity.COMMUNITY_LEAD in required
            and user.has_role(RoleGrant.Role.COMMUNITY_LEAD)):
        return Attestation.Capacity.COMMUNITY_LEAD

    if user.can_attest_as_mentor:
        return Attestation.Capacity.MENTOR
    if user.can_moderate:
        return Attestation.Capacity.COMMUNITY_LEAD
    if project.is_member(user):
        return Attestation.Capacity.PEER
    return None


@transaction.atomic
def attest(contribution: Contribution, *, attestor, confirm: bool, note: str = "") -> Attestation:
    """
    Record one party's judgement on a claim, and settle it if that completes
    the set.

    Three rules are enforced here, and all three exist because of how this
    kind of system is gamed:

      1. Nobody attests to their own work. Without this, the whole scheme is
         a self-service portfolio generator.
      2. One signature per capacity. Someone who is both lead and mentor on
         the same project cannot supply both required confirmations.
      3. A peer's confirmation does not count towards the required two. Peers
         may comment; the lead and the mentor are what settles a record.
    """
    check_may_act(attestor)
    project = contribution.project

    if settings.FORGE_POLICY["FORBID_SELF_ATTESTATION"]:
        if contribution.contributor_id == attestor.id:
            raise NotEligible(
                "You cannot confirm your own contribution. Two other people must.",
                code="self_attestation",
            )

    capacity = capacity_for(attestor, project, contribution)
    if capacity is None:
        raise NotEligible("You are not in a position to confirm work on this project.")

    if contribution.status not in {Contribution.Status.SUBMITTED,
                                   Contribution.Status.DISPUTED}:
        raise DomainRuleViolation("That contribution is not awaiting confirmation.")

    if contribution.attestations.filter(capacity=capacity).exists():
        raise DomainRuleViolation(
            f"A confirmation has already been recorded in the capacity of "
            f"{capacity}. One signature per capacity.",
            code="capacity_taken",
        )
    if not confirm and not note.strip():
        raise DomainRuleViolation("Say why you are disputing this claim.",
                                  code="reason_required")

    attestation = Attestation.objects.create(
        contribution=contribution,
        attestor=attestor,
        attestor_name=attestor.display_name[:160],
        capacity=capacity,
        decision=(Attestation.Decision.CONFIRM if confirm
                  else Attestation.Decision.DISPUTE),
        note=note,
    )
    audit(
        AuditEvent.Action.CONTRIBUTION_ATTESTED if confirm
        else AuditEvent.Action.CONTRIBUTION_DISPUTED,
        actor=attestor, target=contribution,
        metadata={"capacity": capacity, "project": str(project.pk)},
    )

    from forge.notifications.services import notify

    if not confirm:
        contribution.status = Contribution.Status.DISPUTED
        contribution.save(update_fields=["status", "updated_at"])
        notify(contribution.contributor, verb="contribution.disputed", target=contribution,
               summary=f"{attestor.display_name} raised a question about your "
                       f"contribution on {project.title}.")
        return attestation

    required = settling_capacities(project, contribution)
    confirmed_caps = set(
        contribution.attestations.filter(decision=Attestation.Decision.CONFIRM)
        .values_list("capacity", flat=True)
    ) & required

    if len(confirmed_caps) >= settings.FORGE_POLICY["REQUIRED_ATTESTATIONS"]:
        settle(contribution)
        notify(contribution.contributor, verb="contribution.confirmed", target=contribution,
               summary=f"Your contribution on {project.title} is confirmed and is "
                       f"now part of your portfolio.")
    return attestation


@transaction.atomic
def settle(contribution: Contribution) -> LedgerEntry:
    """
    Write a confirmed contribution into the ledger.

    Takes a database-level lock on the ledger's tail while computing the next
    sequence and hash. Two contributions settling at the same instant must not
    both read the same previous hash, or the chain forks and verification
    fails for everything after it.
    """
    if hasattr(contribution, "ledger_entry"):
        return contribution.ledger_entry

    # PostgreSQL advisory lock: serialises appends without locking the table
    # against readers. The constant is arbitrary but must not collide.
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [0x464F524745])

    tail = LedgerEntry.objects.order_by("-sequence").first()
    sequence = (tail.sequence + 1) if tail else 1
    previous_hash = tail.entry_hash if tail else LedgerEntry.GENESIS_HASH

    contribution.status = Contribution.Status.CONFIRMED
    contribution.settled_at = timezone.now()
    contribution.save(update_fields=["status", "settled_at", "updated_at"])

    payload = contribution.canonical_payload()
    points = compute_points(contribution)
    recorded_at = timezone.now()
    entry_hash = LedgerEntry.compute_hash(
        sequence=sequence, previous_hash=previous_hash, payload=payload,
        recorded_at=recorded_at, points=points,
    )

    entry = LedgerEntry.objects.create(
        sequence=sequence,
        contribution=contribution,
        contributor=contribution.contributor,
        project=contribution.project,
        dimension=contribution.dimension,
        points=points,
        payload=payload,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
        recorded_at=recorded_at,
    )

    _credit_skills(contribution)
    audit(AuditEvent.Action.LEDGER_APPENDED, actor=None, target=entry,
          metadata={"sequence": sequence, "points": points,
                    "contributor": str(contribution.contributor_id)})

    from forge.recognition.services import reassess_standing
    reassess_standing(contribution.contributor)
    return entry


def _credit_skills(contribution: Contribution) -> None:
    """
    Turn a confirmed contribution into evidence behind a declared skill.

    This is what makes `UserSkill.evidence_count` mean something. A member who
    claims Python and has never shipped anything in it shows a zero, and the
    portfolio says so rather than taking their word for it.
    """
    from forge.accounts.models import UserSkill

    skill_ids = list(contribution.skills_used.values_list("id", flat=True))
    if not skill_ids:
        return
    UserSkill.objects.filter(
        user=contribution.contributor, skill_id__in=skill_ids
    ).update(evidence_count=F("evidence_count") + 1)

    # A skill used but not yet declared gets declared, with its evidence.
    declared = set(
        UserSkill.objects.filter(user=contribution.contributor, skill_id__in=skill_ids)
        .values_list("skill_id", flat=True)
    )
    for skill_id in set(skill_ids) - declared:
        UserSkill.objects.create(
            user=contribution.contributor, skill_id=skill_id,
            self_rating=UserSkill.Proficiency.WORKING, evidence_count=1,
        )


@transaction.atomic
def withdraw(contribution: Contribution, *, actor) -> Contribution:
    if contribution.contributor_id != actor.id and not actor.is_superuser:
        raise NotEligible("You may only withdraw your own contributions.")
    if contribution.status == Contribution.Status.CONFIRMED:
        raise DomainRuleViolation(
            "A confirmed contribution is part of the permanent record and cannot "
            "be withdrawn. If it is wrong, ask a moderator to record a correction.",
            code="already_settled",
        )
    contribution.status = Contribution.Status.WITHDRAWN
    contribution.save(update_fields=["status", "updated_at"])
    return contribution


def verify_chain(*, start: int = 1, limit: int | None = None) -> dict:
    """
    Walk the ledger and check every link.

    Returns a report rather than raising, because the caller -- a management
    command, a scheduled check, or the Advisory Committee -- wants to see the
    whole picture, not the first problem.
    """
    entries = LedgerEntry.objects.filter(sequence__gte=start).order_by("sequence")
    if limit:
        entries = entries[:limit]

    problems: list[dict] = []
    expected_previous = None
    expected_sequence = None
    checked = 0

    for entry in entries.iterator(chunk_size=500):
        checked += 1
        if expected_sequence is not None and entry.sequence != expected_sequence:
            problems.append({"sequence": entry.sequence, "issue": "sequence_gap",
                             "expected": expected_sequence})
        if expected_previous is not None and entry.previous_hash != expected_previous:
            problems.append({"sequence": entry.sequence, "issue": "broken_link"})
        if entry.sequence == 1 and entry.previous_hash != LedgerEntry.GENESIS_HASH:
            problems.append({"sequence": 1, "issue": "bad_genesis"})
        if not entry.is_intact:
            problems.append({"sequence": entry.sequence, "issue": "hash_mismatch"})
        expected_previous = entry.entry_hash
        expected_sequence = entry.sequence + 1

    return {
        "checked": checked,
        "intact": not problems,
        "problems": problems,
        "head": LedgerEntry.objects.aggregate(m=Max("sequence"))["m"] or 0,
        "verified_at": timezone.now().isoformat(),
    }
