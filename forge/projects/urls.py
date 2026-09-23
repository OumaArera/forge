from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApplicationViewSet, ProjectViewSet, RoleViewSet

router = DefaultRouter()
router.register("applications", ApplicationViewSet, basename="application")
router.register("roles", RoleViewSet, basename="role")
router.register("", ProjectViewSet, basename="project")

urlpatterns = [path("", include(router.urls))]
