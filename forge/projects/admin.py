from django.contrib import admin

from .models import (
    Application,
    Membership,
    Project,
    ProjectReview,
    ProjectRole,
    StageTransition,
)


class ProjectRoleInline(admin.TabularInline):
    model = ProjectRole
    extra = 0
    filter_horizontal = ("required_skills",)


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user", "understudy_to")
    readonly_fields = ("joined_at",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "stage", "lead", "mentor", "school_spread",
                    "last_activity_at")
    list_filter = ("status", "visibility", "is_open_source", "discipline_areas")
    search_fields = ("title", "summary", "lead__full_name")
    autocomplete_fields = ("lead", "mentor")
    filter_horizontal = ("discipline_areas",)
    readonly_fields = ("slug", "submitted_at", "approved_at", "completed_at",
                       "last_activity_at", "stage")
    inlines = [ProjectRoleInline, MembershipInline]
    date_hierarchy = "created_at"

    @admin.display(description="Stage")
    def stage(self, obj) -> int:
        return obj.stage

    @admin.display(description="Schools represented")
    def school_spread(self, obj) -> int:
        return obj.school_spread


@admin.register(ProjectReview)
class ProjectReviewAdmin(admin.ModelAdmin):
    list_display = ("project", "decision", "reviewer", "created_at")
    list_filter = ("decision",)
    search_fields = ("project__title", "reviewer__full_name")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("applicant", "role", "project", "status", "created_at", "decided_at")
    list_filter = ("status",)
    search_fields = ("applicant__full_name", "project__title")


@admin.register(StageTransition)
class StageTransitionAdmin(admin.ModelAdmin):
    list_display = ("project", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status",)
    search_fields = ("project__title",)

    def has_change_permission(self, request, obj=None):
        return False
