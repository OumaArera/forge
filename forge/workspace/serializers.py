from __future__ import annotations

from rest_framework import serializers

from forge.accounts.serializers import PublicUserSerializer

from .models import Milestone, ProgressUpdate, Task


class TaskSerializer(serializers.ModelSerializer):
    assignee = PublicUserSerializer(read_only=True)
    assignee_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Task
        fields = ["id", "project", "milestone", "title", "description", "assignee",
                  "assignee_id", "status", "status_display", "priority", "due_on",
                  "blocked_reason", "completed_at", "created_at"]
        read_only_fields = ["completed_at"]

    def validate(self, attrs):
        status = attrs.get("status", getattr(self.instance, "status", None))
        reason = attrs.get("blocked_reason",
                           getattr(self.instance, "blocked_reason", ""))
        if status == Task.Status.BLOCKED and not (reason or "").strip():
            raise serializers.ValidationError(
                {"blocked_reason": "Say what this is blocked on."})
        return attrs


class MilestoneSerializer(serializers.ModelSerializer):
    task_count = serializers.SerializerMethodField()
    done_count = serializers.SerializerMethodField()
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Milestone
        fields = ["id", "project", "title", "description", "due_on", "status",
                  "delivered_at", "order", "external_url", "task_count",
                  "done_count", "is_overdue"]
        read_only_fields = ["delivered_at"]

    def get_task_count(self, obj) -> int:
        return obj.tasks.count()

    def get_done_count(self, obj) -> int:
        return obj.tasks.filter(status=Task.Status.DONE).count()


class ProgressUpdateSerializer(serializers.ModelSerializer):
    author = PublicUserSerializer(read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)

    class Meta:
        model = ProgressUpdate
        fields = ["id", "project", "project_title", "author", "body", "blockers",
                  "needs_help", "covers_week_of", "created_at"]
        read_only_fields = ["author"]
