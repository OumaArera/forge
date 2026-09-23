from django.urls import path

from .views import (
    MyPortfolioExportView,
    PublicPortfolioView,
    VerificationKeyView,
    VerifyExportView,
)

urlpatterns = [
    path("export/", MyPortfolioExportView.as_view(), name="portfolio-export"),
    path("verify/", VerifyExportView.as_view(), name="portfolio-verify"),
    path("verification-key/", VerificationKeyView.as_view(), name="portfolio-key"),
    path("<slug:slug>/", PublicPortfolioView.as_view(), name="public-portfolio"),
]
