"""Project endpoints: the seven-stage lifecycle over HTTP."""

from __future__ import annotations

from django.db.models import Prefetch, Q
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from forge.common.exceptions import NotEligible
from forge.common.permissions import IsMentorOrLead, IsVerifiedStudent

from .models import Application, Membership, Project, ProjectRole
from .serializers import (
    ApplicationDecisionSerializer,
    ApplicationSerializer,
    HandoverSerializer,
    MembershipSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    ProjectReviewSerializer,
    ProjectRoleSerializer,
    ProjectWriteSerializer,
    StageTransitionSerializer,
    TransitionRequestSerializer,
)
from .services import (
    apply_to_role,
    decide_application,
    hand_over_lead,
    remove_member,
    review_proposal,
    submit_for_review,
    transition,
)


class ProjectFilter(filters.FilterSet):
    discipline = filters.CharFilter(field_name="discipline_areas__slug")
    school = filters.UUIDFilter(field_name="lead__school_id")
    recruiting = filters.BooleanFilter(method="filter_recruiting")
    beginner_friendly = filters.BooleanFilter(method="filter_beginner_friendly")
    cross_disciplinary = filters.BooleanFilter(method="filter_cross_disciplinary")

    class Meta:
        model = Project
        fields = ["status", "is_open_source", "visibility"]

    def filter_recruiting(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(status=Project.Status.RECRUITING,
                               roles__is_open=True).distinct()

    def filter_beginner_friendly(self, queryset, name, value):
        """
        Projects carrying at least one role a newcomer can take.

        Worth a first-class filter: a first-year with no track record who
        cannot find a way in is the single most likely person to give up on
        the platform, and they are exactly who it is for.
        """
        if not value:
            return queryset
        return queryset.filter(roles__open_to_beginners=True,
                               roles__is_open=True).distinct()

    def filter_cross_disciplinary(self, queryset, name, value):
        if not value:
            return queryset
        ids = [p.id for p in queryset if p.school_spread > 1]
        return queryset.filter(id__in=ids)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.none()  # real filtering happens in get_queryset
    lookup_field = "slug"
    filterset_class = ProjectFilter
    search_fields = ["title", "summary", "problem_statement"]
    ordering_fields = ["last_activity_at", "created_at", "target_completion_on"]
    # An explicit default: pagination over an unordered queryset can show the
    # same project on two pages and omit another entirely.
    ordering = ["-last_activity_at"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsVerifiedStudent()]

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        return (
            Project.objects.visible_to(user)
            .select_related("lead", "mentor", "lead__school")
            .prefetch_related(
                "discipline_areas",
                Prefetch("roles", queryset=ProjectRole.objects.prefetch_related(
                    "required_skills")),
            )
            .with_team_size()
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return ProjectWriteSerializer
        if self.action == "retrieve":
            return ProjectDetailSerializer
        return ProjectListSerializer

    def perform_create(self, serializer):
        project = serializer.save(lead=self.request.user)
        # The proposer is a member of their own team from the start; otherwise
        # they cannot log contributions against their own project.
        Membership.objects.create(project=project, user=self.request.user, is_lead=True)

    def perform_update(self, serializer):
        project = self.get_object()
        if not project.may_manage(self.request.user):
            raise NotEligible("Only the project lead may edit this project.")
        if project.status not in {Project.Status.DRAFT, Project.Status.RETURNED,
                                  Project.Status.RECRUITING, Project.Status.BUILDING}:
            raise NotEligible(
                "A project at this stage cannot be edited. The objectives a team "
                "delivered against must stay as they were reviewed."
            )
        serializer.save()

    # -- lifecycle ----------------------------------------------------------

    @extend_schema(request=None, responses={200: ProjectDetailSerializer})
    @action(detail=True, methods=["post"])
    def submit(self, request, slug=None):
        """Stage 1 -> 2. Send a proposal for review."""
        project = submit_for_review(self.get_object(), actor=request.user)
        return Response(ProjectDetailSerializer(project, context={"request": request}).data)

    @extend_schema(request=ProjectReviewSerializer, responses={201: ProjectReviewSerializer})
    @action(detail=True, methods=["post"], permission_classes=[IsMentorOrLead])
    def review(self, request, slug=None):
        """Stage 2. The gate that keeps the platform from filling with abandoned ideas."""
        serializer = ProjectReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = review_proposal(self.get_object(), reviewer=request.user,
                                 **serializer.validated_data)
        return Response(ProjectReviewSerializer(review).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=TransitionRequestSerializer, responses={200: ProjectDetailSerializer})
    @action(detail=True, methods=["post"], url_path="transition")
    def do_transition(self, request, slug=None):
        project = self.get_object()
        if not project.may_manage(request.user):
            raise NotEligible("Only the project lead or mentor may move this project "
                              "between stages.")
        serializer = TransitionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = transition(project, serializer.validated_data["to_status"],
                             actor=request.user,
                             note=serializer.validated_data.get("note", ""))
        return Response(ProjectDetailSerializer(project, context={"request": request}).data)

    @extend_schema(responses={200: StageTransitionSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def history(self, request, slug=None):
        project = self.get_object()
        return Response(StageTransitionSerializer(
            project.transitions.select_related("actor")[:100], many=True).data)

    @extend_schema(responses={200: ProjectReviewSerializer(many=True)})
    @action(detail=True, methods=["get"], url_path="reviews")
    def list_reviews(self, request, slug=None):
        project = self.get_object()
        if not (project.may_manage(request.user) or request.user.can_review_proposals):
            raise NotEligible("Reviews are visible to the project team and to reviewers.")
        return Response(ProjectReviewSerializer(
            project.reviews.select_related("reviewer"), many=True).data)

    # -- team ---------------------------------------------------------------

    @extend_schema(request=ProjectRoleSerializer, responses={201: ProjectRoleSerializer})
    @action(detail=True, methods=["post"], url_path="roles")
    def add_role(self, request, slug=None):
        project = self.get_object()
        if not project.may_manage(request.user):
            raise NotEligible("Only the project lead may advertise roles.")
        serializer = ProjectRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: MembershipSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def team(self, request, slug=None):
        project = self.get_object()
        return Response(MembershipSerializer(
            project.memberships.select_related("user", "role", "understudy_to"),
            many=True).data)

    @extend_schema(request=HandoverSerializer, responses={200: ProjectDetailSerializer})
    @action(detail=True, methods=["post"], url_path="hand-over-lead")
    def handover(self, request, slug=None):
        """
        Transfer leadership. Succession is what keeps a project alive past its
        founder's exam period.
        """
        from forge.accounts.models import User

        serializer = HandoverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to_user = User.objects.get(pk=serializer.validated_data["to_user_id"])
        project = hand_over_lead(self.get_object(), to_user=to_user, actor=request.user,
                                 note=serializer.validated_data.get("note", ""))
        return Response(ProjectDetailSerializer(project, context={"request": request}).data)

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"], url_path="leave")
    def leave(self, request, slug=None):
        remove_member(self.get_object(), request.user, actor=request.user,
                      reason=request.data.get("reason", ""))
        return Response({"detail": "You have left this project. Your confirmed "
                                   "contributions remain part of your portfolio."})

    @extend_schema(responses={200: ProjectListSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="mine",
            permission_classes=[IsAuthenticated])
    def mine(self, request):
        queryset = self.get_queryset().filter(
            memberships__user=request.user, memberships__left_at__isnull=True
        ).distinct()
        page = self.paginate_queryset(queryset)
        serializer = ProjectListSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    @extend_schema(responses={200: ProjectListSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="awaiting-review",
            permission_classes=[IsMentorOrLead])
    def awaiting_review(self, request):
        """The reviewer's queue, oldest first -- the ones keeping someone waiting."""
        queryset = (
            Project.objects.filter(status__in=[Project.Status.SUBMITTED,
                                               Project.Status.UNDER_REVIEW])
            .select_related("lead").prefetch_related("discipline_areas", "roles")
            .order_by("submitted_at")
        )
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(
            ProjectListSerializer(page, many=True, context={"request": request}).data)


class RoleViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = ProjectRoleSerializer
    permission_classes = [IsVerifiedStudent]

    def get_queryset(self):
        return ProjectRole.objects.select_related("project").prefetch_related(
            "required_skills")

    def _check_manage(self, role):
        if not role.project.may_manage(self.request.user):
            raise NotEligible("Only the project lead may change roles.")

    def perform_update(self, serializer):
        self._check_manage(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_manage(instance)
        if instance.filled_slots:
            raise NotEligible("Someone holds this role. Remove them from the team first.")
        instance.delete()

    @extend_schema(request=ApplicationSerializer, responses={201: ApplicationSerializer})
    @action(detail=True, methods=["post"], url_path="apply")
    def apply(self, request, pk=None):
        role = self.get_object()
        application = apply_to_role(role=role, applicant=request.user,
                                    statement=request.data.get("statement", ""))
        return Response(ApplicationSerializer(application).data,
                        status=status.HTTP_201_CREATED)


class ApplicationViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    queryset = Application.objects.none()  # real filtering happens in get_queryset
    serializer_class = ApplicationSerializer
    permission_classes = [IsVerifiedStudent]
    filterset_fields = ["status", "project"]

    def get_queryset(self):
        user = self.request.user
        # You see your own applications, and the applications to projects you lead.
        return (
            Application.objects.filter(
                Q(applicant=user) | Q(project__lead=user)
            )
            .select_related("applicant", "role", "project")
            .distinct()
        )

    @extend_schema(request=ApplicationDecisionSerializer, responses={200: ApplicationSerializer})
    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        serializer = ApplicationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = decide_application(
            self.get_object(), decider=request.user,
            accept=serializer.validated_data["accept"],
            note=serializer.validated_data.get("note", ""),
        )
        return Response(ApplicationSerializer(application).data)

    @extend_schema(request=None, responses={200: ApplicationSerializer})
    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        application = self.get_object()
        if application.applicant_id != request.user.id:
            raise NotEligible("That is not your application.")
        if application.status != Application.Status.PENDING:
            raise NotEligible("That application has already been decided.")
        application.status = Application.Status.WITHDRAWN
        application.save(update_fields=["status", "updated_at"])
        return Response(ApplicationSerializer(application).data)
