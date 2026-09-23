from django.contrib import admin

from .models import PortfolioExport


@admin.register(PortfolioExport)
class PortfolioExportAdmin(admin.ModelAdmin):
    """
    A log of every export issued.

    Read-only: this is the record a signature is checked against, so it must
    say what the platform actually issued rather than what somebody later
    wished it had issued.
    """

    list_display = ("user", "export_format", "entry_count", "issued_at", "key_id")
    list_filter = ("export_format",)
    search_fields = ("user__full_name", "document_digest")
    readonly_fields = [f.name for f in PortfolioExport._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
