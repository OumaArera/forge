from django.contrib import admin

from .models import Post, Space, Thread, Vote


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "discipline_area", "display_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ("title", "space", "kind", "author", "reply_count", "is_resolved",
                    "is_locked", "last_activity_at")
    list_filter = ("kind", "space", "is_locked", "is_resolved")
    search_fields = ("title", "body")
    actions = ["lock", "unlock"]

    @admin.action(description="Lock selected threads")
    def lock(self, request, queryset):
        queryset.update(is_locked=True)

    @admin.action(description="Unlock selected threads")
    def unlock(self, request, queryset):
        queryset.update(is_locked=False)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("author_name", "thread", "vote_score", "created_at", "deleted_at")
    search_fields = ("body", "author_name")
    list_filter = ("deleted_at",)


admin.site.register(Vote)
