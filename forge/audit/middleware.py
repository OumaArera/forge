"""
Carries request context to service functions without threading it through
every signature.

Service functions are called from viewsets, from management commands and
from Celery tasks. Passing `request` down through all of them would put an
HTTP concern into code that has nothing to do with HTTP. A context variable
keeps the audit log honest about where an action came from while leaving the
service layer callable from anywhere.
"""

from __future__ import annotations

import contextvars
from typing import Any

_request_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "forge_request_context", default={}
)


def get_request_context() -> dict[str, Any]:
    return _request_context.get()


def set_request_context(**kwargs) -> None:
    _request_context.set(kwargs)


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        # Left-most entry is the original client, when the proxy is trusted.
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_request_context(
            user=getattr(request, "user", None),
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
            path=request.path,
            method=request.method,
        )
        response = self.get_response(request)

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            try:
                user.touch_last_seen()
            except Exception:  # pragma: no cover
                pass
        set_request_context()
        return response
