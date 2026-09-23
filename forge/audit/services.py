"""Writing to the audit log."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType

from .middleware import get_request_context
from .models import AuditEvent

logger = logging.getLogger("forge.audit")

# Keys that must never reach the audit log, whatever a caller passes.
_FORBIDDEN_METADATA_KEYS = {
    "password", "password1", "password2", "token", "secret", "authorization",
    "access", "refresh", "token_hash", "signing_key", "api_key",
}


def scrub(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    clean = {}
    for key, value in metadata.items():
        if key.lower() in _FORBIDDEN_METADATA_KEYS:
            clean[key] = "[redacted]"
        elif isinstance(value, dict):
            clean[key] = scrub(value)
        else:
            clean[key] = value
    return clean


def record(
    action: str,
    *,
    actor=None,
    target=None,
    target_label: str = "",
    metadata: dict[str, Any] | None = None,
) -> AuditEvent | None:
    """
    Append one event to the audit log.

    Failure to write an audit row must never fail the action being audited --
    a student should not be unable to submit a contribution because the log
    is briefly unavailable. The failure is logged loudly instead.
    """
    context = get_request_context()
    if actor is None:
        actor = context.get("user")

    fields: dict[str, Any] = {
        "action": action,
        "metadata": scrub(metadata),
        "ip_address": context.get("ip"),
        "user_agent": (context.get("user_agent") or "")[:300],
    }
    if actor is not None and getattr(actor, "is_authenticated", False):
        fields["actor"] = actor
        fields["actor_label"] = f"{actor.display_name} <{actor.email}>"[:200]
    if target is not None:
        fields["target_type"] = ContentType.objects.get_for_model(target)
        fields["target_id"] = str(target.pk)
        fields["target_label"] = (target_label or str(target))[:255]

    try:
        return AuditEvent.objects.create(**fields)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Could not write audit event %s", action)
        return None
