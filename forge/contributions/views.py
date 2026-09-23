"""Contribution endpoints: claim, confirm, settle, verify."""

from __future__ import annotations

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from forge.common.exceptions import NotEligible
from forge.common.permissions import IsVerifiedStudent

from .models import Contribution, LedgerEntry
from .serializers import (
    AttestRequestSerializer,
    ContributionSerializer,
    LedgerEntrySerializer,
)
from .services import attest, capacity_for, submit, verify_chain, withdraw


class ContributionViewSet(viewsets.ModelViewSet):
    queryset = Contribution.objects.none()  # real filtering happens in get_queryset
    serializer_class = ContributionSerializer
    permission_classes = [IsVerifiedStudent]
    filterset_fields = ["project", "dimension", "status"]
    ordering_fields = ["occurred_on", "created_at"]

    def get_queryset(self):
        user = self.request.user
        # Your own claims, plus claims on projects where you lead or mentor --
        # which are the ones you may be asked to confirm.
        return (
            Contribution.objects.filter(
                Q(contributor=user) | Q(project__lead=user) | Q(project__mentor=user)
            )
            .select_related("project", "contributor")
            .prefetch_related("attestations", "skills_used")
            .distinct()
        )

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not (project.is_member(self.request.user)
                or project.lead_id == self.request.user.id):
            raise NotEligible("Log contributions against a project you are a member of.")
        serializer.save(contributor=self.request.user)

    def perform_update(self, serializer):
        if not serializer.instance.is_editable:
            raise NotEligible(
                "A submitted contribution cannot be edited. Withdraw it and log a "
                "new one, or ask your lead to dispute it so you can correct it."
            )
        if serializer.instance.contributor_id != self.request.user.id:
            raise NotEligible("That is not your contribution.")
        serializer.save()

    @extend_schema(request=None, responses={200: ContributionSerializer})
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Send a claim to the lead and mentor for confirmation."""
        contribution = submit(self.get_object(), actor=request.user)
        return Response(ContributionSerializer(contribution).data)

    @extend_schema(request=AttestRequestSerializer, responses={201: None})
    @action(detail=True, methods=["post"])
    def attest(self, request, pk=None):
        """
        Confirm or dispute someone else's claim.

        Two independent confirmations -- the lead's and the mentor's -- settle
        a contribution into the ledger. You cannot confirm your own.
        """
        serializer = AttestRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contribution = self.get_object()
        attestation = attest(contribution, attestor=request.user,
                             confirm=serializer.validated_data["confirm"],
                             note=serializer.validated_data.get("note", ""))
        contribution.refresh_from_db()
        return Response(
            {"attestation": {"capacity": attestation.capacity,
                             "decision": attestation.decision},
             "contribution": ContributionSerializer(contribution).data},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: ContributionSerializer})
    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        contribution = withdraw(self.get_object(), actor=request.user)
        return Response(ContributionSerializer(contribution).data)

    @extend_schema(responses={200: ContributionSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="awaiting-my-attestation")
    def awaiting(self, request):
        """
        Claims waiting on the caller.

        Confirmations are the bottleneck in a scheme like this: a lead who is
        three weeks behind is a team whose portfolios are all empty. Making
        this queue easy to find is most of the fix.
        """
        queryset = (
            Contribution.objects.filter(
                Q(project__lead=request.user) | Q(project__mentor=request.user),
                status__in=[Contribution.Status.SUBMITTED, Contribution.Status.DISPUTED],
            )
            .exclude(contributor=request.user)
            .select_related("project", "contributor")
            .prefetch_related("attestations")
            .order_by("submitted_at")
            .distinct()
        )
        pending = [
            c for c in queryset
            if (cap := capacity_for(request.user, c.project, c))
            and not c.attestations.filter(capacity=cap).exists()
        ]
        page = self.paginate_queryset(pending)
        return self.get_paginated_response(
            ContributionSerializer(page, many=True).data)


class LedgerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    viewsets.GenericViewSet):
    """
    The public record.

    Readable without an account on purpose. A verifiable ledger that only
    members can read is not verifiable by the people it needs to convince.
    """

    serializer_class = LedgerEntrySerializer
    permission_classes = [AllowAny]
    lookup_field = "sequence"
    filterset_fields = ["dimension", "project"]

    def get_queryset(self):
        return LedgerEntry.objects.select_related("contributor", "project")


class LedgerVerificationView(APIView):
    """
    Walk the chain and report.

    Anyone may call this. The point of a tamper-evident record is that nobody
    has to take the platform's word for it -- including the University's own
    Advisory Committee, which should run this at every gate.
    """

    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    def get(self, request):
        start = int(request.query_params.get("from", 1) or 1)
        limit = request.query_params.get("limit")
        report = verify_chain(start=start, limit=int(limit) if limit else None)
        return Response(report, status=200 if report["intact"] else 409)
