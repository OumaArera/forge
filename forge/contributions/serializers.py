from __future__ import annotations

from rest_framework import serializers

from forge.accounts.models import Skill
from forge.accounts.serializers import PublicUserSerializer, SkillSerializer

from .models import Attestation, Contribution, LedgerEntry


class AttestationSerializer(serializers.ModelSerializer):
    capacity_display = serializers.CharField(source="get_capacity_display", read_only=True)

    class Meta:
        model = Attestation
        fields = ["id", "attestor_name", "capacity", "capacity_display", "decision",
                  "note", "created_at"]
        read_only_fields = fields


class ContributionSerializer(serializers.ModelSerializer):
    contributor = PublicUserSerializer(read_only=True)
    skills_used = SkillSerializer(many=True, read_only=True)
    skill_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), source="skills_used", many=True,
        write_only=True, required=False,
    )
    attestations = AttestationSerializer(many=True, read_only=True)
    dimension_display = serializers.CharField(source="get_dimension_display", read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)
    is_late = serializers.BooleanField(read_only=True)
    ledger_sequence = serializers.IntegerField(source="ledger_entry.sequence",
                                               read_only=True, default=None)

    class Meta:
        model = Contribution
        fields = ["id", "project", "project_title", "contributor", "dimension",
                  "dimension_display", "description", "evidence_url", "effort_hours",
                  "occurred_on", "milestone", "skills_used", "skill_ids",
                  "ai_assistance", "ai_assistance_note", "status", "attestations",
                  "is_late", "ledger_sequence", "submitted_at", "settled_at",
                  "created_at"]
        read_only_fields = ["contributor", "status", "submitted_at", "settled_at"]

    def validate(self, attrs):
        ai = attrs.get("ai_assistance", getattr(self.instance, "ai_assistance", "none"))
        note = attrs.get("ai_assistance_note",
                         getattr(self.instance, "ai_assistance_note", ""))
        if ai != Contribution.AIAssistance.NONE and not (note or "").strip():
            raise serializers.ValidationError({
                "ai_assistance_note": "Say briefly what the tool did and what you did."
            })
        return attrs


class AttestRequestSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate(self, attrs):
        if not attrs["confirm"] and not (attrs.get("note") or "").strip():
            raise serializers.ValidationError(
                {"note": "Say why you are disputing this claim."})
        return attrs


class LedgerEntrySerializer(serializers.ModelSerializer):
    contributor = PublicUserSerializer(read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)
    is_intact = serializers.BooleanField(read_only=True)

    class Meta:
        model = LedgerEntry
        fields = ["sequence", "contributor", "project_title", "dimension", "points",
                  "previous_hash", "entry_hash", "recorded_at", "is_intact", "payload"]
        read_only_fields = fields
