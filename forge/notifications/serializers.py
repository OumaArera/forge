from __future__ import annotations

from rest_framework import serializers

from forge.accounts.serializers import PublicUserSerializer

from .models import Announcement, Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    actor = PublicUserSerializer(read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "verb", "category", "category_display", "summary", "actor",
                  "url", "is_read", "read_at", "created_at"]
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ["digest_frequency", "muted_categories", "quiet_hours_start",
                  "quiet_hours_end"]


class AnnouncementSerializer(serializers.ModelSerializer):
    author = PublicUserSerializer(read_only=True)

    class Meta:
        model = Announcement
        fields = ["id", "title", "body", "author", "published_at", "expires_at"]
        read_only_fields = fields
