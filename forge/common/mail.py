"""
Sending mail.

Every message FORGE sends goes through `send()`. That is the point of the
module: when somebody reports that an email never arrived, there has to be one
place to look, and a row saying what was attempted and what happened.

The failure mode this exists to prevent is the silent one. A `send_mail` call
scattered through a view either raises -- failing the request that triggered it,
which is almost never the right trade -- or is wrapped in a bare except and
disappears. Neither leaves any evidence. `send()` records an EmailLog row
either way, so "did it go out?" is a question the admin answers.
"""

from __future__ import annotations

import logging
import smtplib
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger("forge.mail")


def send(
    *,
    to: str | list[str],
    subject: str,
    template: str,
    context: dict[str, Any] | None = None,
    category: str = "general",
    user=None,
    reply_to: str | None = None,
) -> bool:
    """
    Render and send one message, recording the attempt either way.

    `template` names a pair under templates/email/: `<template>.txt` is
    required and `<template>.html` is used when it exists. Text-first because
    a plain-text part is what survives a phone mail client on a bad connection,
    which is most of this platform's audience.

    Returns True when the SMTP server accepted the message. Acceptance is not
    delivery -- a message can be accepted and then filed as spam -- which is
    why the log records the recipient and the category rather than just a flag.
    """
    from .models_mail import EmailLog

    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [address for address in recipients if address]
    if not recipients:
        logger.warning("Refusing to send %s: no recipient", template)
        return False

    base_context = {
        "site_url": settings.FRONTEND_BASE_URL,
        "support_email": settings.SUPPORT_EMAIL,
        "year": timezone.now().year,
    }
    base_context.update(context or {})

    text_body = render_to_string(f"email/{template}.txt", base_context)
    try:
        html_body = render_to_string(f"email/{template}.html", base_context)
    except Exception:
        html_body = None

    entry = EmailLog.objects.create(
        to_address=recipients[0],
        subject=subject[:200],
        template=template,
        category=category,
        user=user,
        status=EmailLog.Status.PENDING,
    )

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            reply_to=[reply_to] if reply_to else None,
            connection=get_connection(fail_silently=False),
        )
        if html_body:
            message.attach_alternative(html_body, "text/html")
        message.send()
    except (smtplib.SMTPException, OSError) as error:
        # Never re-raise. A student's contribution must not fail to save
        # because the mail server is briefly unreachable.
        logger.exception("Could not send %s to %s", template, recipients[0])
        entry.status = EmailLog.Status.FAILED
        entry.error = f"{type(error).__name__}: {error}"[:500]
        entry.save(update_fields=["status", "error", "updated_at"])
        return False

    entry.status = EmailLog.Status.SENT
    entry.sent_at = timezone.now()
    entry.save(update_fields=["status", "sent_at", "updated_at"])
    logger.info("Sent %s to %s", template, recipients[0])
    return True
