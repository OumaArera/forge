"""
Notifications, with digests.

The design constraint is stated plainly in the concept proposal: most members
are studying at a distance, many are in employment, and interaction outside
scheduled sessions collapses into messaging groups. A platform that emails
somebody eleven times a day will be muted within a week and will then be
unable to reach them about the one thing that mattered.

So: everything is written in-app, and email is opt-in per category with a
daily or weekly digest as the default. The only categories that send
immediately are the ones where a delay costs somebody something real -- your
application was decided, your contribution was confirmed or disputed, a
moderator has acted on your account.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from forge.common.models import BaseModel


class Category(models.TextChoices):
    PROJECT = "project", "Your projects"
    APPLICATION = "application", "Applications and team formation"
    CONTRIBUTION = "contribution", "Contributions and confirmations"
    COMMUNITY = "community", "Discussions you follow"
    MENTORSHIP = "mentorship", "Mentorship"
    RECOGNITION = "recognition", "Levels, badges and certificates"
    MODERATION = "moderation", "Conduct and moderation"
    PLATFORM = "platform", "Platform announcements"


# Verbs that go out immediately regardless of digest preference, because a
# delay has a cost for the recipient.
IMMEDIATE_VERBS = {
    "application.decided",
    "contribution.confirmed",
    "contribution.disputed",
    "project.reviewed",
    "moderation.action",
    "mentorship.accepted",
    "account.security",
}

VERB_CATEGORY = {
    "project.stage_changed": Category.PROJECT,
    "project.reviewed": Category.PROJECT,
    "project.lead_changed": Category.PROJECT,
    "project.stale": Category.PROJECT,
    "application.received": Category.APPLICATION,
    "application.decided": Category.APPLICATION,
    "contribution.awaiting_attestation": Category.CONTRIBUTION,
    "contribution.confirmed": Category.CONTRIBUTION,
    "contribution.disputed": Category.CONTRIBUTION,
    "community.reply": Category.COMMUNITY,
    "community.answer_accepted": Category.COMMUNITY,
    "mentorship.requested": Category.MENTORSHIP,
    "mentorship.accepted": Category.MENTORSHIP,
    "recognition.level": Category.RECOGNITION,
    "recognition.badge": Category.RECOGNITION,
    "recognition.certificate": Category.RECOGNITION,
    "moderation.action": Category.MODERATION,
    "platform.announcement": Category.PLATFORM,
}


class Notification(BaseModel):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="notifications_caused")
    verb = models.CharField(max_length=48, db_index=True)
    category = models.CharField(max_length=16, choices=Category.choices,
                                default=Category.PLATFORM, db_index=True)
    summary = models.CharField(max_length=300)

    target_type = models.ForeignKey(ContentType, null=True, blank=True,
                                    on_delete=models.SET_NULL)
    target_id = models.CharField(max_length=64, blank=True)
    target = GenericForeignKey("target_type", "target_id")
    url = models.CharField(max_length=300, blank=True)

    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    included_in_digest_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at", "-created_at"]),
            models.Index(fields=["recipient", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.recipient.display_name}: {self.summary[:60]}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self) -> None:
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at", "updated_at"])


class NotificationPreference(BaseModel):
    class Digest(models.TextChoices):
        IMMEDIATE = "immediate", "Email me as things happen"
        DAILY = "daily", "One email a day"
        WEEKLY = "weekly", "One email a week"
        OFF = "off", "No email -- I will check the site"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="notification_preference")
    digest_frequency = models.CharField(max_length=10, choices=Digest.choices,
                                        default=Digest.DAILY)
    muted_categories = models.JSONField(default=list, blank=True)
    quiet_hours_start = models.TimeField(null=True, blank=True, default=None)
    quiet_hours_end = models.TimeField(null=True, blank=True, default=None)

    def __str__(self) -> str:
        return f"{self.user.display_name}: {self.get_digest_frequency_display()}"

    def wants(self, category: str) -> bool:
        return category not in (self.muted_categories or [])

    def wants_email_now(self, verb: str, category: str) -> bool:
        if not self.wants(category):
            return False
        if verb in IMMEDIATE_VERBS:
            return self.digest_frequency != self.Digest.OFF
        return self.digest_frequency == self.Digest.IMMEDIATE


class Announcement(BaseModel):
    """A platform-wide message from the stewards. Rare by design."""

    title = models.CharField(max_length=160)
    body = models.TextField(max_length=4000)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                               on_delete=models.SET_NULL, related_name="announcements")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    send_email = models.BooleanField(default=False)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self) -> str:
        return self.title
