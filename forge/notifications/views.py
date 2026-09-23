from __future__ import annotations

from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Announcement, Notification
from .serializers import (
    AnnouncementSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
)
from .services import preferences_for


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Notification.objects.none()  # real filtering happens in get_queryset
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["category", "verb"]

    def get_queryset(self):
        queryset = Notification.objects.filter(
            recipient=self.request.user).select_related("actor")
        if self.request.query_params.get("unread") == "true":
            queryset = queryset.filter(read_at__isnull=True)
        return queryset

    @extend_schema(responses={200: None})
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        counts = {}
        queryset = Notification.objects.filter(recipient=request.user,
                                               read_at__isnull=True)
        for row in queryset.values("category").annotate(n=Count("id")):
            counts[row["category"]] = row["n"]
        return Response({"total": queryset.count(), "by_category": counts})

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_queryset().filter(pk=pk).first()
        if notification:
            notification.mark_read()
        return Response({"detail": "Marked as read."})

    @extend_schema(request=None, responses={200: None})
    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(
            read_at=timezone.now())
        return Response({"marked": updated})


class NotificationPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: NotificationPreferenceSerializer})
    def get(self, request):
        return Response(NotificationPreferenceSerializer(
            preferences_for(request.user)).data)

    @extend_schema(request=NotificationPreferenceSerializer,
                   responses={200: NotificationPreferenceSerializer})
    def patch(self, request):
        serializer = NotificationPreferenceSerializer(
            preferences_for(request.user), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AnnouncementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Announcement.objects.none()  # real filtering happens in get_queryset
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        now = timezone.now()
        return Announcement.objects.filter(
            is_published=True, published_at__lte=now
        ).exclude(expires_at__lt=now).select_related("author")
