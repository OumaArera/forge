from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from forge.accounts.serializers import PublicUserSerializer

from .models import AcceptableUseAcceptance, ModerationAction, Report

# What may be reported. A closed list, because an open one is an invitation
# to probe the platform's internals by guessing content types.
REPORTABLE = {"community.thread", "community.post", "projects.project",
              "showcase.showcaseentry", "accounts.user", "contributions.contribution"}


class ReportSerializer(serializers.ModelSerializer):
    reporter = PublicUserSerializer(read_only=True)
    target_model = serializers.CharField(write_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    needs_advisor = serializers.BooleanField(read_only=True)

    class Meta:
        model = Report
        fields = ["id", "reporter", "target_model", "target_id", "target_label",
                  "reason", "reason_display", "detail", "status", "needs_advisor",
                  "resolution_note", "created_at", "resolved_at"]
        read_only_fields = ["reporter", "status", "resolution_note", "resolved_at",
                            "target_label"]

    def validate_target_model(self, value: str) -> str:
        if value.lower() not in REPORTABLE:
            raise serializers.ValidationError(
                f"Reportable items are: {', '.join(sorted(REPORTABLE))}.")
        return value.lower()

    def create(self, validated_data):
        label = validated_data.pop("target_model")
        app_label, model = label.split(".")
        validated_data["target_type"] = ContentType.objects.get(app_label=app_label,
                                                                model=model)
        return super().create(validated_data)


class ModerationActionSerializer(serializers.ModelSerializer):
    moderator = PublicUserSerializer(read_only=True)
    subject = PublicUserSerializer(read_only=True)
    subject_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = ModerationAction
        fields = ["id", "report", "moderator", "subject", "subject_id", "action",
                  "action_display", "rationale", "expires_at", "created_at"]
        read_only_fields = ["moderator"]

    def validate_rationale(self, value: str) -> str:
        if len(value.strip()) < 20:
            raise serializers.ValidationError(
                "Write a proper rationale. Every moderation decision on FORGE has "
                "to be explainable, including to the person it is taken against."
            )
        return value


class AcceptanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcceptableUseAcceptance
        fields = ["id", "document", "version", "text_digest", "accepted_at"]
        read_only_fields = ["text_digest", "accepted_at"]
