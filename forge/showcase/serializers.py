from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from forge.accounts.serializers import PublicUserSerializer

from .models import ShowcaseEntry, ShowcaseImage


class ShowcaseImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowcaseImage
        fields = ["id", "image", "caption", "alt_text", "order"]

    def validate_alt_text(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError(
                "Describe the image for someone who cannot see it. Required."
            )
        return value


class ShowcaseEntrySerializer(serializers.ModelSerializer):
    images = ShowcaseImageSerializer(many=True, read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)
    project_slug = serializers.CharField(source="project.slug", read_only=True)
    lead = PublicUserSerializer(source="project.lead", read_only=True)
    team = serializers.SerializerMethodField()
    discipline_areas = serializers.SerializerMethodField()

    class Meta:
        model = ShowcaseEntry
        fields = ["id", "project", "project_title", "project_slug", "headline",
                  "what_we_built", "what_we_learned", "outcome", "demonstration_url",
                  "documentation_url", "live_url", "repository_url", "images",
                  "lead", "team", "discipline_areas", "is_published", "published_at",
                  "is_featured", "featured_note", "view_count"]
        read_only_fields = ["is_featured", "featured_note", "view_count", "published_at"]

    @extend_schema_field(PublicUserSerializer(many=True))
    def get_team(self, obj):
        return PublicUserSerializer(
            [m.user for m in obj.project.active_members], many=True).data

    def get_discipline_areas(self, obj) -> list[str]:
        return [a.name for a in obj.project.discipline_areas.all()]
