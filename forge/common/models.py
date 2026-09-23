"""
Abstract base models used across FORGE.

Two conventions are applied everywhere and are worth stating once:

1. Primary keys are UUIDs. Identifiers appear in portfolio URLs that students
   will paste into job applications, and a sequential integer would leak how
   many students and projects the platform has. It would also make one
   student's record trivially guessable from another's.

2. Almost nothing is hard-deleted. A contribution record that vanished would
   destroy the evidence the whole platform exists to accumulate. Deletion is
   a state, not a DELETE, except where a student exercises their right to
   erasure under the Data Protection Act, 2019 -- which is handled explicitly
   in forge.accounts.services.erase_user.
"""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Records when a row was created and last touched."""

    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager hides soft-deleted rows; `all_objects` shows everything."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_reason = models.CharField(max_length=255, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, reason: str = ""):
        self.deleted_at = timezone.now()
        self.deleted_reason = reason
        self.save(update_fields=["deleted_at", "deleted_reason", "updated_at"])

    def restore(self):
        self.deleted_at = None
        self.deleted_reason = ""
        self.save(update_fields=["deleted_at", "deleted_reason", "updated_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class ImmutableModel(models.Model):
    """
    A row that may be written once and never altered.

    Used for the contribution ledger, attestations and the audit log. These
    are the records that make a FORGE portfolio worth believing; if they were
    editable in the ordinary way, the two-party confirmation described in the
    concept proposal would be decoration rather than a control.

    `save()` on an existing instance raises. Where a genuine correction is
    needed, the pattern is to append a reversing entry, never to edit history.
    """

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ImmutableRecordError(
                f"{type(self).__name__} is append-only and cannot be modified. "
                "Append a correcting record instead."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableRecordError(
            f"{type(self).__name__} is append-only and cannot be deleted."
        )


class ImmutableRecordError(Exception):
    """Raised when code attempts to alter an append-only record."""


# EmailLog lives in its own module because it is operational rather than
# domain data, but Django only discovers models imported from models.py.
from .models_mail import EmailLog  # noqa: E402,F401
