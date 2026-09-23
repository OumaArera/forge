"""
The audit log.

The concept proposal lists "audit logging" among the controls against a data
breach. This is that log. It is append-only (see ImmutableModel) and it is
written by explicit calls from service functions rather than by a signal on
every model save, because a log that records everything records nothing
useful: a reader drowning in `User.save` rows will not notice the one line
that says a moderator removed a post.

What gets logged: authentication events, role grants and revocations,
lifecycle transitions on a project, attestations, moderation actions, data
exports and erasures. What does not: ordinary reads, and ordinary edits to a
member's own profile.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from forge.common.models import ImmutableModel, UUIDModel


class AuditEvent(UUIDModel, ImmutableModel):
    class Action(models.TextChoices):
        # Identity
        REGISTERED = "user.registered", "Member registered"
        EMAIL_VERIFIED = "user.email_verified", "Email verified"
        SIGNED_IN = "user.signed_in", "Signed in"
        SIGN_IN_FAILED = "user.sign_in_failed", "Sign-in failed"
        PASSWORD_CHANGED = "user.password_changed", "Password changed"
        DEPROVISIONED = "user.deprovisioned", "Account deprovisioned"
        DATA_EXPORTED = "user.data_exported", "Personal data exported"
        DATA_ERASED = "user.data_erased", "Personal data erased"
        # Authority
        ROLE_GRANTED = "role.granted", "Role granted"
        ROLE_REVOKED = "role.revoked", "Role revoked"
        # Work
        PROJECT_TRANSITIONED = "project.transitioned", "Project changed stage"
        PROJECT_REVIEWED = "project.reviewed", "Proposal reviewed"
        MEMBER_JOINED = "project.member_joined", "Member joined a project"
        MEMBER_LEFT = "project.member_left", "Member left a project"
        # Evidence
        CONTRIBUTION_SUBMITTED = "contribution.submitted", "Contribution submitted"
        CONTRIBUTION_ATTESTED = "contribution.attested", "Contribution attested"
        CONTRIBUTION_DISPUTED = "contribution.disputed", "Contribution disputed"
        LEDGER_APPENDED = "ledger.appended", "Ledger entry appended"
        CERTIFICATE_ISSUED = "certificate.issued", "Certificate issued"
        CERTIFICATE_REVOKED = "certificate.revoked", "Certificate revoked"
        # Conduct
        CONTENT_REPORTED = "moderation.reported", "Content reported"
        MODERATION_ACTION = "moderation.action", "Moderation action taken"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_events",
        help_text="Null where the platform itself acted, for example a scheduled task.",
    )
    actor_label = models.CharField(
        max_length=200, blank=True,
        help_text="The actor's name as it stood at the time. Kept so that the log "
                  "stays readable after an account is erased.",
    )
    action = models.CharField(max_length=48, choices=Action.choices, db_index=True)

    target_type = models.ForeignKey(ContentType, null=True, blank=True,
                                    on_delete=models.SET_NULL)
    target_id = models.CharField(max_length=64, blank=True)
    target = GenericForeignKey("target_type", "target_id")
    target_label = models.CharField(max_length=255, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["action", "occurred_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]
        verbose_name = "audit event"

    def __str__(self) -> str:
        return f"{self.occurred_at:%Y-%m-%d %H:%M} {self.action} by {self.actor_label or 'system'}"
