"""
Administration for identity.

The Django admin is a large part of why this project is built on Django:
moderation tooling, role management and the data-subject-rights workflow all
need a back office, and building one by hand would have consumed most of a
twelve-week pilot.

Two deliberate restrictions. Passwords are never editable here, and erasure
goes through the service function rather than a delete button, so that the
Data Protection Act path is the same one whether it is exercised through the
API or by the Data Protection Officer.
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    DisciplineArea,
    EmailVerification,
    Programme,
    RoleGrant,
    School,
    Skill,
    User,
    UserSkill,
)
from .services import deprovision, erase_user


class RoleGrantInline(admin.TabularInline):
    model = RoleGrant
    fk_name = "user"
    extra = 0
    fields = ("role", "discipline_area", "granted_by", "granted_at", "expires_at",
              "revoked_at", "note")
    readonly_fields = ("granted_by", "granted_at")


class UserSkillInline(admin.TabularInline):
    model = UserSkill
    extra = 0
    readonly_fields = ("evidence_count",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("full_name", "email", "public_slug", "kind", "status",
                    "school", "verified", "last_seen_at")
    list_filter = ("status", "kind", "school", "is_staff", "portfolio_is_public")
    search_fields = ("full_name", "preferred_name", "email", "public_slug")
    ordering = ("full_name",)
    readonly_fields = ("id", "created_at", "last_seen_at", "email_verified_at",
                       "deprovisioned_at", "last_login")
    inlines = [RoleGrantInline, UserSkillInline]
    actions = ["action_deprovision", "action_erase"]

    fieldsets = (
        ("Identity", {"fields": ("id", "email", "recovery_email", "full_name",
                                 "preferred_name", "public_slug", "password")}),
        ("Academic", {"fields": ("kind", "school", "programme", "year_of_study")}),
        ("Profile", {"fields": ("headline", "bio", "location", "links", "avatar",
                                "interests", "portfolio_is_public",
                                "show_email_on_portfolio")}),
        ("Lifecycle", {"fields": ("status", "email_verified_at", "oidc_subject",
                                  "deprovisioned_at", "last_seen_at",
                                  "accepted_conduct_at", "accepted_conduct_version")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser",
                                    "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "full_name", "public_slug", "password1",
                           "password2")}),
    )
    filter_horizontal = ("groups", "user_permissions", "interests")

    @admin.display(boolean=True, description="Verified")
    def verified(self, obj) -> bool:
        return obj.is_verified_member

    @admin.action(description="Move to alumnus status (graduation / deprovisioning)")
    def action_deprovision(self, request, queryset):
        count = 0
        for user in queryset:
            deprovision(user, reason="admin action")
            count += 1
        self.message_user(
            request,
            f"{count} account(s) moved to alumnus. They keep their portfolios and "
            f"can sign in via their recovery address.",
            messages.SUCCESS,
        )

    @admin.action(description="Erase personal data (Data Protection Act request)")
    def action_erase(self, request, queryset):
        for user in queryset:
            erase_user(user, requested_by=request.user, reason="admin action")
        self.message_user(
            request,
            f"{queryset.count()} account(s) erased. Confirmed contributions remain "
            f"in the ledger pseudonymously so that other members' records stay "
            f"intact -- this is documented in accounts/services.py.",
            messages.WARNING,
        )


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "school", "level", "is_active")
    list_filter = ("school", "level", "is_active")
    search_fields = ("name", "code")


@admin.register(DisciplineArea)
class DisciplineAreaAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "display_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_approved", "usage_count")
    list_filter = ("is_approved",)
    search_fields = ("name",)
    actions = ["approve"]

    @admin.action(description="Approve for the shared vocabulary")
    def approve(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} skill(s) approved.")


@admin.register(RoleGrant)
class RoleGrantAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "discipline_area", "granted_by", "granted_at",
                    "expires_at", "revoked_at")
    list_filter = ("role",)
    search_fields = ("user__full_name", "user__email")
    autocomplete_fields = ("user", "granted_by")


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "email", "expires_at", "consumed_at")
    list_filter = ("purpose",)
    # The token digest is never displayed: showing it would let an
    # administrator complete someone else's verification.
    exclude = ("token_hash",)
    readonly_fields = ("user", "purpose", "email", "expires_at", "consumed_at",
                       "attempts")

    def has_add_permission(self, request):
        return False
