from django.contrib import admin

from .models import MentorProfile, MentorshipRequest, OfficeHour, OfficeHourBooking


@admin.register(MentorProfile)
class MentorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "availability", "capacity", "load", "is_alumnus",
                    "organisation")
    list_filter = ("availability", "is_alumnus")
    search_fields = ("user__full_name", "headline", "organisation")
    filter_horizontal = ("expertise", "discipline_areas")

    @admin.display(description="Current load")
    def load(self, obj) -> str:
        return f"{obj.current_load}/{obj.capacity}"


@admin.register(MentorshipRequest)
class MentorshipRequestAdmin(admin.ModelAdmin):
    list_display = ("requester", "mentor", "project", "status", "created_at")
    list_filter = ("status",)


admin.site.register([OfficeHour, OfficeHourBooking])
