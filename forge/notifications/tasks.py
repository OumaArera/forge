"""Scheduled notification work."""

from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from .models import Notification, NotificationPreference
from .services import send_digest


@shared_task
def send_daily_digests() -> int:
    return _send_for(NotificationPreference.Digest.DAILY)


@shared_task
def send_weekly_digests() -> int:
    return _send_for(NotificationPreference.Digest.WEEKLY)


def _send_for(frequency: str) -> int:
    sent = 0
    queryset = (NotificationPreference.objects
                .filter(digest_frequency=frequency, user__is_active=True)
                .select_related("user"))
    for preference in queryset.iterator(chunk_size=200):
        if send_digest(preference.user, frequency=frequency):
            sent += 1
    return sent


@shared_task
def prune_old_notifications(days: int = 180) -> int:
    """
    Delete read notifications older than six months.

    Notifications are transient by nature. Keeping them forever grows the
    busiest table in the database for no benefit -- the audit log is where the
    durable record of what happened lives.
    """
    cutoff = timezone.now() - timezone.timedelta(days=days)
    deleted, _ = Notification.objects.filter(
        read_at__isnull=False, created_at__lt=cutoff).delete()
    return deleted
