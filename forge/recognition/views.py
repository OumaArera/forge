from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from forge.common.exceptions import NotEligible
from forge.common.throttling import client_address

from .models import Badge, Certificate, LeaderboardSnapshot, Level, Standing
from .serializers import (
    BadgeSerializer,
    CertificateSerializer,
    LeaderboardSerializer,
    LevelSerializer,
    StandingSerializer,
)


class LevelViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """The ladder, published. Nobody should have to guess how to advance."""

    queryset = Level.objects.all()
    serializer_class = LevelSerializer
    permission_classes = [AllowAny]


class BadgeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Badge.objects.filter(is_active=True)
    serializer_class = BadgeSerializer
    permission_classes = [AllowAny]


class StandingViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Standing.objects.none()  # real filtering happens in get_queryset
    serializer_class = StandingSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "user__public_slug"
    lookup_url_kwarg = "slug"

    def get_queryset(self):
        return Standing.objects.select_related("user", "level")

    @extend_schema(responses={200: StandingSerializer})
    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        standing, _ = Standing.objects.get_or_create(user=request.user)
        return Response(StandingSerializer(standing).data)


class LeaderboardViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Frozen boards, by scope and period.

    There is no global all-members ranking here and that is deliberate: the
    purpose is to make good work visible within a community, not to produce a
    single number saying who the best student is.
    """
    queryset = LeaderboardSnapshot.objects.none()  # real filtering happens in get_queryset

    serializer_class = LeaderboardSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["scope", "period", "discipline_area"]

    def get_queryset(self):
        return (LeaderboardSnapshot.objects.select_related("discipline_area")
                .order_by("-period_end"))


class CertificateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):
    queryset = Certificate.objects.none()  # real filtering happens in get_queryset
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (Certificate.objects.filter(user=self.request.user)
                .select_related("project").prefetch_related("downloads"))


class CertificatePDFView(APIView):
    """
    Download a certificate as a PDF.

    Restricted to the holder and to stewards. An earlier version let anybody
    holding the code fetch the file, on the reasoning that a certificate only
    its owner can download is no use to the employer it was sent to. That is
    true, and it is still the wrong trade: the code travels on the document,
    so anybody who was ever shown one could pull a fresh, clean copy and pass
    it on as their own. An employer does not need to download anything — they
    verify the code, which stays open to everyone.

    Every download is recorded, and each copy is stamped with the moment it
    was taken and who took it. A copy that leaks traces back to one download.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "pdf"

    @extend_schema(responses={(200, "application/pdf"): OpenApiTypes.BINARY})
    def get(self, request, code: str):
        from forge.recognition.models import CertificateDownload
        from forge.recognition.pdf import render_certificate

        certificate = get_object_or_404(
            Certificate.objects.select_related("user", "project"),
            verification_code__iexact=code.strip(),
        )

        is_holder = certificate.user_id == request.user.id
        is_steward = request.user.is_superuser or bool(
            {"faculty_advisor", "platform_maintainer"} & set(request.user.role_names)
        )
        if not (is_holder or is_steward):
            raise NotEligible(
                "A certificate can only be downloaded by the person it was issued "
                "to. Anyone can check that it is genuine using its verification "
                "code, which needs no account.",
                code="not_the_holder",
            )

        record = CertificateDownload.objects.create(
            certificate=certificate,
            downloaded_by=request.user,
            downloaded_by_name=request.user.display_name[:160],
            was_holder=is_holder,
            ip_address=client_address(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )

        pdf = render_certificate(
            certificate,
            issued_to=request.user.display_name,
            issued_at=record.downloaded_at,
        )
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="forge-certificate-{certificate.verification_code}.pdf"'
        )
        response["X-Content-Type-Options"] = "nosniff"
        # Each copy is individually stamped, so a cached one would carry
        # somebody else's stamp.
        response["Cache-Control"] = "private, no-store"
        return response


class CertificateVerificationView(APIView):
    """
    Check a certificate by its code. No account needed.

    This endpoint is the difference between a certificate and a picture of
    one. An employer with the code can confirm, in one request, that FORGE
    issued it, to whom, when, and that it has not been revoked.
    """

    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    def get(self, request, code: str):
        certificate = Certificate.objects.filter(
            verification_code__iexact=code.strip()
        ).select_related("user", "project").first()

        if certificate is None:
            return Response({"valid": False,
                             "detail": "No certificate exists with that code."},
                            status=404)
        return Response({
            "valid": certificate.is_valid,
            "recipient_name": certificate.recipient_name,
            "kind": certificate.get_kind_display(),
            "project": certificate.project.title if certificate.project else None,
            "statement": certificate.statement,
            "issued_at": certificate.issued_at.isoformat(),
            "revoked_at": (certificate.revoked_at.isoformat()
                           if certificate.revoked_at else None),
            "revoked_reason": certificate.revoked_reason or None,
            "ledger_head_at_issue": certificate.ledger_head or None,
            "issuer": "FORGE, a student initiative of The Open University of Kenya",
            # How many copies the holder has taken, and when the last one was.
            # Not who took them -- that is the holder's business. It is here
            # because a certificate presented on paper that has never been
            # downloaded is worth a second look.
            "download_count": certificate.download_count,
            "last_downloaded_at": (
                certificate.last_downloaded_at.isoformat()
                if certificate.last_downloaded_at else None
            ),
            "downloadable_by": (
                "The person it was issued to. Anyone else verifies it here instead."
            ),
            "note": ("FORGE carries no academic credit and is not a qualification "
                     "of the University."),
        })
