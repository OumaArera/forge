from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only: the audit log is evidence, not a worksheet."""

    list_display = ("occurred_at", "action", "actor_label", "target_label", "ip_address")
    list_filter = ("action", "occurred_at")
    search_fields = ("actor_label", "target_label", "target_id", "ip_address")
    date_hierarchy = "occurred_at"
    ordering = ("-occurred_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
