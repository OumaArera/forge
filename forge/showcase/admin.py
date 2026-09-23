from django.contrib import admin

from .models import ShowcaseEntry, ShowcaseImage


class ShowcaseImageInline(admin.TabularInline):
    model = ShowcaseImage
    extra = 0


@admin.register(ShowcaseEntry)
class ShowcaseEntryAdmin(admin.ModelAdmin):
    list_display = ("headline", "project", "is_published", "is_featured",
                    "published_at", "view_count")
    list_filter = ("is_published", "is_featured")
    search_fields = ("headline", "what_we_built")
    inlines = [ShowcaseImageInline]
    actions = ["feature", "unfeature"]

    @admin.action(description="Feature on the showcase")
    def feature(self, request, queryset):
        queryset.update(is_featured=True)

    @admin.action(description="Remove from featured")
    def unfeature(self, request, queryset):
        queryset.update(is_featured=False)
