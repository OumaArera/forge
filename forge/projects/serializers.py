"""Serializers for projects, roles, applications and reviews."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from forge.accounts.models import DisciplineArea, Skill
from forge.accounts.serializers import (
    DisciplineAreaSerializer,
    PublicUserSerializer,
    SkillSerializer,
)

from .models import (
    Application,
    Membership,
    Project,
    ProjectReview,
    ProjectRole,
    StageTransition,
)


class ProjectRoleSerializer(serializers.ModelSerializer):
    required_skills = SkillSerializer(many=True, read_only=True)
    required_skill_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), source="required_skills", many=True,
        write_only=True, required=False,
    )
    filled_slots = serializers.IntegerField(read_only=True)
    has_vacancy = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProjectRole
        fields = ["id", "title", "description", "required_skills", "required_skill_ids",
                  "slots", "filled_slots", "has_vacancy", "is_open",
                  "open_to_beginners", "preferred_school"]


class MembershipSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    role_title = serializers.CharField(source="role.title", read_only=True, default=None)
    understudy_to = PublicUserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "role_title", "is_lead", "understudy_to",
                  "joined_at", "left_at", "days_served", "is_active"]
        read_only_fields = fields


class ProjectListSerializer(serializers.ModelSerializer):
    lead = PublicUserSerializer(read_only=True)
    discipline_areas = DisciplineAreaSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    stage = serializers.IntegerField(read_only=True)
    open_roles = serializers.SerializerMethodField()
    team_size = serializers.SerializerMethodField()
    is_cross_disciplinary = serializers.BooleanField(read_only=True)

    class Meta:
        model = Project
        fields = ["id", "title", "slug", "summary", "status", "status_display", "stage",
                  "lead", "discipline_areas", "open_roles", "team_size",
                  "is_cross_disciplinary", "is_open_source", "effort_hours_per_week",
                  "target_completion_on", "last_activity_at", "created_at"]

    def get_open_roles(self, obj) -> int:
        return sum(1 for r in obj.roles.all() if r.has_vacancy)

    def get_team_size(self, obj) -> int:
        return getattr(obj, "team_size", None) or obj.memberships.filter(
            left_at__isnull=True).count()


class ProjectDetailSerializer(ProjectListSerializer):
    roles = ProjectRoleSerializer(many=True, read_only=True)
    memberships = serializers.SerializerMethodField()
    mentor = PublicUserSerializer(read_only=True)
    school_spread = serializers.IntegerField(read_only=True)
    is_stale = serializers.BooleanField(read_only=True)
    permitted_transitions = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

    class Meta(ProjectListSerializer.Meta):
        fields = [*ProjectListSerializer.Meta.fields,
            "problem_statement", "objectives", "roles", "memberships", "mentor",
            "school_spread", "is_stale", "starts_on", "licence", "repository_url",
            "ownership_terms", "ownership_agreed_at", "visibility",
            "permitted_transitions", "my_role", "submitted_at", "approved_at",
            "completed_at",
        ]

    @extend_schema_field(MembershipSerializer(many=True))
    def get_memberships(self, obj):
        return MembershipSerializer(obj.active_members, many=True).data

    def get_permitted_transitions(self, obj) -> list[str]:
        return list(Project.TRANSITIONS.get(obj.status, ()))

    def get_my_role(self, obj) -> str | None:
        user = self.context["request"].user
        if not user.is_authenticated:
            return None
        if obj.lead_id == user.id:
            return "lead"
        if obj.mentor_id == user.id:
            return "mentor"
        membership = obj.memberships.filter(user=user, left_at__isnull=True).first()
        return "member" if membership else None


class ProjectWriteSerializer(serializers.ModelSerializer):
    discipline_area_ids = serializers.PrimaryKeyRelatedField(
        queryset=DisciplineArea.objects.filter(is_active=True),
        source="discipline_areas", many=True, write_only=True,
    )

    class Meta:
        model = Project
        fields = ["title", "summary", "problem_statement", "objectives",
                  "discipline_area_ids", "starts_on", "target_completion_on",
                  "effort_hours_per_week", "is_open_source", "licence",
                  "repository_url", "visibility", "ownership_terms"]

    def validate(self, attrs):
        if attrs.get("is_open_source") and not attrs.get("licence"):
            raise serializers.ValidationError({
                "licence": "Name a licence if the project is released openly. Work "
                           "published without one is not usable by anyone."
            })
        return attrs


class ApplicationSerializer(serializers.ModelSerializer):
    applicant = PublicUserSerializer(read_only=True)
    role_title = serializers.CharField(source="role.title", read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)

    class Meta:
        model = Application
        fields = ["id", "project", "project_title", "role", "role_title", "applicant",
                  "statement", "status", "decided_at", "decision_note", "created_at"]
        read_only_fields = ["project", "status", "decided_at", "decision_note"]


class ApplicationDecisionSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate(self, attrs):
        if not attrs["accept"] and not (attrs.get("note") or "").strip():
            raise serializers.ValidationError({
                "note": "Give a reason when declining. An applicant turned down "
                        "without one learns nothing."
            })
        return attrs


class ProjectReviewSerializer(serializers.ModelSerializer):
    reviewer = PublicUserSerializer(read_only=True)

    class Meta:
        model = ProjectReview
        fields = ["id", "decision", "reasons", "scope_is_realistic",
                  "is_lawful_and_ethical", "is_not_duplicative", "has_clear_objectives",
                  "suggested_mentor", "reviewer", "created_at"]
        read_only_fields = ["reviewer", "created_at"]


class StageTransitionSerializer(serializers.ModelSerializer):
    actor = PublicUserSerializer(read_only=True)

    class Meta:
        model = StageTransition
        fields = ["id", "from_status", "to_status", "actor", "note", "created_at"]
        read_only_fields = fields


class TransitionRequestSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=Project.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class RoleSuggestionSerializer(serializers.ModelSerializer):
    """An open role, with just enough of its project to decide on."""

    project = ProjectListSerializer(read_only=True)
    required_skills = SkillSerializer(many=True, read_only=True)
    match_score = serializers.SerializerMethodField()

    class Meta:
        model = ProjectRole
        fields = ["id", "title", "description", "required_skills", "slots",
                  "open_to_beginners", "project", "match_score"]
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField())
    def get_match_score(self, obj) -> int:
        # Set by suggest_roles_for; absent when a role is serialised elsewhere.
        return getattr(obj, "score", 0)


class HandoverSerializer(serializers.Serializer):
    to_user_id = serializers.UUIDField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
