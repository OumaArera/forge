from django.contrib import admin

from .models import Milestone, ProgressUpdate, Task


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "due_on")
    list_filter = ("status",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "assignee", "due_on")
    list_filter = ("status", "priority")
    search_fields = ("title",)


@admin.register(ProgressUpdate)
class ProgressUpdateAdmin(admin.ModelAdmin):
    list_display = ("project", "author", "covers_week_of", "needs_help")
    list_filter = ("needs_help",)
