"""
The team workspace: milestones, tasks and progress updates.

This is deliberately the thinnest module in FORGE. There are excellent free
project trackers and the platform is not trying to beat them; what it needs
is just enough structure that a contribution claim can point at something
real, and that a mentor can see whether a team is moving. Teams that prefer
to run their board elsewhere can, and `Milestone.external_url` is there for
exactly that.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.utils import timezone

from forge.common.fields import validate_no_html
from forge.common.models import BaseModel


class Milestone(BaseModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        DELIVERED = "delivered", "Delivered"
        DROPPED = "dropped", "Dropped"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE,
                                related_name="milestones")
    title = models.CharField(max_length=140, validators=[validate_no_html])
    description = models.TextField(blank=True, max_length=2000, validators=[validate_no_html])
    due_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNED)
    delivered_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    external_url = models.URLField(
        blank=True, validators=[URLValidator(schemes=["https"])],
        help_text="If the team tracks this work elsewhere, link to it rather than "
                  "keeping two boards in step by hand.",
    )

    class Meta:
        ordering = ["order", "due_on", "created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.project.title})"

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.due_on and self.status != self.Status.DELIVERED
            and self.due_on < timezone.localdate()
        )


class Task(BaseModel):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        BLOCKED = "blocked", "Blocked"
        IN_REVIEW = "in_review", "In review"
        DONE = "done", "Done"
        DROPPED = "dropped", "Dropped"

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        NORMAL = 2, "Normal"
        HIGH = 3, "High"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE,
                                related_name="tasks")
    milestone = models.ForeignKey(Milestone, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="tasks")
    title = models.CharField(max_length=160, validators=[validate_no_html])
    description = models.TextField(blank=True, max_length=4000, validators=[validate_no_html])
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="tasks_assigned")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="tasks_created")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.TODO,
                              db_index=True)
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.NORMAL)
    due_on = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    blocked_reason = models.CharField(
        max_length=300, blank=True,
        help_text="Required when a task is blocked. A blocked task nobody can see "
                  "the reason for is a task that stays blocked.",
    )

    class Meta:
        ordering = ["-priority", "due_on", "created_at"]
        indexes = [models.Index(fields=["project", "status"]),
                   models.Index(fields=["assignee", "status"])]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        super().clean()
        if self.status == self.Status.BLOCKED and not self.blocked_reason.strip():
            raise ValidationError({"blocked_reason": "Say what this is blocked on."})
        if self.milestone and self.milestone.project_id != self.project_id:
            raise ValidationError({"milestone": "That milestone belongs to another project."})

    def save(self, *args, **kwargs):
        if self.status == self.Status.DONE and self.completed_at is None:
            self.completed_at = timezone.now()
        if self.status != self.Status.DONE:
            self.completed_at = None
        super().save(*args, **kwargs)


class ProgressUpdate(BaseModel):
    """
    A short, regular note on how a project is going.

    Required weekly from active projects. It is the cheapest possible early
    warning: a team that has not posted in three weeks is a team in trouble,
    and the mentor finds out from a list rather than from the silence.
    """

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE,
                                related_name="progress_updates")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="progress_updates")
    body = models.TextField(max_length=3000, validators=[validate_no_html])
    blockers = models.TextField(
        blank=True, max_length=1500, validators=[validate_no_html],
        help_text="What is in the way. Leaving this blank week after week while "
                  "nothing ships helps nobody.",
    )
    needs_help = models.BooleanField(
        default=False,
        help_text="Flags this update to the mentor and to community leads. Asking "
                  "for help early is the behaviour the platform wants to reward.",
    )
    covers_week_of = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-covers_week_of", "-created_at"]

    def __str__(self) -> str:
        return f"{self.project.title} week of {self.covers_week_of}"
