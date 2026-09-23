"""
Portfolio exports.

The portfolio itself has no table: it is a view over projects, contributions,
the ledger and recognition. What is stored here is a record of each export --
what was exported, when, and the digest of the document that was produced.

That record exists so that a signature can be checked against what the
platform actually issued, and so that a member can see every export of their
own data that has been taken.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from forge.common.models import BaseModel


class PortfolioExport(BaseModel):
    class Format(models.TextChoices):
        JSON = "json", "Signed JSON"
        DATA_REQUEST = "data_request", "Full personal data export"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="portfolio_exports")
    export_format = models.CharField(max_length=16, choices=Format.choices,
                                     default=Format.JSON)
    document_digest = models.CharField(max_length=64,
                                       help_text="SHA-256 of the exact document issued.")
    signature = models.TextField(blank=True)
    key_id = models.CharField(max_length=64, blank=True)
    ledger_head = models.CharField(max_length=64, blank=True)
    entry_count = models.PositiveIntegerField(default=0)
    issued_at = models.DateTimeField(default=timezone.now)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL,
                                     related_name="portfolio_exports_requested")

    class Meta:
        ordering = ["-issued_at"]
        indexes = [models.Index(fields=["document_digest"])]

    def __str__(self) -> str:
        return f"{self.user.display_name} {self.export_format} {self.issued_at:%Y-%m-%d}"
