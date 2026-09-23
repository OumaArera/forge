"""Team workspace endpoints. Access follows project membership, always."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from forge.common.exceptions import NotEligible
from forge.common.permissions import IsVerifiedStudent
from forge.projects.models import Project

from .models import Milestone, ProgressUpdate, Task
from .serializers import MilestoneSerializer, ProgressUpdateSerializer, TaskSerializer


class TeamScopedMixin:
    """
    Restricts every operation to projects the caller is actually on.

    Written once here rather than repeated in each viewset, because a missing
    membership check on one endpoint is worth more to an attacker than a
    correct check on the other five.
    """

    permission_classes = [IsVerifiedStudent]

    def my_project_ids(self):
        user = self.request.user
        return set(
            Project.objects.filter(memberships__user=user,
                                   memberships__left_at__isnull=True)
            .values_list("id", flat=True)
        ) | set(Project.objects.filter(lead=user).values_list("id", flat=True)) | set(
            Project.objects.filter(mentor=user).values_list("id", flat=True))

    def check_project(self, project):
        if project.id not in self.my_project_ids():
            raise NotEligible("That project's workspace is for its team.")


class MilestoneViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = Milestone.objects.none()  # real filtering happens in get_queryset
    serializer_class = MilestoneSerializer
    filterset_fields = ["project", "status"]

    def get_queryset(self):
        return Milestone.objects.filter(project_id__in=self.my_project_ids())

    def perform_create(self, serializer):
        self.check_project(serializer.validated_data["project"])
        serializer.save()


class TaskViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = Task.objects.none()  # real filtering happens in get_queryset
    serializer_class = TaskSerializer
    filterset_fields = ["project", "milestone", "status", "assignee"]
    ordering_fields = ["priority", "due_on", "created_at"]

    def get_queryset(self):
        return (Task.objects.filter(project_id__in=self.my_project_ids())
                .select_related("assignee", "milestone"))

    def perform_create(self, serializer):
        self.check_project(serializer.validated_data["project"])
        serializer.save(created_by=self.request.user)

    @extend_schema(responses={200: TaskSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        queryset = self.get_queryset().filter(
            assignee=request.user
        ).exclude(status__in=[Task.Status.DONE, Task.Status.DROPPED])
        return Response(TaskSerializer(queryset, many=True).data)


class ProgressUpdateViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = ProgressUpdate.objects.none()  # real filtering happens in get_queryset
    serializer_class = ProgressUpdateSerializer
    filterset_fields = ["project", "needs_help"]

    def get_queryset(self):
        return (ProgressUpdate.objects.filter(project_id__in=self.my_project_ids())
                .select_related("author", "project"))

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        self.check_project(project)
        update = serializer.save(author=self.request.user)
        project.touch_activity()

        if update.needs_help:
            # A team asking for help early is the behaviour the platform most
            # wants to reward, so the ask is routed rather than left to be
            # noticed.
            from forge.notifications.services import notify

            for person in filter(None, [project.mentor]):
                notify(person, verb="project.stage_changed", target=project,
                       summary=f"{project.title} has asked for help in its weekly update.")
