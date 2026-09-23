from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AcceptableUseViewSet, ReportViewSet

router = DefaultRouter()
router.register("reports", ReportViewSet, basename="report")
router.register("acceptable-use", AcceptableUseViewSet, basename="acceptable-use")

urlpatterns = [path("", include(router.urls))]
