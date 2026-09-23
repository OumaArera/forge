from __future__ import annotations

from rest_framework import serializers

from forge.accounts.serializers import (
    DisciplineAreaSerializer,
    PublicUserSerializer,
    SkillSerializer,
)

from .models import MentorProfile, MentorshipRequest, OfficeHour, OfficeHourBooking


class MentorProfileSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    expertise = SkillSerializer(many=True, read_only=True)
    discipline_areas = DisciplineAreaSerializer(many=True, read_only=True)
    current_load = serializers.IntegerField(read_only=True)
    has_capacity = serializers.BooleanField(read_only=True)

    class Meta:
        model = MentorProfile
        fields = ["id", "user", "headline", "about", "expertise", "discipline_areas",
                  "capacity", "current_load", "has_capacity", "availability",
                  "hours_per_month", "is_alumnus", "organisation"]
        read_only_fields = ["user", "current_load", "has_capacity"]


class MentorshipRequestSerializer(serializers.ModelSerializer):
    requester = PublicUserSerializer(read_only=True)
    mentor = PublicUserSerializer(read_only=True)
    mentor_id = serializers.UUIDField(write_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True,
                                          default=None)

    class Meta:
        model = MentorshipRequest
        fields = ["id", "requester", "mentor", "mentor_id", "project", "project_title",
                  "message", "status", "response", "responded_at", "expires_at",
                  "created_at"]
        read_only_fields = ["requester", "mentor", "status", "response", "responded_at"]


class RespondToRequestSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
    response = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class OfficeHourSerializer(serializers.ModelSerializer):
    mentor = PublicUserSerializer(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    booking_count = serializers.SerializerMethodField()

    class Meta:
        model = OfficeHour
        fields = ["id", "mentor", "starts_at", "duration_minutes", "capacity",
                  "topic", "is_cancelled", "is_full", "booking_count"]
        read_only_fields = ["mentor"]

    def get_booking_count(self, obj) -> int:
        return obj.bookings.filter(cancelled_at__isnull=True).count()


class OfficeHourBookingSerializer(serializers.ModelSerializer):
    attendee = PublicUserSerializer(read_only=True)
    joining_url = serializers.SerializerMethodField()

    class Meta:
        model = OfficeHourBooking
        fields = ["id", "office_hour", "attendee", "question", "joining_url",
                  "cancelled_at", "attended"]
        read_only_fields = ["attendee", "attended"]

    def get_joining_url(self, obj) -> str:
        # Only the attendee and the mentor see the link.
        user = self.context["request"].user
        if user.id in {obj.attendee_id, obj.office_hour.mentor_id}:
            return obj.office_hour.joining_url
        return ""
