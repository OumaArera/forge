from django.contrib import admin

from .models import (
    Badge,
    BadgeAward,
    Certificate,
    LeaderboardSnapshot,
    Level,
    LevelAward,
    Standing,
)


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ("rank", "name", "min_points", "min_confirmed_contributions",
                    "min_completed_projects", "requires_teaching")
    ordering = ("rank",)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "criteria", "is_active")
    list_filter = ("kind", "is_active")


@admin.register(Standing)
class StandingAdmin(admin.ModelAdmin):
    list_display = ("user", "level", "total_points", "confirmed_contributions",
                    "completed_projects", "recomputed_at")
    search_fields = ("user__full_name", "user__public_slug")
    readonly_fields = [f.name for f in Standing._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Standing is derived from the ledger. Editing it here would put a
        # number on a portfolio that no contribution backs.
        return False


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("verification_code", "recipient_name", "kind", "project",
                    "issued_at", "revoked_at")
    list_filter = ("kind",)
    search_fields = ("verification_code", "recipient_name")
    readonly_fields = ("verification_code", "statement", "ledger_head", "issued_at")


admin.site.register([LevelAward, BadgeAward, LeaderboardSnapshot])
