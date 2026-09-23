from django.contrib import admin

from .models import Attestation, Contribution, LedgerEntry


class AttestationInline(admin.TabularInline):
    model = Attestation
    extra = 0
    readonly_fields = ("attestor", "attestor_name", "capacity", "decision", "note",
                       "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ("contributor", "project", "dimension", "status", "occurred_on",
                    "ai_assistance", "is_late")
    list_filter = ("status", "dimension", "ai_assistance")
    search_fields = ("description", "contributor__full_name", "project__title")
    autocomplete_fields = ("contributor",)
    filter_horizontal = ("skills_used",)
    readonly_fields = ("submitted_at", "settled_at")
    inlines = [AttestationInline]
    date_hierarchy = "occurred_on"

    @admin.display(boolean=True, description="Logged late")
    def is_late(self, obj) -> bool:
        return obj.is_late


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """
    Read-only, always.

    The ledger is the evidence the whole platform produces. Nothing in the
    admin may write to it: a correction is made by appending, never by editing.
    Run `python manage.py verify_ledger` to check the chain.
    """

    list_display = ("sequence", "contributor", "project", "dimension", "points",
                    "recorded_at", "intact")
    list_filter = ("dimension",)
    search_fields = ("entry_hash", "contributor__full_name", "project__title")
    ordering = ("-sequence",)

    @admin.display(boolean=True, description="Hash verifies")
    def intact(self, obj) -> bool:
        return obj.is_intact

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
