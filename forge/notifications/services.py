"""Creating notifications and sending digests."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import VERB_CATEGORY, Category, Notification, NotificationPreference

logger = logging.getLogger("forge.notifications")


def preferences_for(user) -> NotificationPreference:
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    return prefs


def notify(recipient, *, verb: str, summary: str, target=None, actor=None,
           url: str = "") -> Notification | None:
    """
    Record one notification, and email it if the recipient wants that now.

    Never raises. A notification that cannot be created must not roll back the
    action that caused it -- a student's contribution should not fail to save
    because the mail server is down.
    """
    if recipient is None or not getattr(recipient, "is_active", False):
        return None
    if actor is not None and getattr(actor, "id", None) == recipient.id:
        return None  # nobody needs telling about their own action

    category = VERB_CATEGORY.get(verb, Category.PLATFORM)
    prefs = preferences_for(recipient)
    if not prefs.wants(category):
        return None

    fields = {"recipient": recipient, "actor": actor, "verb": verb,
              "category": category, "summary": summary[:300], "url": url[:300]}
    if target is not None:
        fields["target_type"] = ContentType.objects.get_for_model(target)
        fields["target_id"] = str(target.pk)

    try:
        notification = Notification.objects.create(**fields)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Could not create notification %s for %s", verb, recipient.pk)
        return None

    if prefs.wants_email_now(verb, category):
        transaction.on_commit(lambda: _send_single(notification))
    return notification


def notify_project_team(project, *, verb: str, summary: str, actor=None,
                        include_mentor: bool = True) -> None:
    recipients = {m.user for m in project.active_members}
    recipients.add(project.lead)
    if include_mentor and project.mentor:
        recipients.add(project.mentor)
    for recipient in recipients:
        notify(recipient, verb=verb, summary=summary, target=project, actor=actor)


def _send_single(notification: Notification) -> None:
    try:
        body = render_to_string("notifications/email/single.txt", {
            "notification": notification,
            "base_url": settings.PUBLIC_BASE_URL,
        })
        send_mail("FORGE: " + notification.summary[:120], body,
                  settings.DEFAULT_FROM_EMAIL, [_address_for(notification.recipient)])
        Notification.objects.filter(pk=notification.pk).update(emailed_at=timezone.now())
    except Exception:  # pragma: no cover
        logger.exception("Could not email notification %s", notification.pk)


def _address_for(user) -> str:
    """
    Where to reach somebody.

    An alumnus's University address has stopped working, so mail goes to the
    recovery address. This is the practical half of the durability promise:
    a portfolio they cannot be told about is a portfolio they will forget.
    """
    from forge.accounts.models import User

    if user.status == User.Status.ALUMNUS and user.recovery_email:
        return user.recovery_email
    return user.email


def send_digest(user, *, frequency: str) -> int:
    """Send one member their pending notifications. Returns how many were included."""
    prefs = preferences_for(user)
    if prefs.digest_frequency != frequency:
        return 0

    pending = list(
        Notification.objects.filter(
            recipient=user, read_at__isnull=True,
            emailed_at__isnull=True, included_in_digest_at__isnull=True,
        ).order_by("category", "-created_at")[:50]
    )
    if not pending:
        return 0

    grouped: dict[str, list[Notification]] = {}
    for item in pending:
        grouped.setdefault(item.get_category_display(), []).append(item)

    try:
        body = render_to_string("notifications/email/digest.txt", {
            "user": user, "grouped": grouped, "count": len(pending),
            "base_url": settings.PUBLIC_BASE_URL,
        })
        send_mail(f"FORGE: {len(pending)} update{'s' if len(pending) != 1 else ''} for you",
                  body, settings.DEFAULT_FROM_EMAIL, [_address_for(user)])
    except Exception:  # pragma: no cover
        logger.exception("Could not send digest to %s", user.pk)
        return 0

    Notification.objects.filter(pk__in=[n.pk for n in pending]).update(
        included_in_digest_at=timezone.now()
    )
    return len(pending)
