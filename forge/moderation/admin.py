from django.contrib import admin

from .models import AcceptableUseAcceptance, ModerationAction, Report


class ModerationActionInline(admin.TabularInline):
    model = ModerationAction
    extra = 0
    readonly_fields = ("moderator", "created_at", "notified_subject_at")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "reason", "status", "reporter", "target_label",
                    "assigned_to")
    list_filter = ("status", "reason")
    search_fields = ("detail", "target_label")
    inlines = [ModerationActionInline]
    date_hierarchy = "created_at"


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "moderator", "subject", "expires_at")
    list_filter = ("action",)
    search_fields = ("rationale", "subject__full_name")


@admin.register(AcceptableUseAcceptance)
class AcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user", "document", "version", "accepted_at")
    list_filter = ("document", "version")
    search_fields = ("user__full_name",)
    readonly_fields = [f.name for f in AcceptableUseAcceptance._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
