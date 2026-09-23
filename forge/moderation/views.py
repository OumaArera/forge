from __future__ import annotations

import hashlib

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from forge.audit.models import AuditEvent
from forge.audit.services import record as audit
from forge.common.exceptions import NotEligible
from forge.common.permissions import IsModerator, IsVerifiedStudent

from .models import AcceptableUseAcceptance, ModerationAction, Report
from .serializers import AcceptanceSerializer, ModerationActionSerializer, ReportSerializer


class ReportViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                    mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                    viewsets.GenericViewSet):
    queryset = Report.objects.none()  # real filtering happens in get_queryset
    serializer_class = ReportSerializer
    filterset_fields = ["status", "reason"]

    def get_permissions(self):
        if self.action == "create":
            return [IsVerifiedStudent()]
        return [IsModerator()]

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "report"
        return super().get_throttles()

    def get_queryset(self):
        queryset = Report.objects.select_related("reporter", "assigned_to")
        user = self.request.user
        if self.action in {"list", "retrieve"} and not (user.is_superuser or
                                                        user.can_moderate):
            return queryset.filter(reporter=user)
        return queryset

    def perform_create(self, serializer):
        report = serializer.save(reporter=self.request.user)
        if report.needs_advisor:
            # Harassment, unsafe security activity, academic dishonesty and
            # privacy breaches are not for a student moderator to close. They
            # go to the faculty advisor, who has the University's own
            # disciplinary process behind them.
            report.status = Report.Status.ESCALATED
            report.save(update_fields=["status", "updated_at"])
            _alert_advisors(report)

        audit(AuditEvent.Action.CONTENT_REPORTED, actor=self.request.user,
              target=report, metadata={"reason": report.reason,
                                       "escalated": report.needs_advisor})

    @extend_schema(request=ModerationActionSerializer,
                   responses={201: ModerationActionSerializer})
    @action(detail=True, methods=["post"], url_path="act")
    def act(self, request, pk=None):
        from forge.accounts.models import User

        report = self.get_object()
        serializer = ModerationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if report.needs_advisor and not (request.user.has_role("faculty_advisor")
                                         or request.user.is_superuser):
            raise NotEligible(
                "This category is reserved for the faculty advisor. A student "
                "moderator should not be the last word on a matter that may need "
                "the University's own disciplinary process."
            )

        subject_id = serializer.validated_data.pop("subject_id", None)
        subject = User.objects.filter(pk=subject_id).first() if subject_id else None

        moderation_action = ModerationAction(report=report, moderator=request.user,
                                             subject=subject,
                                             **serializer.validated_data)
        moderation_action.full_clean()
        moderation_action.save()

        _apply_action(moderation_action)

        report.status = Report.Status.UPHELD
        report.resolved_at = timezone.now()
        report.resolution_note = moderation_action.rationale
        report.save(update_fields=["status", "resolved_at", "resolution_note",
                                   "updated_at"])

        audit(AuditEvent.Action.MODERATION_ACTION, actor=request.user,
              target=moderation_action,
              metadata={"action": moderation_action.action,
                        "subject": str(subject.pk) if subject else None})
        return Response(ModerationActionSerializer(moderation_action).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: ReportSerializer})
    @action(detail=True, methods=["post"])
    def dismiss(self, request, pk=None):
        report = self.get_object()
        note = request.data.get("note", "")
        if not note.strip():
            raise NotEligible("Say why the report is being dismissed.")
        report.status = Report.Status.DISMISSED
        report.resolved_at = timezone.now()
        report.resolution_note = note
        report.save(update_fields=["status", "resolved_at", "resolution_note",
                                   "updated_at"])
        return Response(ReportSerializer(report).data)


def _apply_action(moderation_action: ModerationAction) -> None:
    """Carry out the effect of a moderation decision, and tell the subject."""
    from forge.accounts.models import User
    from forge.community.models import Post, Thread
    from forge.notifications.services import notify

    subject = moderation_action.subject
    target = moderation_action.report.target if moderation_action.report else None

    if moderation_action.action == ModerationAction.Action.REMOVE_CONTENT:
        if isinstance(target, Post | Thread):
            target.delete(reason="removed by moderation")
    elif moderation_action.action == ModerationAction.Action.LOCK_THREAD:
        if isinstance(target, Thread):
            target.is_locked = True
            target.save(update_fields=["is_locked", "updated_at"])
    elif moderation_action.action == ModerationAction.Action.SUSPEND and subject:
        subject.status = User.Status.SUSPENDED
        subject.save(update_fields=["status", "updated_at"])

    if subject:
        # Telling somebody what was done to them and why is not a courtesy,
        # it is what makes the decision appealable.
        notify(subject, verb="moderation.action", target=moderation_action,
               summary=(f"A moderator has taken action on your account: "
                        f"{moderation_action.get_action_display()}. "
                        f"Reason: {moderation_action.rationale[:150]}"))
        ModerationAction.objects.filter(pk=moderation_action.pk).update(
            notified_subject_at=timezone.now())


def _alert_advisors(report: Report) -> None:
    from forge.accounts.models import RoleGrant, User
    from forge.notifications.services import notify

    advisors = User.objects.filter(
        role_grants__role=RoleGrant.Role.FACULTY_ADVISOR,
        role_grants__revoked_at__isnull=True,
    ).distinct()
    for advisor in advisors:
        notify(advisor, verb="moderation.action", target=report,
               summary=f"A report categorised as '{report.get_reason_display()}' "
                       f"needs the faculty advisor.")


class AcceptableUseViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                           viewsets.GenericViewSet):
    """
    Recording acceptance of the acceptable use undertaking.

    Section 14.3 of the proposal requires a written undertaking referencing the
    Computer Misuse and Cybercrimes Act, 2018 before any technical exercise.
    The digest of the exact text accepted is stored, so the record survives the
    wording being revised.
    """
    queryset = AcceptableUseAcceptance.objects.none()  # real filtering happens in get_queryset

    serializer_class = AcceptanceSerializer
    permission_classes = [IsVerifiedStudent]

    def get_queryset(self):
        return AcceptableUseAcceptance.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        text = self.request.data.get("accepted_text", "")
        if not text:
            raise NotEligible("Send the exact text being accepted so it can be recorded.")
        from forge.audit.middleware import get_request_context

        serializer.save(
            user=self.request.user,
            text_digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            ip_address=get_request_context().get("ip"),
        )
