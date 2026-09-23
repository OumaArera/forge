"""
Conduct: reports and moderation actions.

The proposal commits to a published code of conduct, active moderation by
community leads, a clear reporting route to the faculty advisor for anything
serious, and defined sanctions. This module is the machinery for that.

Two things are deliberate. First, every action requires a written rationale,
because a moderation decision nobody has to explain is a decision that will
eventually be made badly. Second, the serious categories -- harassment, and
anything touching the Computer Misuse and Cybercrimes Act -- are routed to
the faculty advisor rather than handled by a student moderator, because a
student should not be the last line on a matter that may need the University's
own disciplinary process.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from forge.common.fields import validate_no_html
from forge.common.models import BaseModel


class Report(BaseModel):
    class Reason(models.TextChoices):
        HARASSMENT = "harassment", "Harassment or abuse"
        ACADEMIC_DISHONESTY = "academic_dishonesty", "Academic dishonesty"
        MISATTRIBUTION = "misattribution", "Passing off another's work as one's own"
        UNSAFE_SECURITY = "unsafe_security", "Unsafe or unlawful security activity"
        SPAM = "spam", "Spam or advertising"
        OFF_TOPIC = "off_topic", "Off topic or low quality"
        PRIVACY = "privacy", "Personal data shared without consent"
        OTHER = "other", "Something else"

    # Reasons a student community lead must not close on their own.
    ESCALATE_TO_ADVISOR = {
        Reason.HARASSMENT, Reason.UNSAFE_SECURITY, Reason.ACADEMIC_DISHONESTY,
        Reason.PRIVACY,
    }

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        TRIAGED = "triaged", "Triaged"
        ESCALATED = "escalated", "Escalated to the faculty advisor"
        UPHELD = "upheld", "Upheld"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                 on_delete=models.SET_NULL, related_name="reports_made")
    target_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.CharField(max_length=64)
    target = GenericForeignKey("target_type", "target_id")
    target_label = models.CharField(max_length=255, blank=True)

    reason = models.CharField(max_length=24, choices=Reason.choices)
    detail = models.TextField(max_length=2000, validators=[validate_no_html])
    status = models.CharField(max_length=12, choices=Status.choices,
                              default=Status.OPEN, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="reports_assigned")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True, max_length=2000,
                                       validators=[validate_no_html])

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"]),
                   models.Index(fields=["target_type", "target_id"])]

    def __str__(self) -> str:
        return f"{self.get_reason_display()} ({self.get_status_display()})"

    @property
    def needs_advisor(self) -> bool:
        return self.reason in self.ESCALATE_TO_ADVISOR


class ModerationAction(BaseModel):
    class Action(models.TextChoices):
        NOTE = "note", "Note on file, no action"
        WARN = "warn", "Warning issued"
        REMOVE_CONTENT = "remove_content", "Content removed"
        LOCK_THREAD = "lock_thread", "Thread locked"
        SUSPEND = "suspend", "Member suspended"
        REMOVE_FROM_PROJECT = "remove_from_project", "Removed from a project"
        REFER_TO_UNIVERSITY = "refer_to_university", "Referred to the University"

    report = models.ForeignKey(Report, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="actions")
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                  on_delete=models.SET_NULL, related_name="moderation_actions")
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="moderation_received")
    action = models.CharField(max_length=24, choices=Action.choices)
    rationale = models.TextField(
        max_length=2000, validators=[validate_no_html],
        help_text="Required. Every moderation decision on FORGE is explainable, "
                  "including to the person it was taken against.",
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="For a time-limited suspension. An indefinite suspension needs "
                  "the faculty advisor.",
    )
    notified_subject_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_action_display()} by {self.moderator or 'system'}"

    def clean(self):
        super().clean()
        if not self.rationale.strip():
            raise ValidationError({"rationale": "Give a rationale."})
        if self.action == self.Action.SUSPEND and not self.expires_at:
            if not (self.moderator and self.moderator.has_role("faculty_advisor")):
                raise ValidationError({
                    "expires_at": "An indefinite suspension may only be applied by "
                                  "the faculty advisor. Set an end date."
                })


class AcceptableUseAcceptance(BaseModel):
    """
    A signed undertaking, recorded per version.

    Section 14.3 requires participants to accept a written acceptable use
    undertaking referencing the Computer Misuse and Cybercrimes Act, 2018
    before taking part in any technical exercise. The record has to survive
    the text changing, so the version and a digest of what was accepted are
    both stored.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="acceptances")
    document = models.CharField(max_length=40, default="acceptable_use")
    version = models.CharField(max_length=16)
    text_digest = models.CharField(max_length=64,
                                   help_text="SHA-256 of the exact text accepted.")
    accepted_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-accepted_at"]
        constraints = [models.UniqueConstraint(fields=["user", "document", "version"],
                                               name="uniq_acceptance")]

    def __str__(self) -> str:
        return f"{self.user.display_name} accepted {self.document} v{self.version}"
