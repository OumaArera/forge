"""The seven-stage lifecycle and the rules attached to each gate."""

from __future__ import annotations

import pytest

from forge.common.exceptions import DomainRuleViolation, IllegalTransition, NotEligible
from forge.projects.models import Project, ProjectReview, ProjectRole
from forge.projects.services import (
    apply_to_role,
    decide_application,
    hand_over_lead,
    remove_member,
    review_proposal,
    submit_for_review,
    transition,
)

pytestmark = pytest.mark.django_db


class TestTransitionTable:
    def test_a_draft_cannot_jump_straight_to_completed(self, project):
        with pytest.raises(IllegalTransition):
            transition(project, Project.Status.COMPLETED, actor=project.lead)

    def test_a_proposal_cannot_recruit_before_it_is_approved(self, project, role):
        submit_for_review(project, actor=project.lead)
        with pytest.raises(IllegalTransition):
            transition(project, Project.Status.RECRUITING, actor=project.lead)

    def test_the_full_happy_path(self, approved_project, mentor):
        assert approved_project.status == Project.Status.RECRUITING
        assert approved_project.stage == 3

        for status in (Project.Status.BUILDING, Project.Status.IN_REVIEW,
                       Project.Status.DOCUMENTING, Project.Status.COMPLETED):
            transition(approved_project, status, actor=approved_project.lead)

        approved_project.refresh_from_db()
        assert approved_project.status == Project.Status.COMPLETED
        assert approved_project.completed_at is not None
        assert approved_project.stage == 7

    def test_every_transition_is_recorded(self, approved_project):
        transition(approved_project, Project.Status.BUILDING, actor=approved_project.lead,
                   note="team is complete")
        history = list(approved_project.transitions.order_by("created_at"))
        assert [(t.from_status, t.to_status) for t in history] == [
            (Project.Status.DRAFT, Project.Status.SUBMITTED),
            (Project.Status.SUBMITTED, Project.Status.UNDER_REVIEW),
            (Project.Status.UNDER_REVIEW, Project.Status.RECRUITING),
            (Project.Status.RECRUITING, Project.Status.BUILDING),
        ]


class TestSubmissionGate:
    def test_a_proposal_with_no_roles_is_refused(self, project):
        with pytest.raises(DomainRuleViolation) as exc:
            submit_for_review(project, actor=project.lead)
        assert exc.value.code == "no_roles"

    def test_only_the_lead_may_submit(self, project, role, peer):
        with pytest.raises(NotEligible):
            submit_for_review(project, actor=peer)

    def test_a_member_may_not_lead_more_than_the_cap(self, student, area, skill, settings):
        settings.FORGE_POLICY = {**settings.FORGE_POLICY, "MAX_LED_PROJECTS": 2}

        for index in range(3):
            project = Project.objects.create(
                title=f"Project {index}", summary="s",
                problem_statement="p", objectives="o", lead=student,
            )
            project.discipline_areas.add(area)
            ProjectRole.objects.create(project=project, title="Dev", description="d")
            if index < 2:
                submit_for_review(project, actor=student)
            else:
                with pytest.raises(DomainRuleViolation) as exc:
                    submit_for_review(project, actor=student)
                assert exc.value.code == "lead_capacity"


class TestReviewGate:
    def test_a_student_cannot_review_proposals(self, project, role, peer):
        submit_for_review(project, actor=project.lead)
        with pytest.raises(NotEligible):
            review_proposal(project, reviewer=peer,
                            decision=ProjectReview.Decision.APPROVED,
                            reasons="Looks good to me.")

    def test_nobody_reviews_their_own_proposal(self, project, role, mentor):
        project.lead = mentor
        project.save(update_fields=["lead"])
        project.memberships.update(user=mentor)
        submit_for_review(project, actor=mentor)

        with pytest.raises(NotEligible):
            review_proposal(project, reviewer=mentor,
                            decision=ProjectReview.Decision.APPROVED,
                            reasons="My own proposal is excellent.")

    def test_approval_requires_all_four_checks(self, project, role, mentor):
        from django.core.exceptions import ValidationError

        submit_for_review(project, actor=project.lead)
        with pytest.raises(ValidationError):
            review_proposal(project, reviewer=mentor,
                            decision=ProjectReview.Decision.APPROVED,
                            reasons="Approving anyway.",
                            is_not_duplicative=False)

    def test_a_decision_without_reasons_is_refused(self, project, role, mentor):
        from django.core.exceptions import ValidationError

        submit_for_review(project, actor=project.lead)
        with pytest.raises(ValidationError):
            review_proposal(project, reviewer=mentor,
                            decision=ProjectReview.Decision.DECLINED, reasons="   ")

    def test_approval_attaches_a_mentor(self, approved_project, mentor):
        """Stage 7 needs somebody to countersign; an unassigned project has nobody."""
        assert approved_project.mentor == mentor

    def test_a_returned_proposal_can_be_resubmitted(self, project, role, mentor):
        submit_for_review(project, actor=project.lead)
        review_proposal(project, reviewer=mentor,
                        decision=ProjectReview.Decision.RETURNED,
                        reasons="Narrow the scope to one clinic.")
        project.refresh_from_db()
        assert project.status == Project.Status.RETURNED

        submit_for_review(project, actor=project.lead)
        project.refresh_from_db()
        assert project.status == Project.Status.SUBMITTED


class TestTeamFormation:
    def test_applying_and_being_accepted(self, approved_project, role, peer):
        application = apply_to_role(role=role, applicant=peer, statement="I can help.")
        decide_application(application, decider=approved_project.lead, accept=True)

        approved_project.refresh_from_db()
        assert approved_project.is_member(peer)

    def test_declining_requires_a_reason(self, approved_project, role, peer):
        application = apply_to_role(role=role, applicant=peer, statement="I can help.")
        with pytest.raises(DomainRuleViolation) as exc:
            decide_application(application, decider=approved_project.lead, accept=False)
        assert exc.value.code == "reason_required"

    def test_an_alumnus_keeps_their_portfolio_but_not_new_roles(
        self, approved_project, role, peer
    ):
        from forge.accounts.services import deprovision

        deprovision(peer)
        peer.refresh_from_db()
        assert peer.is_verified_member is True      # can still sign in and be seen
        assert peer.may_join_projects is False

        with pytest.raises(NotEligible) as exc:
            apply_to_role(role=role, applicant=peer, statement="Let me back in.")
        assert exc.value.code == "alumni_cannot_join"

    def test_a_full_role_takes_no_more_applications(self, approved_project, peer, nurse):
        role = ProjectRole.objects.create(project=approved_project, title="Sole designer",
                                          description="One slot.", slots=1)
        application = apply_to_role(role=role, applicant=peer, statement="Me.")
        decide_application(application, decider=approved_project.lead, accept=True)

        with pytest.raises(DomainRuleViolation):
            apply_to_role(role=role, applicant=nurse, statement="Me too.")

    def test_only_the_lead_decides(self, approved_project, role, peer, nurse):
        application = apply_to_role(role=role, applicant=peer, statement="I can help.")
        with pytest.raises(NotEligible):
            decide_application(application, decider=nurse, accept=True)


class TestSuccession:
    def test_a_lead_cannot_simply_walk_away(self, approved_project):
        with pytest.raises(DomainRuleViolation) as exc:
            remove_member(approved_project, approved_project.lead,
                          actor=approved_project.lead)
        assert exc.value.code == "lead_must_hand_over"

    def test_handover_requires_an_existing_member(self, approved_project, nurse):
        with pytest.raises(DomainRuleViolation):
            hand_over_lead(approved_project, to_user=nurse, actor=approved_project.lead)

    def test_handover_moves_the_lead_flag(self, approved_project, role, peer):
        application = apply_to_role(role=role, applicant=peer, statement="I can help.")
        decide_application(application, decider=approved_project.lead, accept=True)

        hand_over_lead(approved_project, to_user=peer, actor=approved_project.lead)
        approved_project.refresh_from_db()

        assert approved_project.lead == peer
        assert approved_project.memberships.get(user=peer, left_at__isnull=True).is_lead
        assert not approved_project.memberships.filter(
            is_lead=True).exclude(user=peer).exists()

    def test_a_departing_member_keeps_their_record(self, approved_project, role, peer):
        application = apply_to_role(role=role, applicant=peer, statement="I can help.")
        decide_application(application, decider=approved_project.lead, accept=True)
        remove_member(approved_project, peer, actor=peer, reason="exam period")

        membership = approved_project.memberships.get(user=peer)
        assert membership.left_at is not None
        assert membership.left_reason == "exam period"
        assert membership.days_served >= 0


class TestCrossDisciplinary:
    def test_school_spread_counts_distinct_schools(
        self, approved_project, role, peer, nurse
    ):
        assert approved_project.school_spread == 1
        assert approved_project.is_cross_disciplinary is False

        for applicant in (peer, nurse):
            application = apply_to_role(role=role, applicant=applicant,
                                        statement="I can help.")
            decide_application(application, decider=approved_project.lead, accept=True)

        assert approved_project.school_spread == 2
        assert approved_project.is_cross_disciplinary is True
