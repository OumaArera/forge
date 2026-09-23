"""
Account lifecycle operations.

Everything with a rule attached lives here rather than in a serializer or a
view, so that the same rule applies whether the caller is the API, the Django
admin, a management command or a scheduled task.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import unicodedata

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from forge.audit.models import AuditEvent
from forge.audit.services import record as audit
from forge.common.exceptions import DomainRuleViolation, NotEligible

from .models import RESERVED_SLUGS, EmailVerification, User

logger = logging.getLogger("forge.accounts")


def hash_token(token: str) -> str:
    """SHA-256 of a verification token. Only the digest is ever stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def suggest_public_slug(full_name: str) -> str:
    """
    Propose a portfolio address from a member's name.

    The result is only a suggestion; the member may change it at registration.
    After that it is effectively permanent, because it is the address they
    will have put on a CV.
    """
    normalised = unicodedata.normalize("NFKD", full_name or "")
    base = slugify(normalised.encode("ascii", "ignore").decode())[:32] or "member"
    base = re.sub(r"-+", "-", base).strip("-") or "member"
    if len(base) < 3:
        base = f"{base}-forge"

    candidate, counter = base, 1
    while candidate in RESERVED_SLUGS or User.objects.filter(public_slug=candidate).exists():
        counter += 1
        suffix = f"-{counter}"
        candidate = f"{base[: 40 - len(suffix)]}{suffix}"
    return candidate


#: The alphabet a generated password is drawn from.
#:
#: Lowercase only, and without the characters people confuse: no i, l or o,
#: no 0 or 1. An earlier version mixed case and produced strings like
#: "eN4eEEJLks4W8Q", which reads fine on a screen and is miserable to retype
#: — the first person to try it dropped a character and shifted another.
#: That matters more here than it would elsewhere, because the whole design
#: assumes the password is read off a phone and typed into a laptop.
PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"

PASSWORD_GROUPS = 3
PASSWORD_GROUP_SIZE = 4


def generated_password() -> str:
    """
    A password the platform picks, to be emailed once and then replaced.

    Grouped like a product key -- `mkaa-7fud-3rop` -- because the groups give
    the eye somewhere to rest and make it obvious when a character has been
    dropped. The hyphens are part of the password; they are typed.

    Twelve characters from a 31-character alphabet is about 59 bits, which is
    far beyond reach through a login that allows five attempts before locking
    with an escalating backoff. Guessing is not the threat this defends
    against -- a leaked mailbox is -- and a password nobody can type correctly
    defends against nothing at all.
    """
    groups = [
        "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_GROUP_SIZE))
        for _ in range(PASSWORD_GROUPS)
    ]
    return "-".join(groups)


@transaction.atomic
def register_student(
    *,
    email: str,
    full_name: str,
    password: str | None = None,
    programme=None,
    school=None,
    year_of_study: int | None = None,
    recovery_email: str = "",
    public_slug: str = "",
    kind: str = User.Kind.STUDENT,
    invitation=None,
) -> tuple[User, str]:
    """
    Create an account and send its credentials to the University address.

    The member does not choose a password here, and there is no field for one
    in the API. That single decision is what makes a fake account expensive:
    with a self-chosen password, anyone who can guess the *shape* of a
    University address can open an account and use the platform without ever
    proving they can read that mailbox. Mailing the credentials means the
    mailbox is the credential.

    `password` is accepted only so that management commands and tests can pin
    one. The registration endpoint never passes it.

    Returns (user, password). The caller must not log or return the password.
    """
    email = email.lower().strip()
    domain_exempt = kind != User.Kind.STUDENT or invitation is not None
    if not domain_exempt and not User.is_university_email(email):
        raise DomainRuleViolation(
            "FORGE is open to members of the Open University of Kenya. Register "
            "with your University email address.",
            code="not_university_email",
        )
    if User.objects.filter(email=email).exists():
        raise DomainRuleViolation("An account already exists for that address.",
                                  code="email_taken")

    issued = password or generated_password()
    generated = password is None

    user = User(
        email=email,
        full_name=full_name.strip(),
        recovery_email=recovery_email.lower().strip(),
        public_slug=public_slug or suggest_public_slug(full_name),
        school=school or (programme.school if programme else None),
        programme=programme,
        year_of_study=year_of_study,
        kind=kind,
        # The address is proved by the fact that the credentials arrived at it,
        # so there is no separate verification step to sit through.
        status=User.Status.ACTIVE,
        email_verified_at=timezone.now(),
        must_change_password=generated,
    )
    user.set_password(issued)
    user.full_clean(exclude=["password"])
    user.save()

    if invitation is not None and invitation.invited_by_id:
        user.invited_by_id = invitation.invited_by_id
        user.save(update_fields=["invited_by", "updated_at"])

    send_credentials(user, issued)
    audit(AuditEvent.Action.REGISTERED, actor=user, target=user,
          metadata={"programme": str(programme) if programme else None,
                    "kind": kind, "by_invitation": invitation is not None})
    return user, issued


def send_credentials(user: User, password: str) -> bool:
    """Email a new account its sign-in details."""
    from forge.common.mail import send

    return send(
        to=user.email,
        subject="Your FORGE account is ready",
        template="credentials",
        category="credentials",
        user=user,
        context={
            "user": user,
            "password": password,
            "sign_in_url": f"{settings.FRONTEND_BASE_URL}/sign-in",
        },
    )


def send_verification_email(user: User, token: str, purpose: str) -> bool:
    """Send a verification link for whichever address the purpose concerns."""
    from forge.common.mail import send

    is_recovery = purpose == EmailVerification.Purpose.RECOVERY_EMAIL
    # A recovery link has to go to the address being claimed, not to the one
    # already on file -- otherwise it proves nothing about the new address.
    destination = user.pending_recovery_email if is_recovery else user.email
    if not destination:
        logger.error("No destination for %s verification of user %s", purpose, user.pk)
        return False

    return send(
        to=destination,
        subject=(
            "Confirm your FORGE recovery address" if is_recovery
            else "Confirm your FORGE email address"
        ),
        template="recovery_email" if is_recovery else "verify",
        category="verification",
        user=user,
        context={
            "user": user,
            "address": destination,
            "action_url": f"{settings.FRONTEND_BASE_URL}/verify?token={token}",
            "hours": settings.EMAIL_VERIFICATION_TTL_HOURS,
        },
    )


@transaction.atomic
def _already_achieved(verification, user: User) -> bool:
    """
    Did this link already do what it was for?

    A single-use token that has been used is normally an error. But the
    ordinary reasons a link is opened twice are entirely innocent: the member
    clicks it again, a mail client prefetches it, a browser restores the tab,
    or -- as here -- React's development mode runs the effect twice. Telling
    somebody "that link did not work" seconds after it worked perfectly is
    both wrong and alarming.

    So a consumed token is checked against its own goal. If the address it was
    meant to confirm is confirmed, the link succeeded and we say so. Nothing is
    re-granted: this only changes what is reported.
    """
    if verification.purpose == EmailVerification.Purpose.RECOVERY_EMAIL:
        return user.recovery_email.lower() == verification.email.lower()
    return user.email_verified_at is not None


def verify_email(token: str) -> tuple[User, bool]:
    """
    Consume a verification link.

    Returns (user, already_confirmed). `already_confirmed` is True when the
    link had already done its job -- see `_already_achieved`.
    """
    digest = hash_token(token)
    verification = (
        EmailVerification.objects.select_for_update()
        .filter(token_hash=digest)
        .order_by("-created_at")
        .first()
    )

    if verification is None:
        raise DomainRuleViolation(
            "That link does not match any confirmation we sent. Check that you "
            "copied the whole of it, including anything after the last dot.",
            code="unknown_verification",
        )

    user = verification.user

    if verification.consumed_at is not None:
        if _already_achieved(verification, user):
            return user, True
        raise DomainRuleViolation(
            "That link has already been used, and a newer one was sent after "
            "it. Use the most recent email.",
            code="superseded_verification",
        )

    if verification.expires_at <= timezone.now():
        raise DomainRuleViolation(
            f"That link expired after "
            f"{settings.EMAIL_VERIFICATION_TTL_HOURS} hours. Request a new one.",
            code="expired_verification",
        )

    if verification.attempts >= 10:
        raise DomainRuleViolation(
            "That link has been tried too many times. Request a new one.",
            code="invalid_verification",
        )

    verification.consumed_at = timezone.now()
    verification.save(update_fields=["consumed_at", "updated_at"])

    if verification.purpose == EmailVerification.Purpose.RECOVERY_EMAIL:
        user.recovery_email = verification.email
        user.pending_recovery_email = ""
        user.save(update_fields=["recovery_email", "pending_recovery_email",
                                 "updated_at"])
    else:
        user.email_verified_at = timezone.now()
        if user.status in {User.Status.PENDING, User.Status.ALUMNUS}:
            user.status = User.Status.ACTIVE
        user.save(update_fields=["email_verified_at", "status", "updated_at"])

    audit(AuditEvent.Action.EMAIL_VERIFIED, actor=user, target=user,
          metadata={"purpose": verification.purpose})
    return user, False


@transaction.atomic
def deprovision(user: User, *, reason: str = "graduated") -> User:
    """
    Move an account to alumnus status.

    This is the graduation path, and it is deliberately not a deletion. The
    student keeps their portfolio -- which is the moment it becomes most
    valuable to them -- and keeps access through their recovery address. What
    they lose is the ability to take up a project role that a current student
    could fill.

    Called by the ICT Directorate's deprovisioning feed, when one exists, or
    by a moderator, or by the annual re-verification sweep.
    """
    if not user.recovery_email:
        # Not fatal, but the member is about to lose their way back in.
        logger.warning("Deprovisioning %s with no recovery address on file", user.pk)

    user.status = User.Status.ALUMNUS
    user.kind = User.Kind.ALUMNUS if user.kind == User.Kind.STUDENT else user.kind
    user.deprovisioned_at = timezone.now()
    user.save(update_fields=["status", "kind", "deprovisioned_at", "updated_at"])
    audit(AuditEvent.Action.DEPROVISIONED, target=user, metadata={"reason": reason})
    return user


@transaction.atomic
def grant_role(*, user: User, role: str, granted_by: User, discipline_area=None,
               expires_at=None, note: str = ""):
    from .models import RoleGrant

    existing = RoleGrant.objects.filter(
        user=user, role=role, discipline_area=discipline_area, revoked_at__isnull=True
    ).first()
    if existing and existing.is_active:
        raise DomainRuleViolation("That role is already held.", code="role_held")

    grant = RoleGrant.objects.create(
        user=user, role=role, discipline_area=discipline_area,
        granted_by=granted_by, expires_at=expires_at, note=note,
    )
    audit(AuditEvent.Action.ROLE_GRANTED, actor=granted_by, target=user,
          metadata={"role": role, "expires_at": expires_at.isoformat() if expires_at else None,
                    "area": str(discipline_area) if discipline_area else None})
    return grant


@transaction.atomic
def revoke_role(*, grant, revoked_by: User, note: str = ""):
    if grant.revoked_at is not None:
        raise DomainRuleViolation("That grant has already been revoked.")
    grant.revoked_at = timezone.now()
    grant.note = (grant.note + " | " if grant.note else "") + note
    grant.save(update_fields=["revoked_at", "note", "updated_at"])
    audit(AuditEvent.Action.ROLE_REVOKED, actor=revoked_by, target=grant.user,
          metadata={"role": grant.role, "note": note})
    return grant


# ---------------------------------------------------------------------------
# Data subject rights, Data Protection Act 2019
# ---------------------------------------------------------------------------


def export_personal_data(user: User) -> dict:
    """
    Everything the platform holds about one member, in one document.

    The proposal commits to "a mechanism for a student to export or delete
    their profile on request". This is the export half. It is assembled here
    rather than in a view so that the Data Protection Officer can run it from
    a management command without going through the API.
    """
    from forge.contributions.models import Attestation, Contribution
    from forge.projects.models import Membership

    data = {
        "exported_at": timezone.now().isoformat(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "recovery_email": user.recovery_email,
            "full_name": user.full_name,
            "preferred_name": user.preferred_name,
            "public_slug": user.public_slug,
            "kind": user.kind,
            "status": user.status,
            "school": str(user.school) if user.school else None,
            "programme": str(user.programme) if user.programme else None,
            "year_of_study": user.year_of_study,
            "headline": user.headline,
            "bio": user.bio,
            "location": user.location,
            "links": user.links,
            "joined_at": user.created_at.isoformat(),
            "email_verified_at": user.email_verified_at.isoformat()
            if user.email_verified_at else None,
            "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
        },
        "skills": [
            {"skill": us.skill.name, "self_rating": us.get_self_rating_display(),
             "evidence_count": us.evidence_count}
            for us in user.skills.select_related("skill")
        ],
        "roles_held": [
            {"role": g.get_role_display(), "granted_at": g.granted_at.isoformat(),
             "expires_at": g.expires_at.isoformat() if g.expires_at else None,
             "revoked_at": g.revoked_at.isoformat() if g.revoked_at else None}
            for g in user.role_grants.all()
        ],
        "project_memberships": [
            {"project": m.project.title, "role": m.role.title if m.role else None,
             "joined_at": m.joined_at.isoformat(),
             "left_at": m.left_at.isoformat() if m.left_at else None,
             "was_lead": m.is_lead}
            for m in Membership.objects.filter(user=user).select_related("project", "role")
        ],
        "contributions": [
            {"project": c.project.title, "dimension": c.dimension,
             "description": c.description, "hours": float(c.effort_hours or 0),
             "status": c.status, "occurred_on": c.occurred_on.isoformat(),
             "ai_assistance": c.ai_assistance}
            for c in Contribution.objects.filter(contributor=user).select_related("project")
        ],
        "attestations_given": [
            {"contribution": str(a.contribution_id), "capacity": a.capacity,
             "decision": a.decision, "at": a.created_at.isoformat()}
            for a in Attestation.objects.filter(attestor=user)
        ],
        "notifications_preferences": _preference_export(user),
    }
    audit(AuditEvent.Action.DATA_EXPORTED, actor=user, target=user)
    return data


def _preference_export(user) -> dict:
    prefs = getattr(user, "notification_preference", None)
    if prefs is None:
        return {}
    return {"digest_frequency": prefs.digest_frequency,
            "categories_muted": prefs.muted_categories}


@transaction.atomic
def erase_user(user: User, *, requested_by: User, reason: str = "member request") -> User:
    """
    Erase a member's personal data while leaving the collaborative record intact.

    This is the hardest rule in the system and it is worth being explicit
    about the trade-off. A right to erasure is real, but a contribution
    ledger that could be silently rewritten by one participant would destroy
    the value of every other participant's portfolio -- their teammate's
    confirmed contributions reference the same project and the same reviews.

    So: identifying data is destroyed, the account becomes an unnamed tombstone,
    and the ledger keeps a pseudonymous reference. Nobody can recover who the
    member was from what remains, and nobody else's record is falsified.
    """
    if user.status == User.Status.CLOSED:
        raise DomainRuleViolation("That account is already closed.")

    tombstone = f"erased-{user.pk.hex[:12]}"
    user.email = f"{tombstone}@erased.invalid"
    user.recovery_email = ""
    user.full_name = "Former member"
    user.preferred_name = ""
    user.public_slug = tombstone[:40]
    user.headline = ""
    user.bio = ""
    user.location = ""
    user.links = {}
    user.oidc_subject = ""
    user.status = User.Status.CLOSED
    user.is_active = False
    user.portfolio_is_public = False
    user.set_unusable_password()
    if user.avatar:
        user.avatar.delete(save=False)
    user.save()

    user.skills.all().delete()
    user.verifications.all().delete()
    user.interests.clear()

    audit(AuditEvent.Action.DATA_ERASED, actor=requested_by, target=user,
          metadata={"reason": reason, "tombstone": tombstone})
    return user


def check_may_act(user: User) -> None:
    """Guard used by write endpoints that need a verified, unsuspended member."""
    if not user.is_verified_member:
        raise NotEligible(
            "Verify your University email address before taking part.",
            code="unverified",
        )
    if user.status == User.Status.SUSPENDED:
        raise NotEligible("Your account is suspended.", code="suspended")


# ---------------------------------------------------------------------------
# Recovery address
# ---------------------------------------------------------------------------


@transaction.atomic
def request_recovery_email(user: User, address: str) -> bool:
    """
    Start confirming a personal address.

    The address is held in `pending_recovery_email` and only promoted to
    `recovery_email` once the link is followed. Two things follow from that,
    and the earlier version of this code got both wrong:

      * The link has to be sent to the address being claimed. Sending it
        anywhere else proves nothing about the new address.
      * The interface has to be able to say "waiting on you". Storing nothing
        until confirmation meant the member submitted the form, saw no change,
        and reasonably concluded it was broken.

    Any earlier unconsumed request is invalidated, so that an address typed
    wrongly and then corrected cannot be confirmed by the first link.
    """
    address = address.lower().strip()
    if address == user.email.lower():
        raise DomainRuleViolation(
            "Use a personal address that will outlast your University account.",
            code="same_as_university_email",
        )
    if user.recovery_email and user.recovery_email.lower() == address:
        raise DomainRuleViolation("That is already your recovery address.",
                                  code="already_set")

    EmailVerification.objects.filter(
        user=user,
        purpose=EmailVerification.Purpose.RECOVERY_EMAIL,
        consumed_at__isnull=True,
    ).update(consumed_at=timezone.now())

    user.pending_recovery_email = address
    user.save(update_fields=["pending_recovery_email", "updated_at"])

    _, token = EmailVerification.issue(
        user, address, EmailVerification.Purpose.RECOVERY_EMAIL
    )
    delivered = send_verification_email(
        user, token, EmailVerification.Purpose.RECOVERY_EMAIL
    )
    if not delivered:
        logger.error("Recovery address mail to %s could not be sent", address)
    return delivered


@transaction.atomic
def cancel_recovery_email(user: User) -> None:
    EmailVerification.objects.filter(
        user=user,
        purpose=EmailVerification.Purpose.RECOVERY_EMAIL,
        consumed_at__isnull=True,
    ).update(consumed_at=timezone.now())
    user.pending_recovery_email = ""
    user.save(update_fields=["pending_recovery_email", "updated_at"])


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------


@transaction.atomic
def invite(
    *,
    email: str,
    invited_by: User,
    full_name: str = "",
    kind: str = User.Kind.STUDENT,
    role: str = "",
    discipline_area=None,
    message: str = "",
):
    """
    Invite somebody who cannot use the open route.

    Students with a University address do not need this; they register
    directly. Invitations are for staff, alumni returning to mentor, and
    external partners, whose accounts are exempt from the domain check. Each
    one therefore records who issued it.
    """
    from datetime import timedelta

    from .models import Invitation

    email = email.lower().strip()
    if User.objects.filter(email=email).exists():
        raise DomainRuleViolation("That address already has a FORGE account.",
                                  code="already_member")

    existing = Invitation.objects.filter(email=email,
                                         status=Invitation.Status.PENDING).first()
    if existing and existing.is_usable:
        raise DomainRuleViolation(
            "An invitation to that address is already open. Resend it rather than "
            "issuing a second one.",
            code="already_invited",
        )
    if existing:
        existing.status = Invitation.Status.EXPIRED
        existing.save(update_fields=["status", "updated_at"])

    token = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        email=email,
        full_name=full_name.strip(),
        kind=kind,
        role=role,
        discipline_area=discipline_area,
        message=message.strip(),
        invited_by=invited_by,
        invited_by_name=invited_by.display_name[:160],
        token_hash=hash_token(token),
        expires_at=timezone.now()
        + timedelta(days=settings.FORGE_POLICY["INVITATION_TTL_DAYS"]),
    )
    _send_invitation(invitation, token)
    audit(AuditEvent.Action.ROLE_GRANTED, actor=invited_by, target=invitation,
          metadata={"invited": email, "kind": kind, "role": role or None})
    return invitation


def _send_invitation(invitation, token: str) -> bool:
    from forge.common.mail import send

    return send(
        to=invitation.email,
        subject=f"{invitation.invited_by_name} has invited you to FORGE",
        template="invitation",
        category="invitation",
        context={
            "invitation": invitation,
            "action_url": f"{settings.FRONTEND_BASE_URL}/accept-invitation?token={token}",
            "days": settings.FORGE_POLICY["INVITATION_TTL_DAYS"],
        },
    )


@transaction.atomic
def resend_invitation(invitation, *, actor: User) -> bool:
    if not invitation.is_usable:
        raise DomainRuleViolation("That invitation is no longer open.")
    if invitation.sent_count >= 5:
        raise DomainRuleViolation(
            "That invitation has been sent five times. If it is not arriving, the "
            "address is probably wrong or the mail is being filtered -- check the "
            "email log before sending again.",
            code="resend_limit",
        )
    token = secrets.token_urlsafe(32)
    invitation.token_hash = hash_token(token)
    invitation.sent_count += 1
    invitation.last_sent_at = timezone.now()
    invitation.save(update_fields=["token_hash", "sent_count", "last_sent_at",
                                   "updated_at"])
    return _send_invitation(invitation, token)


@transaction.atomic
def revoke_invitation(invitation, *, actor: User):
    from .models import Invitation

    if invitation.status != Invitation.Status.PENDING:
        raise DomainRuleViolation("That invitation is not open.")
    invitation.status = Invitation.Status.REVOKED
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["status", "revoked_at", "updated_at"])
    return invitation


def peek_invitation(token: str):
    """
    Look up an invitation without consuming it.

    The accept screen needs to show who invited you and in what capacity
    before you fill anything in.
    """
    from .models import Invitation

    invitation = Invitation.objects.filter(token_hash=hash_token(token)).first()
    if invitation is None or not invitation.is_usable:
        raise DomainRuleViolation(
            "That invitation link is not valid. It may have expired, been used "
            "already, or been withdrawn.",
            code="invalid_invitation",
        )
    return invitation


@transaction.atomic
def accept_invitation(*, token: str, full_name: str = "", programme=None,
                      year_of_study: int | None = None, public_slug: str = ""):
    """Create the invited account and email it credentials."""
    from .models import Invitation

    invitation = Invitation.objects.select_for_update().filter(
        token_hash=hash_token(token)
    ).first()
    if invitation is None or not invitation.is_usable:
        raise DomainRuleViolation(
            "That invitation link is not valid.", code="invalid_invitation"
        )

    user, _password = register_student(
        email=invitation.email,
        full_name=full_name or invitation.full_name or invitation.email.split("@")[0],
        programme=programme,
        year_of_study=year_of_study,
        public_slug=public_slug,
        kind=invitation.kind,
        invitation=invitation,
    )

    if invitation.role:
        grant_role(user=user, role=invitation.role,
                   granted_by=invitation.invited_by or user,
                   discipline_area=invitation.discipline_area,
                   note="Granted on accepting an invitation.")

    invitation.status = Invitation.Status.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.accepted_user = user
    invitation.save(update_fields=["status", "accepted_at", "accepted_user",
                                   "updated_at"])
    return user
