from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ContributionViewSet, LedgerVerificationView, LedgerViewSet

router = DefaultRouter()
router.register("ledger", LedgerViewSet, basename="ledger")
router.register("", ContributionViewSet, basename="contribution")

urlpatterns = [
    path("ledger/verify/", LedgerVerificationView.as_view(), name="ledger-verify"),
    path("", include(router.urls)),
]
