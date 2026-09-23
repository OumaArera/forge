"""
Project lifecycle operations.

Every rule that governs how a project moves through the seven stages is in
this module. Views validate shapes; this validates meaning.
"""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from forge.accounts.services import check_may_act
from forge.audit.models import AuditEvent
from forge.audit.services import record as audit
from forge.common.exceptions import DomainRuleViolation, IllegalTransition, NotEligible

from .models import Application, Membership, Project, ProjectReview, StageTransition


@transaction.atomic
def transition(project: Project, to_status: str, *, actor=None, note: str = "") -> Project:
    """
    Move a project to a new stage, or refuse.

    This is the only supported way to change `Project.status`. Assigning the
    field directly elsewhere would bypass the transition table, the timestamps
    and the audit trail, so don't.
    """
    if project.status == to_status:
        return project
    if not project.can_transition_to(to_status):
        allowed = ", ".join(project.TRANSITIONS.get(project.status, ())) or "nothing"
        raise IllegalTransition(
            f"A project that is '{project.get_status_display()}' cannot become "
            f"'{to_status}'. Permitted next stages: {allowed}."
        )

    previous = project.status
    project.status = to_status
    now = timezone.now()
    touched = ["status", "last_activity_at", "updated_at"]
    project.last_activity_at = now

    if to_status == Project.Status.SUBMITTED:
        project.submitted_at = now
        touched.append("submitted_at")
    elif to_status == Project.Status.RECRUITING and project.approved_at is None:
        project.approved_at = now
        touched.append("approved_at")
    elif to_status == Project.Status.COMPLETED:
        project.completed_at = now
        touched.append("completed_at")

    project.save(update_fields=touched)
    StageTransition.objects.create(project=project, from_status=previous,
                                   to_status=to_status, actor=actor, note=note[:500])
    audit(AuditEvent.Action.PROJECT_TRANSITIONED, actor=actor, target=project,
          metadata={"from": previous, "to": to_status, "note": note[:200]})

    from forge.notifications.services import notify_project_team
    notify_project_team(project, verb="project.stage_changed",
                        summary=f"{project.title} moved to {project.get_status_display()}.")
    return project


@transaction.atomic
def submit_for_review(project: Project, *, actor) -> Project:
    check_may_act(actor)
    if not project.is_lead(actor) and not actor.is_superuser:
        raise NotEligible("Only the project lead may submit a proposal for review.")
    if not project.roles.exists():
        raise DomainRuleViolation(
            "Advertise at least one role before submitting. A proposal with no "
            "roles has nothing for anyone to join.",
            code="no_roles",
        )
    if not project.discipline_areas.exists():
        raise DomainRuleViolation(
            "Tag at least one discipline area, so that the right students and "
            "the right mentor can find this.",
            code="no_discipline",
        )

    led = Project.objects.filter(
        lead=actor, status__in=[*Project.ACTIVE_STATUSES, Project.Status.SUBMITTED,
                    Project.Status.UNDER_REVIEW]
    ).exclude(pk=project.pk).count()
    cap = settings.FORGE_POLICY["MAX_LED_PROJECTS"]
    if led >= cap:
        raise DomainRuleViolation(
            f"You are already leading {led} live projects, which is the limit of "
            f"{cap}. Finish or hand one over before starting another. The limit "
            "exists because a team whose lead has disappeared is worse for its "
            "members than a project that was never started.",
            code="lead_capacity",
        )
    return transition(project, Project.Status.SUBMITTED, actor=actor)


@transaction.atomic
def review_proposal(
    project: Project, *, reviewer, decision: str, reasons: str,
    scope_is_realistic: bool = True, is_lawful_and_ethical: bool = True,
    is_not_duplicative: bool = True, has_clear_objectives: bool = True,
    suggested_mentor=None,
) -> ProjectReview:
    """Stage two. The gate that keeps the platform from filling with abandoned ideas."""
    check_may_act(reviewer)
    if not (reviewer.can_review_proposals or reviewer.is_superuser):
        raise NotEligible("Only a mentor, community lead or faculty advisor may "
                          "review proposals.")
    if project.lead_id == reviewer.id:
        raise NotEligible("You cannot review your own proposal.")
    if project.status not in {Project.Status.SUBMITTED, Project.Status.UNDER_REVIEW}:
        raise IllegalTransition("This proposal is not awaiting review.")

    review = ProjectReview(
        project=project, reviewer=reviewer, decision=decision, reasons=reasons,
        scope_is_realistic=scope_is_realistic,
        is_lawful_and_ethical=is_lawful_and_ethical,
        is_not_duplicative=is_not_duplicative,
        has_clear_objectives=has_clear_objectives,
        suggested_mentor=suggested_mentor,
    )
    review.full_clean()
    review.save()

    if project.status == Project.Status.SUBMITTED:
        transition(project, Project.Status.UNDER_REVIEW, actor=reviewer,
                   note="picked up for review")

    outcome = {
        ProjectReview.Decision.APPROVED: Project.Status.RECRUITING,
        ProjectReview.Decision.RETURNED: Project.Status.RETURNED,
        ProjectReview.Decision.DECLINED: Project.Status.DECLINED,
    }[decision]

    if decision == ProjectReview.Decision.APPROVED and project.mentor_id is None:
        # The reviewer becomes the mentor by default. Section 9 assumes a named
        # mentor from approval onwards, because stage 7 needs someone to
        # countersign and an unassigned project has nobody to ask.
        project.mentor = suggested_mentor or reviewer
        project.save(update_fields=["mentor", "updated_at"])

    transition(project, outcome, actor=reviewer, note=reasons[:200])
    audit(AuditEvent.Action.PROJECT_REVIEWED, actor=reviewer, target=project,
          metadata={"decision": decision})

    from forge.notifications.services import notify
    notify(project.lead, verb="project.reviewed", target=project,
           summary=f"Your proposal '{project.title}' was {review.get_decision_display().lower()}.")
    return review


@transaction.atomic
def apply_to_role(*, role, applicant, statement: str) -> Application:
    check_may_act(applicant)
    project = role.project
    if not applicant.may_join_projects:
        raise NotEligible(
            "Alumni keep their portfolio and may mentor, but project roles are "
            "reserved for current students.",
            code="alumni_cannot_join",
        )
    if project.status != Project.Status.RECRUITING:
        raise DomainRuleViolation("This project is not recruiting.")
    if project.lead_id == applicant.id:
        raise DomainRuleViolation("You lead this project.")
    if project.is_member(applicant):
        raise DomainRuleViolation("You are already on this team.")
    if not role.has_vacancy:
        raise DomainRuleViolation("That role is already filled.")

    application = Application.objects.create(project=project, role=role,
                                             applicant=applicant, statement=statement)
    project.touch_activity()

    from forge.notifications.services import notify
    notify(project.lead, verb="application.received", target=application,
           summary=f"{applicant.display_name} applied for {role.title} on {project.title}.")
    return application


@transaction.atomic
def decide_application(application: Application, *, decider, accept: bool,
                       note: str = "") -> Application:
    project = application.project
    if not project.may_manage(decider):
        raise NotEligible("Only the project lead may decide applications.")
    if application.status != Application.Status.PENDING:
        raise DomainRuleViolation("That application has already been decided.")
    if not accept and not note.strip():
        raise DomainRuleViolation(
            "Give a reason when declining. Being turned down without one teaches "
            "the applicant nothing and makes them less likely to apply again.",
            code="reason_required",
        )

    application.status = (Application.Status.ACCEPTED if accept
                          else Application.Status.DECLINED)
    application.decided_at = timezone.now()
    application.decided_by = decider
    application.decision_note = note
    application.save(update_fields=["status", "decided_at", "decided_by",
                                    "decision_note", "updated_at"])

    if accept:
        if not application.role.has_vacancy:
            raise DomainRuleViolation("That role filled up while this application "
                                      "was pending.")
        add_member(project, application.applicant, role=application.role, actor=decider)

    from forge.notifications.services import notify
    notify(application.applicant, verb="application.decided", target=application,
           summary=(f"You were accepted for {application.role.title} on {project.title}."
                    if accept else
                    f"Your application for {application.role.title} was not taken forward."))
    return application


@transaction.atomic
def add_member(project: Project, user, *, role=None, actor=None, is_lead: bool = False):
    if project.memberships.filter(user=user, left_at__isnull=True).exists():
        raise DomainRuleViolation("That member is already on the team.")
    membership = Membership.objects.create(project=project, user=user, role=role,
                                           is_lead=is_lead)
    project.touch_activity()
    audit(AuditEvent.Action.MEMBER_JOINED, actor=actor, target=project,
          metadata={"member": str(user.pk), "role": role.title if role else None})
    return membership


@transaction.atomic
def remove_member(project: Project, user, *, actor, reason: str = "") -> Membership:
    membership = project.memberships.filter(user=user, left_at__isnull=True).first()
    if membership is None:
        raise DomainRuleViolation("That member is not on the team.")
    if membership.is_lead or project.lead_id == user.id:
        raise DomainRuleViolation(
            "Hand the lead over to someone else before leaving. A team without a "
            "lead has nobody who can confirm anyone's contribution.",
            code="lead_must_hand_over",
        )
    if not (project.may_manage(actor) or actor.id == user.id):
        raise NotEligible("Only the lead or the member themselves may do this.")

    membership.left_at = timezone.now()
    membership.left_reason = reason[:255]
    membership.save(update_fields=["left_at", "left_reason", "updated_at"])
    project.touch_activity()
    audit(AuditEvent.Action.MEMBER_LEFT, actor=actor, target=project,
          metadata={"member": str(user.pk), "reason": reason[:200]})
    return membership


@transaction.atomic
def hand_over_lead(project: Project, *, to_user, actor, note: str = "") -> Project:
    """
    Transfer leadership.

    Succession is a commitment in the proposal and, in a volunteer platform,
    it is the difference between a project that survives its founder's exam
    period and one that does not. The incoming lead must already be on the
    team: leadership is not handed to a stranger.
    """
    if not (project.is_lead(actor) or actor.is_superuser):
        raise NotEligible("Only the current lead may hand over.")
    if not project.is_member(to_user):
        raise DomainRuleViolation("The new lead must already be a member of this team.")

    project.memberships.filter(is_lead=True).update(is_lead=False)
    project.memberships.filter(user=to_user, left_at__isnull=True).update(is_lead=True)
    previous = project.lead
    project.lead = to_user
    project.save(update_fields=["lead", "updated_at"])
    project.touch_activity()

    StageTransition.objects.create(
        project=project, from_status=project.status, to_status=project.status,
        actor=actor, note=f"lead handed from {previous.display_name} to {to_user.display_name}",
    )
    from forge.notifications.services import notify_project_team
    notify_project_team(project, verb="project.lead_changed",
                        summary=f"{to_user.display_name} now leads {project.title}.")
    return project


def suggest_roles_for(user, *, limit: int = 10):
    """
    Open roles that fit a member, best first.

    This is ordinary set arithmetic over declared skills and interests, not a
    recommender and emphatically not a model. It is here because the single
    most common way a voluntary platform fails is that a willing student
    cannot find the thing they would have been glad to do.

    Scoring, in order of weight:
      * a required skill the member already has, with evidence behind it
      * a required skill the member has declared without evidence
      * a role the member has flagged as something they want to learn
      * the project's discipline area matching a declared interest
      * a bonus for roles open to beginners where the member has not yet
        completed a project, so that a first-year is offered a way in

    The candidate set -- open roles on projects currently recruiting -- is
    small by construction, so the scoring runs in Python. That is deliberate:
    the equivalent SQL is a tangle of conditional aggregates that the next
    student maintainer would not be able to read, let alone change, and the
    set would have to grow by two orders of magnitude before it mattered.
    """
    from .models import ProjectRole

    skill_ids = set(user.skills.values_list("skill_id", flat=True))
    evidenced_ids = set(
        user.skills.filter(evidence_count__gt=0).values_list("skill_id", flat=True)
    )
    wants_ids = set(user.skills.filter(wants_to_learn=True).values_list("skill_id", flat=True))
    interest_ids = set(user.interests.values_list("id", flat=True))
    is_newcomer = not Membership.objects.filter(
        user=user, project__status=Project.Status.COMPLETED
    ).exists()

    candidates = (
        ProjectRole.objects.filter(
            is_open=True,
            project__status=Project.Status.RECRUITING,
            project__deleted_at__isnull=True,
        )
        .exclude(project__lead=user)
        .exclude(project__memberships__user=user,
                 project__memberships__left_at__isnull=True)
        .exclude(applications__applicant=user,
                 applications__status__in=[Application.Status.PENDING,
                                           Application.Status.ACCEPTED])
        .select_related("project", "project__lead", "project__mentor")
        .prefetch_related("required_skills", "project__discipline_areas",
                          "memberships")
        .distinct()
    )

    scored = []
    for role in candidates:
        if not role.has_vacancy:
            continue

        score = 0
        for skill in role.required_skills.all():
            if skill.id in evidenced_ids:
                score += 5
            elif skill.id in skill_ids:
                score += 3
            elif skill.id in wants_ids:
                score += 2

        if interest_ids & {a.id for a in role.project.discipline_areas.all()}:
            score += 2
        if role.open_to_beginners and is_newcomer:
            score += 3

        role.score = score
        scored.append(role)

    scored.sort(key=lambda r: (-r.score, -r.project.last_activity_at.timestamp()))
    return scored[:limit]
