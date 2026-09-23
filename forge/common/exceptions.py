"""A single, predictable error shape for the whole API."""

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .models import ImmutableRecordError

logger = logging.getLogger("forge.api")


class ForgeError(Exception):
    """Base class for domain rules that a caller has broken."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "forge_error"
    default_detail = "The request could not be completed."

    def __init__(self, detail: str | None = None, *, code: str | None = None):
        self.detail = detail or self.default_detail
        if code:
            self.code = code
        super().__init__(self.detail)


class DomainRuleViolation(ForgeError):
    code = "rule_violation"


class IllegalTransition(ForgeError):
    code = "illegal_transition"
    default_detail = "That is not a permitted change of state."


class NotEligible(ForgeError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "not_eligible"
    default_detail = "You are not eligible to perform this action."


def forge_exception_handler(exc, context):
    """
    Translate exceptions into one consistent body:

        {"error": {"code": "...", "detail": ..., "field_errors": {...}}}

    A frontend that can rely on a single shape is a frontend that spends its
    time on the interface rather than on error parsing.
    """
    if isinstance(exc, ImmutableRecordError):
        exc = DomainRuleViolation(str(exc), code="append_only")
    if isinstance(exc, DjangoValidationError):
        detail = getattr(exc, "message_dict", None) or list(exc.messages)
        return _body("validation_error", detail, status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, PermissionDenied):
        return _body("permission_denied", str(exc) or "Permission denied.", 403)
    if isinstance(exc, Http404):
        return _body("not_found", "Not found.", 404)
    if isinstance(exc, ForgeError):
        return _body(exc.code, exc.detail, exc.status_code)

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled exception in %s", context.get("view"))
        return _body("server_error", "An unexpected error occurred.", 500)

    detail = response.data
    code = "error"
    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        code = getattr(detail["detail"], "code", "error")
        detail = str(detail["detail"])
    response.data = {"error": {"code": code, "detail": detail}}
    return response


def _body(code: str, detail, http_status: int) -> Response:
    return Response({"error": {"code": code, "detail": detail}}, status=http_status)
