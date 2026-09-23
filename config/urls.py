"""Root URL configuration for FORGE."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from forge.common.views import health, readiness

api_v1 = [
    path("accounts/", include("forge.accounts.urls")),
    path("projects/", include("forge.projects.urls")),
    path("workspace/", include("forge.workspace.urls")),
    path("contributions/", include("forge.contributions.urls")),
    path("recognition/", include("forge.recognition.urls")),
    path("community/", include("forge.community.urls")),
    path("showcase/", include("forge.showcase.urls")),
    path("mentorship/", include("forge.mentorship.urls")),
    path("moderation/", include("forge.moderation.urls")),
    path("notifications/", include("forge.notifications.urls")),
    path("portfolio/", include("forge.portfolio.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("healthz/", health, name="health"),
    path("readyz/", readiness, name="readiness"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "FORGE administration"
admin.site.site_title = "FORGE"
admin.site.index_title = "Platform administration"
