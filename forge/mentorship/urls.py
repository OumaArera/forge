from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MentorshipRequestViewSet, MentorViewSet, OfficeHourViewSet

router = DefaultRouter()
router.register("mentors", MentorViewSet, basename="mentor")
router.register("requests", MentorshipRequestViewSet, basename="mentorship-request")
router.register("office-hours", OfficeHourViewSet, basename="office-hour")

urlpatterns = [path("", include(router.urls))]
