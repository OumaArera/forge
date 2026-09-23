from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ShowcaseViewSet

router = DefaultRouter()
router.register("", ShowcaseViewSet, basename="showcase")

urlpatterns = [path("", include(router.urls))]
