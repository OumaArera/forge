from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AnnouncementViewSet, NotificationPreferenceView, NotificationViewSet

router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("", NotificationViewSet, basename="notification")

urlpatterns = [
    path("preferences/", NotificationPreferenceView.as_view(), name="notification-preferences"),
    path("", include(router.urls)),
]
