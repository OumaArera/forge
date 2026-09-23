from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MilestoneViewSet, ProgressUpdateViewSet, TaskViewSet

router = DefaultRouter()
router.register("milestones", MilestoneViewSet, basename="milestone")
router.register("tasks", TaskViewSet, basename="task")
router.register("progress-updates", ProgressUpdateViewSet, basename="progress-update")

urlpatterns = [path("", include(router.urls))]
