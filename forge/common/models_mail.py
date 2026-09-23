"""
A record of every message the platform attempted to send.

Kept because "the email never arrived" is otherwise unanswerable. With this,
the question splits into three that each have an answer: did we try, did the
server accept it, and what address did it go to.

No message body is stored. Verification links and generated credentials pass
through here, and a table holding them would be a far better target than the
password hashes it sits next to.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .models import BaseModel


class EmailLog(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Accepted by the mail server"
        FAILED = "failed", "Failed"

    to_address = models.EmailField()
    subject = models.CharField(max_length=200)
    template = models.CharField(max_length=60)
    category = models.CharField(max_length=40, default="general", db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="emails",
        help_text="The member this concerned, where there was one.",
    )
    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.PENDING, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]
        verbose_name = "email log"

    def __str__(self) -> str:
        return f"{self.template} to {self.to_address} ({self.status})"
