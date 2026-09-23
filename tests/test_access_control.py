"""
Abuse control, invitations and administration.

The theme is that every one of these is a control somebody will eventually try
to route around, so each is tested from the attacker's side as well as the
ordinary one.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.core.cache import cache
from django.utils import timezone

from forge.accounts import lockout
from forge.accounts.models import Invitation, RoleGrant, User
from forge.accounts.services import (
    accept_invitation,
    cancel_recovery_email,
    invite,
    peek_invitation,
    register_student,
    request_recovery_email,
    resend_invitation,
    revoke_invitation,
    verify_email,
)
from forge.common.exceptions import DomainRuleViolation

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean_cache():
    """Throttle and lockout counters live in the cache, so tests must not share."""
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------- lockout


class TestSignInLockout:
    def test_repeated_failures_lock_the_account(self, api, student):
        for _ in range(5):
            api.post("/api/v1/accounts/token/",
                     {"email": student.email, "password": "wrong"}, format="json")

        assert lockout.is_locked(student.email) is True

        # Even the correct password is refused while the lock stands.
        response = api.post("/api/v1/accounts/token/", {
            "email": student.email, "password": "a-long-enough-password",
        }, format="json")
        assert response.status_code == 400
        assert "account_locked" in str(response.data)

    def test_the_lock_lengthens_with_repetition(self, student):
        for _ in range(5):
            lockout.record_failure(student.email)
        first = lockout.locked_until(student.email)

        for _ in range(7):
            lockout.record_failure(student.email)
        second = lockout.locked_until(student.email)

        assert second > first

    def test_a_correct_password_clears_the_count(self, api, student):
        for _ in range(3):
            api.post("/api/v1/accounts/token/",
                     {"email": student.email, "password": "wrong"}, format="json")
        assert lockout.remaining_attempts(student.email) == 2

        response = api.post("/api/v1/accounts/token/", {
            "email": student.email, "password": "a-long-enough-password",
        }, format="json")
        assert response.status_code == 200
        assert lockout.remaining_attempts(student.email) == 5

    def test_an_unknown_address_is_counted_too(self):
        """
        Otherwise the addresses that can be retried forever are exactly the
        ones with no account, which is an enumeration oracle.
        """
        for _ in range(5):
            lockout.record_failure("nobody@ouk.ac.ke")
        assert lockout.is_locked("nobody@ouk.ac.ke") is True

    def test_the_member_is_told_once(self, student):
        for _ in range(5):
            lockout.record_failure(student.email)
        assert len(mail.outbox) == 1
        assert "locked" in mail.outbox[0].subject.lower()

        for _ in range(3):
            lockout.record_failure(student.email)
        assert len(mail.outbox) == 1  # not once per failure

    def test_a_steward_can_unlock_without_changing_the_password(
        self, api, student, advisor
    ):
        for _ in range(5):
            lockout.record_failure(student.email)

        api.force_authenticate(user=advisor)
        response = api.post(f"/api/v1/accounts/admin/members/{student.public_slug}/unlock/")
        assert response.status_code == 200
        assert response.data["was_locked"] is True
        assert lockout.is_locked(student.email) is False


class TestThrottling:
    """
    Tested against the rates that actually ship.

    Overriding them in the test would prove that DRF can throttle, which was
    never in doubt. What matters is whether the configured numbers engage, and
    whether they are loose enough that ordinary use never meets them.
    """

    def test_sign_in_is_rate_limited_per_source_address(self, api):
        codes = [
            api.post("/api/v1/accounts/token/",
                     {"email": f"guess{index}@ouk.ac.ke", "password": "wrong"},
                     format="json").status_code
            for index in range(14)
        ]
        assert 429 in codes, f"expected the login throttle to engage: {codes}"
        # It has to allow a reasonable number of honest mistakes first.
        assert codes.index(429) >= 5

    def test_sign_in_is_rate_limited_per_account(self, api, student):
        """
        The complement of the address limit: this is what makes a distributed
        attack on one known account expensive.
        """
        codes = [
            api.post("/api/v1/accounts/token/",
                     {"email": student.email, "password": "wrong"},
                     format="json").status_code
            for index in range(12)
        ]
        assert 429 in codes, f"expected the per-account throttle to engage: {codes}"

    def test_registration_is_rate_limited(self, api, programme):
        codes = [
            api.post("/api/v1/accounts/register/", {
                "full_name": f"Person {index}",
                "email": f"person{index}@students.ouk.ac.ke",
                "programme_id": str(programme.id),
            }, format="json").status_code
            for index in range(9)
        ]
        assert 429 in codes, f"expected the registration throttle to engage: {codes}"

    def test_an_ordinary_page_load_is_nowhere_near_the_limit(self, api, student):
        """
        A limit that ordinary use trips is a limit that gets removed. The
        dashboard fires roughly a dozen requests on mount; thirty in a row
        must still be fine.
        """
        api.force_authenticate(user=student)
        codes = [api.get("/api/v1/accounts/me/").status_code for _ in range(30)]
        assert set(codes) == {200}


# ------------------------------------------------------------ recovery email


class TestRecoveryAddress:
    def test_submitting_an_address_holds_it_as_pending(self, student):
        """
        The earlier version stored nothing until confirmation, so the form
        appeared to do nothing at all. The pending field is what lets the
        interface say 'waiting on you'.
        """
        previous = student.recovery_email
        request_recovery_email(student, "personal@example.com")
        student.refresh_from_db()

        assert student.pending_recovery_email == "personal@example.com"
        # Unconfirmed, so the address in force has not changed yet.
        assert student.recovery_email == previous

    def test_the_link_goes_to_the_address_being_claimed(self, student):
        request_recovery_email(student, "personal@example.com")
        assert mail.outbox[-1].to == ["personal@example.com"]

    def test_confirming_promotes_it(self, student):
        from forge.accounts.models import EmailVerification
        from forge.accounts.services import hash_token, verify_email

        request_recovery_email(student, "personal@example.com")

        # Recover the plaintext token the way the recipient would: from the email.
        body = mail.outbox[-1].body
        token = body.split("token=")[1].split()[0].strip()
        assert EmailVerification.objects.filter(token_hash=hash_token(token)).exists()

        user, already = verify_email(token)
        assert already is False
        student.refresh_from_db()
        assert student.recovery_email == "personal@example.com"
        assert student.pending_recovery_email == ""

    def test_correcting_a_typo_invalidates_the_first_link(self, student):
        request_recovery_email(student, "typo@example.com")
        first_token = mail.outbox[-1].body.split("token=")[1].split()[0].strip()

        request_recovery_email(student, "correct@example.com")

        from forge.accounts.services import verify_email

        with pytest.raises(DomainRuleViolation):
            verify_email(first_token)

    def test_the_university_address_is_refused(self, student):
        with pytest.raises(DomainRuleViolation) as exc:
            request_recovery_email(student, student.email)
        assert exc.value.code == "same_as_university_email"

    def test_a_pending_address_can_be_withdrawn(self, student):
        request_recovery_email(student, "personal@example.com")
        cancel_recovery_email(student)
        student.refresh_from_db()
        assert student.pending_recovery_email == ""

    def test_the_api_returns_the_updated_member(self, api, student):
        api.force_authenticate(user=student)
        response = api.post("/api/v1/accounts/me/recovery-email/",
                            {"recovery_email": "personal@example.com"}, format="json")
        assert response.status_code == 202
        assert response.data["member"]["pending_recovery_email"] == "personal@example.com"
        assert response.data["delivered"] is True

    def test_a_failed_send_still_records_the_pending_address(self, api, student, settings):
        """
        A transient mail failure must not lose what the member typed, or they
        have to type it again with no idea why.
        """
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = "127.0.0.1"
        settings.EMAIL_PORT = 1  # nothing listens here

        api.force_authenticate(user=student)
        response = api.post("/api/v1/accounts/me/recovery-email/",
                            {"recovery_email": "personal@example.com"}, format="json")

        assert response.status_code == 202
        assert response.data["delivered"] is False
        student.refresh_from_db()
        assert student.pending_recovery_email == "personal@example.com"

    def test_a_failed_send_is_visible_in_the_email_log(self, student, settings):
        from forge.common.models_mail import EmailLog

        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = "127.0.0.1"
        settings.EMAIL_PORT = 1

        request_recovery_email(student, "personal@example.com")

        entry = EmailLog.objects.latest("created_at")
        assert entry.status == EmailLog.Status.FAILED
        assert entry.error


class TestVerificationLinks:
    """
    Opening a confirmation link.

    The failure that prompted these: a link was opened, it worked, and the
    screen said it had not. React's development StrictMode ran the effect
    twice — the first request consumed the token and succeeded, the second
    found it consumed and failed, and the failure resolved last.
    """

    def _token(self, student) -> str:
        request_recovery_email(student, "personal@example.com")
        return mail.outbox[-1].body.split("token=")[1].split()[0].strip()

    def test_opening_the_same_link_twice_still_reports_success(self, student):
        """
        A mail client prefetching the link, a restored tab, a double-click and
        a double-invoked effect all look identical from here, and all of them
        are innocent. Nothing is re-granted — only the reporting changes.
        """
        token = self._token(student)

        first_user, first_already = verify_email(token)
        second_user, second_already = verify_email(token)

        assert first_already is False
        assert second_already is True
        assert first_user.pk == second_user.pk

        student.refresh_from_db()
        assert student.recovery_email == "personal@example.com"

    def test_a_superseded_link_says_so_specifically(self, student):
        """
        Distinguished from 'already used': this one did not achieve its goal,
        because a newer request replaced it. The remedy is different — open
        the most recent email, not request another.
        """
        first = self._token(student)
        self._token(student)  # a second request supersedes the first

        with pytest.raises(DomainRuleViolation) as exc:
            verify_email(first)
        assert exc.value.code == "superseded_verification"

    def test_an_expired_link_says_so_specifically(self, student):
        from datetime import timedelta

        from forge.accounts.models import EmailVerification

        token = self._token(student)
        EmailVerification.objects.update(expires_at=timezone.now() - timedelta(hours=1))

        with pytest.raises(DomainRuleViolation) as exc:
            verify_email(token)
        assert exc.value.code == "expired_verification"

    def test_an_unknown_token_says_so_specifically(self, db):
        with pytest.raises(DomainRuleViolation) as exc:
            verify_email("not-a-real-token-at-all")
        assert exc.value.code == "unknown_verification"

    def test_the_api_reports_the_purpose_so_the_client_can_route_the_remedy(
        self, api, student
    ):
        """
        A recovery-address link and a registration link fail for the same
        reasons and need completely different next steps. An earlier version
        of the page always offered the registration resend, which is the wrong
        door for somebody confirming a personal address.
        """
        token = self._token(student)
        response = api.post("/api/v1/accounts/verify-email/", {"token": token},
                            format="json")

        assert response.status_code == 200
        assert response.data["purpose"] == "recovery_email"
        assert response.data["confirmed_address"] == "personal@example.com"
        assert response.data["already_confirmed"] is False

    def test_the_api_repeats_cleanly(self, api, student):
        token = self._token(student)
        first = api.post("/api/v1/accounts/verify-email/", {"token": token},
                         format="json")
        second = api.post("/api/v1/accounts/verify-email/", {"token": token},
                          format="json")

        assert first.status_code == 200 and second.status_code == 200
        assert second.data["already_confirmed"] is True


# ---------------------------------------------------------------- invitations


class TestInvitations:
    def test_a_steward_can_invite_a_non_university_address(self, advisor):
        """
        The whole reason invitations exist: staff, alumni and partners have no
        students.ouk.ac.ke address and cannot use the open route.
        """
        invitation = invite(email="partner@example.com", invited_by=advisor,
                            kind=User.Kind.EXTERNAL, full_name="A Partner",
                            message="We would like your help on the clinic project.")
        assert invitation.status == Invitation.Status.PENDING
        assert mail.outbox[-1].to == ["partner@example.com"]
        assert "clinic project" in mail.outbox[-1].body

    def test_accepting_creates_the_account_and_emails_credentials(self, advisor):
        invite(email="partner@example.com", invited_by=advisor,
               kind=User.Kind.EXTERNAL, full_name="A Partner")
        token = mail.outbox[-1].body.split("token=")[1].split()[0].strip()

        user = accept_invitation(token=token, full_name="A Partner")

        assert user.email == "partner@example.com"
        assert user.kind == User.Kind.EXTERNAL
        assert user.must_change_password is True
        assert mail.outbox[-1].to == ["partner@example.com"]
        assert "password" in mail.outbox[-1].body.lower()

    def test_a_role_on_the_invitation_is_granted_on_acceptance(self, advisor):
        invite(email="mentor@example.com", invited_by=advisor,
               kind=User.Kind.EXTERNAL, role=RoleGrant.Role.MENTOR)
        token = mail.outbox[-1].body.split("token=")[1].split()[0].strip()

        user = accept_invitation(token=token, full_name="A Mentor")
        assert user.has_role(RoleGrant.Role.MENTOR)

    def test_a_token_works_once(self, advisor):
        invite(email="partner@example.com", invited_by=advisor,
               kind=User.Kind.EXTERNAL)
        token = mail.outbox[-1].body.split("token=")[1].split()[0].strip()
        accept_invitation(token=token, full_name="A Partner")

        with pytest.raises(DomainRuleViolation):
            accept_invitation(token=token, full_name="Somebody Else")

    def test_a_revoked_invitation_cannot_be_accepted(self, advisor):
        invitation = invite(email="partner@example.com", invited_by=advisor,
                            kind=User.Kind.EXTERNAL)
        token = mail.outbox[-1].body.split("token=")[1].split()[0].strip()
        revoke_invitation(invitation, actor=advisor)

        with pytest.raises(DomainRuleViolation):
            accept_invitation(token=token, full_name="A Partner")

    def test_an_expired_invitation_cannot_be_accepted(self, advisor):
        from datetime import timedelta

        invitation = invite(email="partner@example.com", invited_by=advisor,
                            kind=User.Kind.EXTERNAL)
        token = mail.outbox[-1].body.split("token=")[1].split()[0].strip()
        Invitation.objects.filter(pk=invitation.pk).update(
            expires_at=timezone.now() - timedelta(days=1))

        with pytest.raises(DomainRuleViolation):
            peek_invitation(token)

    def test_resending_invalidates_the_previous_link(self, advisor):
        invitation = invite(email="partner@example.com", invited_by=advisor,
                            kind=User.Kind.EXTERNAL)
        first = mail.outbox[-1].body.split("token=")[1].split()[0].strip()

        resend_invitation(invitation, actor=advisor)

        with pytest.raises(DomainRuleViolation):
            peek_invitation(first)

    def test_inviting_an_existing_member_is_refused(self, advisor, student):
        with pytest.raises(DomainRuleViolation) as exc:
            invite(email=student.email, invited_by=advisor)
        assert exc.value.code == "already_member"

    def test_only_a_hash_of_the_token_is_stored(self, advisor):
        invite(email="partner@example.com", invited_by=advisor,
               kind=User.Kind.EXTERNAL)
        token = mail.outbox[-1].body.split("token=")[1].split()[0].strip()

        stored = Invitation.objects.get().token_hash
        assert token not in stored
        assert len(stored) == 64

    def test_an_ordinary_student_cannot_invite(self, api, student):
        api.force_authenticate(user=student)
        response = api.post("/api/v1/accounts/invitations/", {
            "email": "friend@example.com", "kind": "external",
        }, format="json")
        assert response.status_code == 403

    def test_a_steward_can_invite_through_the_api(self, api, advisor):
        api.force_authenticate(user=advisor)
        response = api.post("/api/v1/accounts/invitations/", {
            "email": "partner@example.com", "kind": "external",
            "role": "mentor", "message": "Please join us.",
        }, format="json")
        assert response.status_code == 201
        assert response.data["email"] == "partner@example.com"

    def test_the_preview_does_not_consume_the_token(self, advisor):
        invite(email="partner@example.com", invited_by=advisor,
               kind=User.Kind.EXTERNAL, message="Come and help.")
        token = mail.outbox[-1].body.split("token=")[1].split()[0].strip()

        preview = peek_invitation(token)
        assert preview.message == "Come and help."
        assert peek_invitation(token) is not None  # still usable


# -------------------------------------------------------------- administration


class TestAdministration:
    def test_a_student_cannot_reach_the_console(self, api, student):
        api.force_authenticate(user=student)
        assert api.get("/api/v1/accounts/admin/overview/").status_code == 403
        assert api.get("/api/v1/accounts/admin/members/").status_code == 403
        assert api.get("/api/v1/accounts/admin/email-log/").status_code == 403

    def test_a_steward_sees_the_overview(self, api, advisor, student):
        api.force_authenticate(user=advisor)
        response = api.get("/api/v1/accounts/admin/overview/")
        assert response.status_code == 200
        assert response.data["members"]["total"] >= 2
        assert "email" in response.data

    def test_suspending_requires_a_reason(self, api, advisor, student):
        api.force_authenticate(user=advisor)
        response = api.post(
            f"/api/v1/accounts/admin/members/{student.public_slug}/suspend/",
            {"reason": "bad"}, format="json")
        assert response.status_code == 400
        assert "reason_required" in str(response.data)

    def test_suspending_and_reinstating(self, api, advisor, student):
        api.force_authenticate(user=advisor)
        api.post(f"/api/v1/accounts/admin/members/{student.public_slug}/suspend/",
                 {"reason": "Repeated harassment in the Health space."}, format="json")
        student.refresh_from_db()
        assert student.status == User.Status.SUSPENDED

        api.post(f"/api/v1/accounts/admin/members/{student.public_slug}/reinstate/")
        student.refresh_from_db()
        assert student.status == User.Status.ACTIVE

    def test_a_suspended_member_cannot_sign_in(self, api, advisor, student):
        api.force_authenticate(user=advisor)
        api.post(f"/api/v1/accounts/admin/members/{student.public_slug}/suspend/",
                 {"reason": "Repeated harassment in the Health space."}, format="json")

        api.force_authenticate(user=None)
        response = api.post("/api/v1/accounts/token/", {
            "email": student.email, "password": "a-long-enough-password",
        }, format="json")
        assert response.status_code == 400
        assert "suspended" in str(response.data).lower()

    def test_a_steward_can_reissue_credentials(self, api, advisor, student):
        api.force_authenticate(user=advisor)
        response = api.post(
            f"/api/v1/accounts/admin/members/{student.public_slug}/reset-password/")

        assert response.status_code == 200
        assert response.data["delivered"] is True
        student.refresh_from_db()
        assert student.must_change_password is True
        assert not student.check_password("a-long-enough-password")

    def test_role_grants_are_restricted_to_stewards(self, api, student, peer):
        api.force_authenticate(user=student)
        response = api.post("/api/v1/accounts/role-grants/", {
            "user_id": str(peer.id), "role": "faculty_advisor",
        }, format="json")
        assert response.status_code == 403

    def test_a_steward_can_grant_and_revoke_a_role(self, api, advisor, student):
        api.force_authenticate(user=advisor)
        created = api.post("/api/v1/accounts/role-grants/", {
            "user_id": str(student.id), "role": "mentor",
        }, format="json")
        assert created.status_code == 201

        refreshed = User.objects.get(pk=student.pk)
        assert refreshed.has_role("mentor")

        api.delete(f"/api/v1/accounts/role-grants/{created.data['id']}/")
        assert not User.objects.get(pk=student.pk).has_role("mentor")

    def test_the_email_log_records_what_was_attempted(self, api, advisor, programme):
        register_student(email="new.student@ouk.ac.ke", full_name="New Student",
                         programme=programme)

        api.force_authenticate(user=advisor)
        response = api.get("/api/v1/accounts/admin/email-log/")
        assert response.status_code == 200
        assert response.data["count"] >= 1
        row = response.data["results"][0]
        assert set(row) >= {"to_address", "template", "status"}
