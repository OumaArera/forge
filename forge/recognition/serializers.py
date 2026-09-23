from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from forge.accounts.serializers import PublicUserSerializer

from .models import (
    Badge,
    BadgeAward,
    Certificate,
    CertificateDownload,
    LeaderboardSnapshot,
    Level,
    Standing,
)


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = ["id", "name", "slug", "rank", "min_points",
                  "min_confirmed_contributions", "min_completed_projects",
                  "requires_teaching", "description"]


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ["id", "name", "slug", "kind", "description", "criteria", "icon"]


class BadgeAwardSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True,
                                          default=None)

    class Meta:
        model = BadgeAward
        fields = ["id", "badge", "project_title", "reason", "awarded_at"]


class StandingSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    level = LevelSerializer(read_only=True)
    next_level = serializers.SerializerMethodField()

    class Meta:
        model = Standing
        fields = ["user", "level", "next_level", "total_points",
                  "confirmed_contributions", "completed_projects", "projects_led",
                  "people_mentored", "points_by_dimension", "points_by_area",
                  "first_contribution_at", "last_contribution_at", "recomputed_at"]

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_next_level(self, obj):
        current_rank = obj.level.rank if obj.level else 0
        nxt = Level.objects.filter(rank__gt=current_rank).order_by("rank").first()
        if nxt is None:
            return None
        return {
            "name": nxt.name,
            "points_needed": max(nxt.min_points - obj.total_points, 0),
            "contributions_needed": max(
                nxt.min_confirmed_contributions - obj.confirmed_contributions, 0),
            "projects_needed": max(
                nxt.min_completed_projects - obj.completed_projects, 0),
            "requires_teaching": nxt.requires_teaching,
        }


class LeaderboardSerializer(serializers.ModelSerializer):
    discipline_area_name = serializers.CharField(source="discipline_area.name",
                                                 read_only=True, default=None)

    class Meta:
        model = LeaderboardSnapshot
        fields = ["id", "scope", "discipline_area_name", "period", "period_start",
                  "period_end", "rows", "computed_at"]


class CertificateDownloadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateDownload
        fields = ["id", "downloaded_by_name", "was_holder", "downloaded_at"]
        read_only_fields = fields


class CertificateSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source="project.title", read_only=True,
                                          default=None)
    is_valid = serializers.BooleanField(read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    download_count = serializers.IntegerField(read_only=True)
    last_downloaded_at = serializers.DateTimeField(read_only=True)
    # The holder's own audit trail. They are the only person who sees it, so
    # it names the account rather than summarising -- if a certificate they
    # downloaded once shows four, the problem is the account, not the file.
    downloads = CertificateDownloadSerializer(many=True, read_only=True)

    class Meta:
        model = Certificate
        fields = ["id", "kind", "kind_display", "project_title", "recipient_name",
                  "statement", "verification_code", "ledger_head", "issued_at",
                  "is_valid", "download_count", "last_downloaded_at", "downloads"]
        read_only_fields = fields
