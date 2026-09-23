"""
Portfolio endpoints.

The public portfolio and the verification endpoint are open to anyone. That
is the whole point of the module: a record only the University can read does
nothing for the employability argument the initiative rests on.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from forge.accounts.models import User

from .serializers import VerificationRequestSerializer
from .services import build_portfolio, issue_signed_export
from .signing import public_key_b64, verify


class PublicPortfolioView(APIView):
    """A member's public record, at a stable address that survives graduation."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    def get(self, request, slug: str):
        user = get_object_or_404(
            User.objects.select_related("school", "programme"),
            public_slug=slug, is_active=True,
        )
        if not user.portfolio_is_public:
            viewer = request.user
            if not (viewer.is_authenticated and (viewer.id == user.id
                                                 or viewer.is_superuser)):
                return Response(
                    {"error": {"code": "portfolio_private",
                               "detail": "This member has made their portfolio private."}},
                    status=404,
                )
        return Response(build_portfolio(user, for_public=True))


class MyPortfolioExportView(APIView):
    """
    Download a signed copy of your own record.

    The signature is what turns "this student says the platform confirmed
    their work" into something an employer can check for themselves against a
    key published on the University's own subdomain.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "export"

    @extend_schema(responses={200: None})
    def get(self, request):
        return Response(issue_signed_export(request.user, requested_by=request.user))


class VerificationKeyView(APIView):
    """The public key, so anybody can verify an export offline."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    def get(self, request):
        from django.conf import settings

        try:
            key = public_key_b64()
        except Exception:
            return Response({"error": {"code": "signing_unavailable",
                                       "detail": "No signing key is configured."}},
                            status=503)
        return Response({
            "algorithm": "Ed25519",
            "key_id": settings.PORTFOLIO_SIGNING_KEY_ID,
            "public_key": key,
            "encoding": "base64 of the 32 raw public key bytes",
            "signed_payload": (
                "The 'portfolio' object of an export, serialised as JSON with "
                "sorted keys, no whitespace between tokens, and UTF-8 encoding."
            ),
        })


class VerifyExportView(APIView):
    """
    Check a signed export.

    Anyone may POST an export here. The endpoint says whether the signature is
    good and, separately, whether the ledger head quoted in the document still
    matches the live chain -- which catches a genuine export that has since
    been superseded as distinct from one that was altered.
    """

    permission_classes = [AllowAny]

    @extend_schema(request=VerificationRequestSerializer, responses={200: None})
    def post(self, request):
        from forge.contributions.models import LedgerEntry

        serializer = VerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.validated_data["portfolio"]
        signature = serializer.validated_data["signature"]
        public_key = serializer.validated_data.get("public_key") or None

        signature_ok = verify(document, signature, public_key)

        # An export from someone with no confirmed contributions quotes no
        # ledger head, so there is nothing to recognise. That is reported as
        # null rather than false: false would read as "we checked and it was
        # wrong", which is a different and much more alarming statement.
        quoted_head = (document.get("ledger") or {}).get("head_hash")
        head_known = (
            LedgerEntry.objects.filter(entry_hash=quoted_head).exists()
            if quoted_head
            else None
        )

        return Response({
            "signature_valid": signature_ok,
            "ledger_head_recognised": head_known,
            "member": (document.get("member") or {}).get("display_name"),
            "contribution_count": (document.get("ledger") or {}).get("entry_count"),
            "verdict": (
                "This document was issued by FORGE and has not been altered."
                if signature_ok else
                "This document does not carry a valid FORGE signature. Do not rely on it."
            ),
            "note": (
                "A valid signature proves FORGE issued this document unchanged. It "
                "does not prove the document is current -- a member may have "
                "contributed more since it was issued."
            ),
        })
