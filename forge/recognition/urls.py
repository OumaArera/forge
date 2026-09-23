from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BadgeViewSet,
    CertificatePDFView,
    CertificateVerificationView,
    CertificateViewSet,
    LeaderboardViewSet,
    LevelViewSet,
    StandingViewSet,
)

router = DefaultRouter()
router.register("levels", LevelViewSet, basename="level")
router.register("badges", BadgeViewSet, basename="badge")
router.register("leaderboards", LeaderboardViewSet, basename="leaderboard")
router.register("certificates", CertificateViewSet, basename="certificate")
router.register("standings", StandingViewSet, basename="standing")

urlpatterns = [
    path("certificates/verify/<str:code>/", CertificateVerificationView.as_view(),
         name="certificate-verify"),
    path("certificates/<str:code>/pdf/", CertificatePDFView.as_view(),
         name="certificate-pdf"),
    path("", include(router.urls)),
]
