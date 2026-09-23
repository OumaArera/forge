"""
Scheduled work on projects.

Two jobs here address failure modes the concept proposal names but that
nothing in the request/response path would ever catch: projects that quietly
die, and students who quietly disappear.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Project

logger = logging.getLogger("forge.projects")


@shared_task
def flag_stale_projects() -> dict:
    """
    Nudge, then archive.

    A showcase full of projects that stopped six months ago is worse than an
    empty one, because it teaches a visitor that nothing here gets finished.
    The lead and mentor get a warning first; only silence after that archives
    the project, and archiving is reversible.
    """
    from forge.notifications.services import notify

    policy = settings.FORGE_POLICY
    now = timezone.now()
    warn_cutoff = now - timedelta(days=policy["PROJECT_STALE_AFTER_DAYS"])
    abandon_cutoff = now - timedelta(days=policy["PROJECT_ABANDON_AFTER_DAYS"])

    warned = abandoned = 0

    for project in Project.objects.active().filter(
        last_activity_at__lt=abandon_cutoff
    ).select_related("lead", "mentor"):
        from .services import transition

        try:
            transition(project, Project.Status.ABANDONED, actor=None,
                       note="no activity for "
                            f"{policy['PROJECT_ABANDON_AFTER_DAYS']} days")
            abandoned += 1
        except Exception:
            logger.exception("Could not archive stale project %s", project.pk)

    for project in Project.objects.active().filter(
        last_activity_at__lt=warn_cutoff, last_activity_at__gte=abandon_cutoff
    ).select_related("lead", "mentor"):
        days = (now - project.last_activity_at).days
        for person in filter(None, [project.lead, project.mentor]):
            notify(person, verb="project.stale", target=project,
                   summary=(f"'{project.title}' has had no activity for {days} days. "
                            f"Post a progress update, or hand it over, or close it -- "
                            f"any of the three is better than silence."))
        warned += 1

    return {"warned": warned, "abandoned": abandoned}


@shared_task
def nudge_quiet_members() -> dict:
    """
    Reach out to members who have gone quiet.

    Section 3.2 of the proposal makes the case that isolation is a retention
    risk as much as a skills one: a student who studies alone for four years
    and never collaborates on anything consequential is a student at higher
    risk of disengaging altogether.

    This is deliberately gentle and deliberately rare. It fires once, it
    suggests roles that actually fit them, and it never mentions how long they
    have been away. A guilt-inducing reminder from a voluntary platform gets
    the platform muted.
    """
    from forge.accounts.models import User
    from forge.notifications.services import notify

    from .models import Membership
    from .services import suggest_roles_for

    cutoff = timezone.now() - timedelta(
        days=settings.FORGE_POLICY["LEARNER_QUIET_AFTER_DAYS"])
    recently_nudged = timezone.now() - timedelta(days=60)

    # Members currently on a team. Computed as an explicit set of ids rather
    # than `.exclude(memberships__left_at__isnull=True)`, because that form
    # excludes members with NO memberships at all: the LEFT JOIN gives them a
    # null left_at, which satisfies the condition being excluded. That would
    # have skipped exactly the people this task exists to reach.
    on_a_team = set(
        Membership.objects.filter(left_at__isnull=True).values_list("user_id", flat=True)
    )

    candidates = (
        User.objects.filter(status=User.Status.ACTIVE, is_active=True)
        .filter(last_seen_at__lt=cutoff)
        .exclude(id__in=on_a_team)
        .exclude(notifications__verb="platform.announcement",
                 notifications__created_at__gte=recently_nudged)
        .distinct()[:500]
    )

    nudged = 0
    for user in candidates:
        roles = list(suggest_roles_for(user, limit=3))
        if not roles:
            continue
        titles = ", ".join(f"{r.title} on {r.project.title}" for r in roles)
        notify(user, verb="platform.announcement",
               summary=f"Some open roles that look like a fit for you: {titles}.")
        nudged += 1

    return {"nudged": nudged}


@shared_task
def expire_stale_applications() -> int:
    """
    Decline applications a lead has left sitting.

    An application that is never answered is worse for the applicant than one
    that is declined, because they cannot apply elsewhere for the role and do
    not know where they stand.
    """
    from .models import Application

    cutoff = timezone.now() - timedelta(days=21)
    return Application.objects.filter(
        status=Application.Status.PENDING, created_at__lt=cutoff
    ).update(status=Application.Status.WITHDRAWN,
             decision_note="Lapsed: no decision was recorded within 21 days.")
