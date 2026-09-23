"""
The scheduled jobs.

These address failure modes nothing in the request/response path would ever
catch: projects that quietly die, and students who quietly disappear.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from forge.notifications.models import Notification
from forge.projects.models import Application, Project
from forge.projects.tasks import (
    expire_stale_applications,
    flag_stale_projects,
    nudge_quiet_members,
)

pytestmark = pytest.mark.django_db


class TestStaleProjects:
    def test_a_quiet_project_warns_the_lead_and_mentor_first(
        self, approved_project, mentor, settings
    ):
        Project.all_objects.filter(pk=approved_project.pk).update(
            last_activity_at=timezone.now() - timedelta(days=35))

        result = flag_stale_projects()
        approved_project.refresh_from_db()

        assert result["warned"] == 1
        assert result["abandoned"] == 0
        assert approved_project.status == Project.Status.RECRUITING
        assert Notification.objects.filter(recipient=approved_project.lead,
                                           verb="project.stale").exists()
        assert Notification.objects.filter(recipient=mentor,
                                           verb="project.stale").exists()

    def test_a_long_dead_project_is_archived(self, approved_project):
        """
        A showcase full of projects that stopped six months ago is worse than
        an empty one: it teaches a visitor that nothing here gets finished.
        """
        Project.all_objects.filter(pk=approved_project.pk).update(
            last_activity_at=timezone.now() - timedelta(days=90))

        result = flag_stale_projects()
        approved_project.refresh_from_db()

        assert result["abandoned"] == 1
        assert approved_project.status == Project.Status.ABANDONED

    def test_archiving_is_reversible(self, approved_project):
        from forge.projects.services import transition

        Project.all_objects.filter(pk=approved_project.pk).update(
            last_activity_at=timezone.now() - timedelta(days=90))
        flag_stale_projects()
        approved_project.refresh_from_db()

        transition(approved_project, Project.Status.RECRUITING,
                   actor=approved_project.lead, note="picked back up")
        approved_project.refresh_from_db()
        assert approved_project.status == Project.Status.RECRUITING

    def test_an_active_project_is_left_alone(self, approved_project):
        result = flag_stale_projects()
        assert result == {"warned": 0, "abandoned": 0}


class TestStaleApplications:
    def test_an_unanswered_application_lapses(self, approved_project, role, peer):
        from forge.projects.services import apply_to_role

        application = apply_to_role(role=role, applicant=peer, statement="I can help.")
        Application.objects.filter(pk=application.pk).update(
            created_at=timezone.now() - timedelta(days=30))

        assert expire_stale_applications() == 1
        application.refresh_from_db()
        assert application.status == Application.Status.WITHDRAWN
        assert "Lapsed" in application.decision_note

    def test_a_recent_application_is_untouched(self, approved_project, role, peer):
        from forge.projects.services import apply_to_role

        apply_to_role(role=role, applicant=peer, statement="I can help.")
        assert expire_stale_applications() == 0


class TestQuietMembers:
    def test_a_quiet_member_with_no_projects_is_offered_a_way_in(
        self, approved_project, role, nurse, settings
    ):
        """
        Section 3.2: a student who never collaborates on anything consequential
        is at higher risk of disengaging altogether. The nudge suggests roles
        that actually fit and never mentions how long they have been away.
        """
        from forge.accounts.models import User

        User.objects.filter(pk=nurse.pk).update(
            last_seen_at=timezone.now() - timedelta(days=40))

        result = nudge_quiet_members()
        assert result["nudged"] == 1

        notification = Notification.objects.get(recipient=nurse,
                                                verb="platform.announcement")
        assert role.title in notification.summary
        # Gentle by design: no guilt, no count of days away.
        assert "days" not in notification.summary.lower()

    def test_someone_already_on_a_team_is_not_nudged(
        self, approved_project, role, peer
    ):
        from forge.accounts.models import User
        from forge.projects.services import add_member

        add_member(approved_project, peer, actor=approved_project.lead)
        User.objects.filter(pk=peer.pk).update(
            last_seen_at=timezone.now() - timedelta(days=40))

        assert nudge_quiet_members()["nudged"] == 0

    def test_an_active_member_is_not_nudged(self, approved_project, role, nurse):
        assert nudge_quiet_members()["nudged"] == 0


class TestRoleMatching:
    def test_matching_prefers_evidenced_skills(self, approved_project, role, nurse,
                                               skill, db):
        from forge.accounts.models import Skill, UserSkill
        from forge.projects.models import ProjectRole
        from forge.projects.services import suggest_roles_for

        other_skill = Skill.objects.create(name="Agronomy", slug="agronomy",
                                           is_approved=True)
        weaker = ProjectRole.objects.create(project=approved_project,
                                            title="Field assistant",
                                            description="Collect data.")
        weaker.required_skills.add(other_skill)

        UserSkill.objects.create(user=nurse, skill=skill, evidence_count=3)
        UserSkill.objects.create(user=nurse, skill=other_skill, evidence_count=0)

        suggestions = list(suggest_roles_for(nurse))
        assert suggestions[0].id == role.id

    def test_a_newcomer_is_offered_beginner_roles(self, approved_project, nurse, db):
        """
        A first-year with no track record who cannot find a way in is the
        person most likely to give up on the platform, and exactly who it is for.
        """
        from forge.projects.models import ProjectRole
        from forge.projects.services import suggest_roles_for

        ProjectRole.objects.create(project=approved_project, title="Advanced role",
                                   description="Hard.", open_to_beginners=False)
        beginner = ProjectRole.objects.create(project=approved_project,
                                              title="Documentation helper",
                                              description="Write it up.",
                                              open_to_beginners=True)

        suggestions = list(suggest_roles_for(nurse))
        assert suggestions[0].id == beginner.id

    def test_roles_you_already_applied_for_are_not_suggested(
        self, approved_project, role, peer
    ):
        from forge.projects.services import apply_to_role, suggest_roles_for

        apply_to_role(role=role, applicant=peer, statement="I can help.")
        assert role.id not in {r.id for r in suggest_roles_for(peer)}

    def test_your_own_project_is_not_suggested_to_you(self, approved_project, role):
        from forge.projects.services import suggest_roles_for

        assert list(suggest_roles_for(approved_project.lead)) == []


class TestNotificationDigest:
    def test_a_digest_batches_rather_than_spamming(self, student, peer, db):
        """
        A platform that emails somebody eleven times a day gets muted within a
        week, and is then unable to reach them about the one thing that mattered.
        """
        from django.core import mail

        from forge.notifications.models import NotificationPreference
        from forge.notifications.services import notify, send_digest

        NotificationPreference.objects.create(
            user=student, digest_frequency=NotificationPreference.Digest.DAILY)

        for index in range(5):
            notify(student, verb="community.reply", actor=peer,
                   summary=f"Reply number {index}.")

        assert len(mail.outbox) == 0   # nothing sent immediately

        count = send_digest(student, frequency=NotificationPreference.Digest.DAILY)
        assert count == 5
        assert len(mail.outbox) == 1
        assert "5 updates" in mail.outbox[0].subject

    def test_urgent_notifications_do_not_wait_for_the_digest(
        self, student, peer, db, django_capture_on_commit_callbacks
    ):
        """
        Email for an urgent verb is queued on transaction commit, so that a
        member is never told about something that then rolls back.
        """
        from django.core import mail

        from forge.notifications.models import NotificationPreference
        from forge.notifications.services import notify

        NotificationPreference.objects.create(
            user=student, digest_frequency=NotificationPreference.Digest.DAILY)

        with django_capture_on_commit_callbacks(execute=True):
            notify(student, verb="contribution.disputed", actor=peer,
                   summary="A question was raised about your contribution.")
        assert len(mail.outbox) == 1

    def test_a_muted_category_is_not_recorded(self, student, peer, db):
        from forge.notifications.models import Category, NotificationPreference
        from forge.notifications.services import notify

        NotificationPreference.objects.create(
            user=student, muted_categories=[Category.COMMUNITY])

        assert notify(student, verb="community.reply", actor=peer,
                      summary="A reply.") is None

    def test_nobody_is_notified_about_their_own_action(self, student, db):
        from forge.notifications.services import notify

        assert notify(student, verb="community.reply", actor=student,
                      summary="You replied.") is None
