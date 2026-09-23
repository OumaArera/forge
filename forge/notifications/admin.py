from django.contrib import admin

from .models import Announcement, Notification, NotificationPreference


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "published_at", "expires_at", "send_email")
    list_filter = ("is_published",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "verb", "category", "summary", "read_at", "created_at")
    list_filter = ("category", "verb")
    search_fields = ("recipient__full_name", "summary")


admin.site.register(NotificationPreference)
