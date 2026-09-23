"""
End-to-end API behaviour and the permission boundaries.

A missing permission check on one endpoint is worth more to an attacker than
a correct check on the other five, so the negative cases here matter more than
the positive ones.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from forge.accounts.models import User
from forge.projects.models import Project

pytestmark = pytest.mark.django_db


class TestOperationalEndpoints:
    def test_health_does_not_touch_the_database(self, client, django_assert_num_queries):
        with django_assert_num_queries(0):
            response = client.get("/healthz/")
        assert response.status_code == 200

    def test_readiness_checks_the_database(self, client):
        response = client.get("/readyz/")
        assert response.status_code == 200
        assert response.json()["checks"]["database"] == "ok"


class TestPublicSurface:
    def test_reference_data_is_one_request(self, api, school, programme, area, skill):
        """
        Five round trips before a registration form can be drawn is four too
        many for somebody on a constrained connection.
        """
        response = api.get("/api/v1/accounts/reference/")
        assert response.status_code == 200
        assert {"schools", "programmes", "discipline_areas", "skills"} <= set(
            response.data)
        assert len(response.data["programmes"]) == 1

    def test_the_ledger_is_readable_without_an_account(self, api):
        """A verifiable record only members can read is not verifiable."""
        assert api.get("/api/v1/contributions/ledger/").status_code == 200
        assert api.get("/api/v1/contributions/ledger/verify/").status_code == 200

    def test_anonymous_callers_cannot_write(self, api, area):
        response = api.post("/api/v1/projects/", {
            "title": "Anonymous project", "summary": "s",
            "problem_statement": "p", "objectives": "o",
            "discipline_area_ids": [str(area.id)],
        }, format="json")
        assert response.status_code in (401, 403)

    def test_a_draft_project_is_not_publicly_listed(self, api, project):
        response = api.get("/api/v1/projects/")
        titles = [p["title"] for p in response.data["results"]]
        assert project.title not in titles


class TestVerificationGate:
    def test_an_unverified_member_cannot_act(self, api, school, programme, area):
        unverified = User(email="pending@ouk.ac.ke", full_name="Pending Person",
                          public_slug="pending-person", status=User.Status.PENDING,
                          school=school, programme=programme)
        unverified.set_password("a-long-enough-password")
        unverified.save()

        api.force_authenticate(user=unverified)
        response = api.post("/api/v1/projects/", {
            "title": "Too soon", "summary": "s", "problem_statement": "p",
            "objectives": "o", "discipline_area_ids": [str(area.id)],
        }, format="json")
        assert response.status_code == 403
        assert "verify" in str(response.data).lower()


class TestProjectApi:
    def test_creating_a_project_makes_the_proposer_a_member(self, api, student, area):
        api.force_authenticate(user=student)
        response = api.post("/api/v1/projects/", {
            "title": "Field data collection for smallholder farms",
            "summary": "Collect and analyse yield data with partner farmers.",
            "problem_statement": "Farmers have no record of what worked last season.",
            "objectives": "A working data collection tool and one season of data.",
            "discipline_area_ids": [str(area.id)],
        }, format="json")

        assert response.status_code == 201
        project = Project.objects.get(title__startswith="Field data")
        assert project.lead == student
        assert project.is_member(student)

    def test_a_non_lead_cannot_edit(self, api, approved_project, peer):
        api.force_authenticate(user=peer)
        response = api.patch(f"/api/v1/projects/{approved_project.slug}/",
                             {"title": "Hijacked"}, format="json")
        assert response.status_code == 403

    def test_a_draft_is_invisible_to_outsiders(self, api, project, peer):
        """
        404 rather than 403, deliberately.

        A draft proposal is private to its author and to reviewers, and 403
        would confirm that a project by that name exists -- which is itself
        the information being withheld.
        """
        api.force_authenticate(user=peer)
        assert api.get(f"/api/v1/projects/{project.slug}/").status_code == 404
        assert api.patch(f"/api/v1/projects/{project.slug}/",
                         {"title": "Hijacked"}, format="json").status_code == 404

    def test_a_student_cannot_review(self, api, approved_project, peer):
        """A recruiting project is visible to everyone; reviewing it is not."""
        api.force_authenticate(user=peer)
        response = api.post(f"/api/v1/projects/{approved_project.slug}/review/", {
            "decision": "approved", "reasons": "Looks fine to me.",
        }, format="json")
        assert response.status_code == 403

    def test_a_mentor_sees_the_review_queue(self, api, project, role, mentor):
        from forge.projects.services import submit_for_review

        submit_for_review(project, actor=project.lead)
        api.force_authenticate(user=mentor)
        response = api.get("/api/v1/projects/awaiting-review/")
        assert response.status_code == 200
        assert any(p["title"] == project.title for p in response.data["results"])

    def test_the_detail_view_reports_permitted_next_stages(
        self, api, approved_project, student
    ):
        api.force_authenticate(user=student)
        response = api.get(f"/api/v1/projects/{approved_project.slug}/")
        assert response.status_code == 200
        assert set(response.data["permitted_transitions"]) == {
            "building", "abandoned", "archived"}
        assert response.data["my_role"] == "lead"


class TestContributionApi:
    def test_the_attestation_queue_shows_only_what_is_waiting_on_you(
        self, api, approved_project, peer, mentor
    ):
        """
        Confirmations are the bottleneck in this scheme. A lead three weeks
        behind is a team whose portfolios are all empty, so this queue has to
        be trivially easy to find and honest about what is in it.
        """
        from forge.contributions.models import Dimension
        from forge.contributions.services import attest, submit
        from forge.projects.services import add_member

        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = approved_project.contributions.create(
            contributor=peer, dimension=Dimension.DELIVERY,
            description="Wrote the importer.", occurred_on=timezone.localdate(),
        )
        submit(contribution, actor=peer)

        api.force_authenticate(user=approved_project.lead)
        response = api.get("/api/v1/contributions/awaiting-my-attestation/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

        attest(contribution, attestor=approved_project.lead, confirm=True)
        response = api.get("/api/v1/contributions/awaiting-my-attestation/")
        assert len(response.data["results"]) == 0

        # It is still waiting on the mentor.
        api.force_authenticate(user=mentor)
        response = api.get("/api/v1/contributions/awaiting-my-attestation/")
        assert len(response.data["results"]) == 1

    def test_you_cannot_log_work_on_a_project_you_are_not_on(
        self, api, approved_project, nurse
    ):
        api.force_authenticate(user=nurse)
        response = api.post("/api/v1/contributions/", {
            "project": str(approved_project.id), "dimension": "delivery",
            "description": "I helped, honestly.",
            "occurred_on": str(timezone.localdate()),
        }, format="json")
        assert response.status_code == 403

    def test_ai_assistance_must_be_described_when_declared(
        self, api, approved_project, student
    ):
        api.force_authenticate(user=student)
        response = api.post("/api/v1/contributions/", {
            "project": str(approved_project.id), "dimension": "delivery",
            "description": "Generated the serialisers.",
            "occurred_on": str(timezone.localdate()),
            "ai_assistance": "generated",
        }, format="json")
        assert response.status_code == 400
        assert "ai_assistance_note" in str(response.data)


class TestWorkspaceIsolation:
    def test_another_team_cannot_read_your_tasks(self, api, approved_project, nurse):
        from forge.workspace.models import Task

        Task.objects.create(project=approved_project, title="Private task",
                            created_by=approved_project.lead)

        api.force_authenticate(user=nurse)
        response = api.get("/api/v1/workspace/tasks/")
        assert response.status_code == 200
        assert response.data["results"] == []


class TestErrorShape:
    def test_domain_errors_use_one_consistent_shape(self, api, approved_project, peer):
        """A frontend that can rely on one error shape spends its time on the
        interface rather than on error parsing."""
        api.force_authenticate(user=peer)
        response = api.post(f"/api/v1/projects/{approved_project.slug}/submit/")
        assert response.status_code == 403
        assert "error" in response.data
        assert set(response.data["error"]) >= {"code", "detail"}


class TestModeration:
    def test_serious_categories_are_escalated_to_the_advisor(
        self, api, student, peer, advisor
    ):
        from forge.moderation.models import Report

        api.force_authenticate(user=student)
        response = api.post("/api/v1/moderation/reports/", {
            "target_model": "accounts.user", "target_id": str(peer.id),
            "reason": "harassment",
            "detail": "Repeated abusive messages in the Health space.",
        }, format="json")

        assert response.status_code == 201
        report = Report.objects.get()
        assert report.status == Report.Status.ESCALATED

    def test_a_student_moderator_cannot_close_an_escalated_report(
        self, api, student, peer, advisor
    ):
        from forge.accounts.models import RoleGrant
        from forge.accounts.services import grant_role
        from forge.moderation.models import Report

        grant_role(user=student, role=RoleGrant.Role.MODERATOR, granted_by=advisor)
        report = Report.objects.create(
            reporter=peer, target_type=__import__(
                "django.contrib.contenttypes.models", fromlist=["ContentType"]
            ).ContentType.objects.get(app_label="accounts", model="user"),
            target_id=str(peer.id), reason=Report.Reason.HARASSMENT,
            detail="Something serious.", status=Report.Status.ESCALATED,
        )

        api.force_authenticate(user=User.objects.get(pk=student.pk))
        response = api.post(f"/api/v1/moderation/reports/{report.id}/act/", {
            "action": "suspend",
            "rationale": "This warrants a suspension of the member's account.",
            "expires_at": (timezone.now() + timezone.timedelta(days=7)).isoformat(),
        }, format="json")
        assert response.status_code == 403
        assert "faculty advisor" in str(response.data).lower()

    def test_a_moderation_action_requires_a_real_rationale(
        self, api, student, peer, advisor
    ):
        from forge.moderation.models import Report

        report = Report.objects.create(
            reporter=peer, target_type=__import__(
                "django.contrib.contenttypes.models", fromlist=["ContentType"]
            ).ContentType.objects.get(app_label="accounts", model="user"),
            target_id=str(student.id), reason=Report.Reason.SPAM,
            detail="Advertising.",
        )
        api.force_authenticate(user=advisor)
        response = api.post(f"/api/v1/moderation/reports/{report.id}/act/", {
            "action": "warn", "rationale": "bad",
        }, format="json")
        assert response.status_code == 400
