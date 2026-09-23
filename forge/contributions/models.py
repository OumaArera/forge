"""
Contributions, attestations and the ledger.

This is the module the rest of FORGE exists to serve. A portfolio is only
worth showing an employer if the claims in it are hard to fabricate, so the
design separates three things that are often conflated:

  Contribution   what someone says they did. Editable while in draft.
  Attestation    what two other people say about that claim. Append-only.
  LedgerEntry    the settled record, written once both attestations are in.
                 Append-only and hash-chained.

The chaining is the part that does the work. Each entry carries the hash of
the entry before it, so altering a historical row invalidates every row after
it. That does not make tampering impossible -- an administrator with database
access could rewrite the whole chain -- but it makes silent tampering
impossible, which is the achievable goal. A portfolio export ships the chain
and its signature together, so a reader can verify both without trusting the
person who handed them the file.

Section 9 of the concept proposal requires confirmation by two independent
parties: the project lead and the mentor. That is enforced in
`services.attest`, not here, because it is a rule about people rather than
about storage.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.utils import timezone

from forge.common.fields import validate_no_html
from forge.common.models import BaseModel, ImmutableModel, UUIDModel


class Dimension(models.TextChoices):
    """
    The kinds of value the platform records.

    Section 10.1 asks for several dimensions rather than a single score, so
    that different kinds of contribution stay visible. Without this, a
    platform quietly becomes a leaderboard for whoever writes the most code,
    and the student who ran the documentation, chased the field data or
    taught three juniors how to use Git appears to have done nothing.
    """

    DELIVERY = "delivery", "Delivery -- work completed against an objective"
    REVIEW = "review", "Review -- checking and improving others' work"
    DOCUMENTATION = "documentation", "Documentation -- writing it down for others"
    MENTORSHIP = "mentorship", "Mentorship -- teaching and supporting others"
    COMMUNITY = "community", "Community -- answering, organising, moderating"
    LEADERSHIP = "leadership", "Leadership -- coordinating a team to a result"
    RESEARCH = "research", "Research -- investigation, field work, analysis"
    DESIGN = "design", "Design -- interface, service or visual design"


class Contribution(BaseModel):
    """
    A claim of work done, awaiting confirmation.

    Contributions are logged as the work happens rather than reconstructed at
    the end -- `occurred_on` is a date the claimant states, and a claim filed
    long after the fact is flagged for the attestors rather than refused,
    since people forget and honest late entries exist.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Awaiting confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        DISPUTED = "disputed", "Disputed"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class AIAssistance(models.TextChoices):
        """
        Disclosure of AI assistance.

        The platform's own principle is evidence before claims, and a
        contribution record is worth nothing if it cannot distinguish work
        someone did from work someone prompted. The response to that is
        disclosure, not prohibition: generative tools are part of how software
        is now written, and a rule that pretended otherwise would simply be
        ignored. What is not acceptable is an undisclosed claim, and an
        attestor who finds undisclosed assistance has grounds to dispute.
        """

        NONE = "none", "No AI assistance"
        ASSISTED = "assisted", "AI-assisted, reviewed and understood by me"
        GENERATED = "generated", "Substantially AI-generated, curated by me"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE,
                                related_name="contributions")
    contributor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="contributions")
    dimension = models.CharField(max_length=16, choices=Dimension.choices, db_index=True)
    description = models.TextField(
        max_length=2000, validators=[validate_no_html],
        help_text="What you did, specifically enough that your lead and mentor "
                  "can recognise it. 'Worked on the backend' is not a contribution "
                  "record; 'built and tested the contribution ledger, including the "
                  "hash chain' is.",
    )
    evidence_url = models.URLField(
        blank=True, validators=[URLValidator(schemes=["https"])],
        help_text="A link to the work itself: a commit, a pull request, a document, "
                  "a recording. Optional but it makes confirmation quick.",
    )
    effort_hours = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("2000"))],
        help_text="Approximate. Used for your own record, not for ranking.",
    )
    occurred_on = models.DateField(default=timezone.localdate)
    milestone = models.ForeignKey("workspace.Milestone", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="contributions")
    skills_used = models.ManyToManyField("accounts.Skill", blank=True,
                                          related_name="contributions")
    ai_assistance = models.CharField(max_length=10, choices=AIAssistance.choices,
                                     default=AIAssistance.NONE)
    ai_assistance_note = models.CharField(max_length=300, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices,
                              default=Status.DRAFT, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-occurred_on", "-created_at"]
        indexes = [
            models.Index(fields=["contributor", "status"]),
            models.Index(fields=["project", "status"]),
            models.Index(fields=["dimension", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.contributor.display_name}: {self.description[:60]}"

    def clean(self):
        super().clean()
        if self.occurred_on and self.occurred_on > timezone.localdate():
            raise ValidationError({"occurred_on": "You cannot log work you have not done yet."})
        if self.ai_assistance != self.AIAssistance.NONE and not self.ai_assistance_note.strip():
            raise ValidationError({
                "ai_assistance_note": "Say briefly what the tool did and what you did. "
                                      "Disclosure without detail is not disclosure."
            })

    @property
    def is_editable(self) -> bool:
        return self.status in {self.Status.DRAFT, self.Status.DISPUTED}

    @property
    def is_late(self) -> bool:
        """Flagged to attestors, not refused. Honest late entries exist."""
        if not self.submitted_at:
            return False
        return (self.submitted_at.date() - self.occurred_on).days > 30

    @property
    def confirmations(self):
        return self.attestations.filter(decision=Attestation.Decision.CONFIRM)

    @property
    def is_fully_attested(self) -> bool:
        required = settings.FORGE_POLICY["REQUIRED_ATTESTATIONS"]
        capacities = set(self.confirmations.values_list("capacity", flat=True))
        return len(capacities) >= required

    def canonical_payload(self) -> dict:
        """
        The settled facts, in a stable shape.

        This is what gets hashed into the ledger, so the ordering and the
        field set must not drift: changing them would invalidate every
        existing chain. If a field ever needs adding, add a new payload
        version rather than editing this one.
        """
        return {
            "v": 1,
            "contribution_id": str(self.id),
            "contributor_id": str(self.contributor_id),
            "project_id": str(self.project_id),
            "project_title": self.project.title,
            "dimension": self.dimension,
            "description": self.description,
            "evidence_url": self.evidence_url,
            "effort_hours": str(self.effort_hours) if self.effort_hours is not None else None,
            "occurred_on": self.occurred_on.isoformat(),
            "ai_assistance": self.ai_assistance,
            "skills": sorted(s.name for s in self.skills_used.all()),
            "attestations": [
                {
                    "attestor_id": str(a.attestor_id),
                    "attestor_name": a.attestor_name,
                    "capacity": a.capacity,
                    "decision": a.decision,
                    "at": a.created_at.isoformat(),
                }
                for a in self.attestations.order_by("created_at")
            ],
        }


class Attestation(UUIDModel, ImmutableModel):
    """
    One person's statement about someone else's claim. Written once.

    `attestor_name` is denormalised on purpose. If the attestor later exercises
    their right to erasure, the fact that a named person in a named capacity
    confirmed this work must survive, or every portfolio that depended on them
    silently loses its backing.
    """

    class Capacity(models.TextChoices):
        LEAD = "lead", "Project lead"
        MENTOR = "mentor", "Mentor"
        PEER = "peer", "Peer reviewer"
        COMMUNITY_LEAD = "community_lead", "Community lead"

    class Decision(models.TextChoices):
        CONFIRM = "confirm", "Confirmed"
        DISPUTE = "dispute", "Disputed"

    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE,
                                     related_name="attestations")
    attestor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                 on_delete=models.SET_NULL, related_name="attestations_given")
    attestor_name = models.CharField(max_length=160)
    capacity = models.CharField(max_length=16, choices=Capacity.choices)
    decision = models.CharField(max_length=8, choices=Decision.choices)
    note = models.TextField(max_length=1000, blank=True, validators=[validate_no_html])
    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["contribution", "capacity"],
                                    name="uniq_attestation_per_capacity"),
        ]

    def __str__(self) -> str:
        return f"{self.attestor_name} ({self.capacity}) {self.decision}"


class LedgerEntry(UUIDModel, ImmutableModel):
    """
    A settled contribution, chained to the one before it.

    The chain is global rather than per-member. A per-member chain would let
    someone with database access rewrite one person's history in isolation; a
    global chain means any alteration breaks verification for every entry that
    followed, including entries belonging to people with no connection to the
    change.

    Verify the whole chain with: python manage.py verify_ledger
    """

    sequence = models.BigIntegerField(unique=True, editable=False)
    contribution = models.OneToOneField(Contribution, on_delete=models.PROTECT,
                                        related_name="ledger_entry")
    contributor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                    on_delete=models.SET_NULL, related_name="ledger_entries")
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT,
                                related_name="ledger_entries")
    dimension = models.CharField(max_length=16, choices=Dimension.choices, db_index=True)
    points = models.PositiveIntegerField(
        default=0,
        help_text="Recognition weight, computed at settlement. Frozen here so "
                  "that a later change to the weighting cannot quietly rewrite "
                  "what someone already earned.",
    )
    payload = models.JSONField(editable=False)
    previous_hash = models.CharField(max_length=64, editable=False)
    entry_hash = models.CharField(max_length=64, unique=True, editable=False)
    recorded_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    GENESIS_HASH = "0" * 64

    class Meta:
        ordering = ["sequence"]
        indexes = [
            models.Index(fields=["contributor", "recorded_at"]),
            models.Index(fields=["project", "dimension"]),
        ]
        verbose_name_plural = "ledger entries"

    def __str__(self) -> str:
        return f"#{self.sequence} {self.entry_hash[:12]}"

    @staticmethod
    def canonical_json(payload: dict) -> str:
        """Stable serialisation. Sorted keys, no incidental whitespace."""
        return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)

    @classmethod
    def compute_hash(cls, *, sequence: int, previous_hash: str, payload: dict,
                     recorded_at, points: int) -> str:
        material = "|".join([
            str(sequence),
            previous_hash,
            cls.canonical_json(payload),
            recorded_at.isoformat(),
            str(points),
        ])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def recompute_hash(self) -> str:
        return self.compute_hash(
            sequence=self.sequence, previous_hash=self.previous_hash,
            payload=self.payload, recorded_at=self.recorded_at, points=self.points,
        )

    @property
    def is_intact(self) -> bool:
        return self.recompute_hash() == self.entry_hash
