from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PostViewSet, SpaceViewSet, ThreadViewSet

router = DefaultRouter()
router.register("spaces", SpaceViewSet, basename="space")
router.register("threads", ThreadViewSet, basename="thread")
router.register("posts", PostViewSet, basename="post")

urlpatterns = [path("", include(router.urls))]
