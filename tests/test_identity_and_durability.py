"""
Identity, verification, deprovisioning and the right to erasure.

The theme running through these tests is that a FORGE record has to outlive
the University account that created it. That is the promise the platform makes
to a student, and it is the promise easiest to break by accident.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.utils import timezone

from forge.accounts.models import User
from forge.accounts.services import (
    deprovision,
    erase_user,
    export_personal_data,
    register_student,
    suggest_public_slug,
)
from forge.common.exceptions import DomainRuleViolation

pytestmark = pytest.mark.django_db


class TestRegistration:
    """
    Joining, under the credentials-by-email rule.

    Students do not choose a password. The platform generates one and sends it
    to the University address, so opening an account requires being able to
    read that mailbox. That is the whole anti-fake-account mechanism, and these
    tests are what keep somebody from quietly reintroducing a password field.
    """

    def test_a_non_university_address_is_refused(self, programme):
        with pytest.raises(DomainRuleViolation) as exc:
            register_student(email="someone@gmail.com", full_name="Someone",
                             programme=programme)
        assert exc.value.code == "not_university_email"

    def test_the_account_is_usable_immediately(self, programme):
        """
        No separate verification step. Receiving the credentials *is* the
        proof of address, so making somebody click a second link would add
        friction without adding any assurance.
        """
        user, _ = register_student(
            email="new.student@ouk.ac.ke", full_name="New Student",
            programme=programme,
        )
        assert user.status == User.Status.ACTIVE
        assert user.is_verified_member is True
        assert user.email_verified_at is not None

    def test_a_generated_password_must_be_replaced(self, programme):
        user, password = register_student(
            email="new.student@ouk.ac.ke", full_name="New Student",
            programme=programme,
        )
        assert user.must_change_password is True
        assert user.check_password(password)

    def test_a_generated_password_can_actually_be_typed(self):
        """
        It is read off a phone and typed into a laptop, so transcribing it has
        to be hard to get wrong. The first real attempt at this failed: a
        mixed-case string lost a character and shifted another.
        """
        import re

        from forge.accounts.services import generated_password

        for _ in range(60):
            password = generated_password()
            # Grouped like a product key: the groups give the eye somewhere to
            # rest and make a dropped character obvious.
            assert re.fullmatch(r"[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}", password), password
            # No character anybody confuses for another.
            assert not set(password) & set("ilo01"), password
            # No shift key: every uppercase pair is a chance to mistype.
            assert password == password.lower()

    def test_generated_passwords_do_not_repeat(self):
        from forge.accounts.services import generated_password

        assert len({generated_password() for _ in range(500)}) == 500

    def test_the_credentials_are_emailed_to_the_university_address(self, programme):
        from forge.common.models_mail import EmailLog

        user, password = register_student(
            email="new.student@ouk.ac.ke", full_name="New Student",
            programme=programme,
        )
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]
        assert password in mail.outbox[0].body

        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.SENT
        assert entry.template == "credentials"
        # The log must never carry the credential it announced.
        assert password not in str(entry.__dict__)

    def test_an_existing_address_cannot_be_used_twice(self, programme):
        register_student(email="new.student@ouk.ac.ke", full_name="New Student",
                         programme=programme)
        with pytest.raises(DomainRuleViolation) as exc:
            register_student(email="new.student@ouk.ac.ke", full_name="Impostor",
                             programme=programme)
        assert exc.value.code == "email_taken"

    def test_the_endpoint_does_not_reveal_whether_an_address_is_taken(
        self, api, programme
    ):
        """
        Both answers are identical, deliberately. A different response would
        turn registration into a way of discovering which students are on the
        platform.
        """
        body = {"full_name": "New Student", "email": "new.student@ouk.ac.ke",
                "programme_id": str(programme.id)}
        first = api.post("/api/v1/accounts/register/", body, format="json")
        second = api.post("/api/v1/accounts/register/", body, format="json")

        assert first.status_code == second.status_code == 202
        assert first.data == second.data
        assert User.objects.filter(email="new.student@ouk.ac.ke").count() == 1

    def test_the_api_ignores_a_password_if_one_is_sent(self, api, programme):
        api.post("/api/v1/accounts/register/", {
            "full_name": "New Student", "email": "new.student@ouk.ac.ke",
            "programme_id": str(programme.id), "password": "chosen-by-me-123",
        }, format="json")
        user = User.objects.get(email="new.student@ouk.ac.ke")
        assert not user.check_password("chosen-by-me-123")

    def test_slugs_do_not_collide(self, user_factory):
        user_factory("a@ouk.ac.ke", "Grace Njeri", slug="grace-njeri")
        assert suggest_public_slug("Grace Njeri") != "grace-njeri"

    def test_reserved_slugs_are_refused(self, db):
        assert suggest_public_slug("admin") != "admin"


class TestPortfolioDurability:
    def test_graduation_keeps_the_portfolio_and_the_slug(self, student):
        original_slug = student.public_slug
        deprovision(student, reason="graduated")
        student.refresh_from_db()

        assert student.status == User.Status.ALUMNUS
        assert student.public_slug == original_slug
        assert student.is_verified_member is True
        assert student.portfolio_is_public is True

    def test_an_alumnus_is_contacted_at_their_recovery_address(self, student):
        from forge.notifications.services import _address_for

        deprovision(student)
        student.refresh_from_db()
        assert _address_for(student) == student.recovery_email

    def test_a_recovery_address_may_not_be_the_university_one(self, student):
        from django.core.exceptions import ValidationError

        student.recovery_email = student.email
        with pytest.raises(ValidationError):
            student.full_clean()


class TestErasure:
    def test_erasure_removes_identity_but_keeps_the_collaborative_record(
        self, approved_project, peer, mentor, advisor
    ):
        """
        The hardest trade-off in the system.

        A teammate's confirmed contributions reference the same project and the
        same reviews. If one member could silently rewrite that, every other
        member's portfolio would quietly lose its backing.
        """
        from forge.contributions.models import Dimension, LedgerEntry
        from forge.contributions.services import attest, submit
        from forge.projects.services import add_member

        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = approved_project.contributions.create(
            contributor=peer, dimension=Dimension.DELIVERY,
            description="Built the ingest job.", occurred_on=timezone.localdate(),
        )
        submit(contribution, actor=peer)
        attest(contribution, attestor=approved_project.lead, confirm=True)
        attest(contribution, attestor=mentor, confirm=True)

        entry_count_before = LedgerEntry.objects.count()
        original_email = peer.email

        erase_user(peer, requested_by=advisor)
        peer.refresh_from_db()

        assert peer.status == User.Status.CLOSED
        assert peer.full_name == "Former member"
        assert original_email not in peer.email
        assert peer.email.endswith("@erased.invalid")
        assert peer.bio == ""
        assert peer.portfolio_is_public is False
        assert not peer.skills.exists()

        # The record other people depend on is untouched.
        assert LedgerEntry.objects.count() == entry_count_before
        entry = LedgerEntry.objects.latest("sequence")
        assert entry.is_intact

    def test_an_attestors_name_survives_their_erasure(
        self, approved_project, peer, mentor, advisor
    ):
        """
        Otherwise every portfolio the mentor ever confirmed loses its backing
        the day the mentor leaves.
        """
        from forge.contributions.models import Attestation, Dimension
        from forge.contributions.services import attest, submit
        from forge.projects.services import add_member

        add_member(approved_project, peer, actor=approved_project.lead)
        contribution = approved_project.contributions.create(
            contributor=peer, dimension=Dimension.DELIVERY,
            description="Wrote the tests.", occurred_on=timezone.localdate(),
        )
        submit(contribution, actor=peer)
        attest(contribution, attestor=approved_project.lead, confirm=True)
        attest(contribution, attestor=mentor, confirm=True)

        mentor_name = mentor.display_name
        erase_user(mentor, requested_by=advisor)

        attestation = Attestation.objects.get(contribution=contribution,
                                              capacity=Attestation.Capacity.MENTOR)
        assert attestation.attestor_name == mentor_name

    def test_erasing_twice_is_refused(self, peer, advisor):
        erase_user(peer, requested_by=advisor)
        peer.refresh_from_db()
        with pytest.raises(DomainRuleViolation):
            erase_user(peer, requested_by=advisor)


class TestDataExport:
    def test_export_covers_the_account_and_omits_secrets(self, student):
        data = export_personal_data(student)

        assert data["account"]["email"] == student.email
        assert data["account"]["public_slug"] == student.public_slug
        assert "skills" in data and "project_memberships" in data

        # An export is a document a member may forward to anybody. It must not
        # carry a password hash or any verification token.
        serialised = str(data)
        assert student.password not in serialised
        assert "token" not in serialised.lower()


class TestRoles:
    def test_a_role_grant_records_who_made_it(self, student, advisor):
        from forge.accounts.models import RoleGrant
        from forge.accounts.services import grant_role

        grant = grant_role(user=student, role=RoleGrant.Role.COMMUNITY_LEAD,
                           granted_by=advisor, note="Trimester 2")
        assert grant.granted_by == advisor
        assert grant.is_active is True

    def test_an_expired_grant_confers_nothing(self, student, advisor):
        from datetime import timedelta

        from forge.accounts.models import RoleGrant
        from forge.accounts.services import grant_role

        grant_role(user=student, role=RoleGrant.Role.MODERATOR, granted_by=advisor,
                   expires_at=timezone.now() - timedelta(days=1))
        student.refresh_from_db()
        assert student.can_moderate is False

    def test_revoking_a_grant_removes_the_capability(self, student, advisor):
        from forge.accounts.models import RoleGrant
        from forge.accounts.services import grant_role, revoke_role

        grant = grant_role(user=student, role=RoleGrant.Role.MODERATOR,
                           granted_by=advisor)
        student = User.objects.get(pk=student.pk)
        assert student.can_moderate is True

        revoke_role(grant=grant, revoked_by=advisor, note="trimester ended")
        student = User.objects.get(pk=student.pk)
        assert student.can_moderate is False


class TestSignIn:
    def test_an_account_that_never_confirmed_is_not_issued_a_token(self, api, school):
        """
        No registration path leaves an account PENDING any more, but the gate
        stays: an account in that state -- a legacy row, or one created by
        hand -- must not be able to sign in.
        """
        user = User(email="unconfirmed@ouk.ac.ke", full_name="Unconfirmed Person",
                    public_slug="unconfirmed-person", status=User.Status.PENDING,
                    school=school)
        user.set_password("a-long-enough-password")
        user.save()

        response = api.post("/api/v1/accounts/token/", {
            "email": "unconfirmed@ouk.ac.ke", "password": "a-long-enough-password",
        }, format="json")

        assert response.status_code == 400
        assert "email_not_verified" in str(response.data)

    def test_a_generated_password_is_flagged_for_replacement_at_sign_in(
        self, api, programme
    ):
        user, password = register_student(
            email="new.student@ouk.ac.ke", full_name="New Student",
            programme=programme,
        )
        response = api.post("/api/v1/accounts/token/", {
            "email": user.email, "password": password,
        }, format="json")

        assert response.status_code == 200
        # The client uses this to hold the member at the change-password screen.
        assert response.data["member"]["must_change_password"] is True

    def test_choosing_a_password_clears_the_flag(self, api, programme):
        user, password = register_student(
            email="new.student@ouk.ac.ke", full_name="New Student",
            programme=programme,
        )
        api.force_authenticate(user=user)
        response = api.post("/api/v1/accounts/me/password/", {
            "current_password": password, "new_password": "my-own-choice-2026",
        }, format="json")

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.must_change_password is False
        assert user.check_password("my-own-choice-2026")

    def test_a_verified_account_signs_in(self, api, student):
        response = api.post("/api/v1/accounts/token/", {
            "email": student.email, "password": "a-long-enough-password",
        }, format="json")

        assert response.status_code == 200
        assert "access" in response.data
        assert response.data["member"]["public_slug"] == student.public_slug

    def test_a_suspended_account_cannot_sign_in(self, api, student):
        student.status = User.Status.SUSPENDED
        student.save(update_fields=["status"])

        response = api.post("/api/v1/accounts/token/", {
            "email": student.email, "password": "a-long-enough-password",
        }, format="json")
        assert response.status_code == 400
        assert "suspended" in str(response.data).lower()

    def test_an_alumnus_signs_in_with_their_recovery_address(self, api, student):
        """
        The practical half of the durability promise. Losing the University
        account must not lock somebody out of the record it exists to give them.
        """
        deprovision(student)
        student.refresh_from_db()

        response = api.post("/api/v1/accounts/token/", {
            "email": student.recovery_email, "password": "a-long-enough-password",
        }, format="json")

        assert response.status_code == 200
        assert response.data["member"]["public_slug"] == student.public_slug

    def test_an_erased_account_cannot_sign_in(self, api, student, advisor):
        original_email = student.email
        erase_user(student, requested_by=advisor)

        response = api.post("/api/v1/accounts/token/", {
            "email": original_email, "password": "a-long-enough-password",
        }, format="json")
        assert response.status_code == 401
