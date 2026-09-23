"""
Mentorship: capacity, matching and requests.

The proposal promises light-touch mentorship from volunteer academic staff
and alumni, and is explicit that no member of staff is required to mentor.
Everything here follows from taking that seriously.

`capacity` is the important field. The predictable failure of a volunteer
mentoring scheme is that three willing lecturers get matched to forty
students, burn out in a trimester, and the scheme acquires a reputation that
outlives the fix. A mentor states what they can carry, and the platform will
not exceed it.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from forge.common.fields import validate_no_html
from forge.common.models import BaseModel


class MentorProfile(BaseModel):
    class Availability(models.TextChoices):
        OPEN = "open", "Accepting requests"
        LIMITED = "limited", "At capacity"
        PAUSED = "paused", "Not available at the moment"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="mentor_profile")
    headline = models.CharField(max_length=160, validators=[validate_no_html])
    about = models.TextField(max_length=2000, validators=[validate_no_html])
    expertise = models.ManyToManyField("accounts.Skill", blank=True,
                                        related_name="mentors")
    discipline_areas = models.ManyToManyField("accounts.DisciplineArea", blank=True,
                                               related_name="mentors")
    capacity = models.PositiveSmallIntegerField(
        default=2, validators=[MinValueValidator(0), MaxValueValidator(20)],
        help_text="How many projects you are willing to mentor at once. Set this "
                  "honestly and low. Nobody is served by a mentor who has agreed "
                  "to more than they can do.",
    )
    availability = models.CharField(max_length=10, choices=Availability.choices,
                                    default=Availability.OPEN)
    hours_per_month = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(200)],
        help_text="Indicative. Shown to students so they ask for a realistic amount.",
    )
    is_alumnus = models.BooleanField(default=False)
    organisation = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["user__full_name"]

    def __str__(self) -> str:
        return f"{self.user.display_name} (mentor)"

    @property
    def current_load(self) -> int:
        from forge.projects.models import Project

        return Project.objects.filter(
            mentor=self.user, status__in=Project.ACTIVE_STATUSES
        ).count()

    @property
    def has_capacity(self) -> bool:
        return (self.availability == self.Availability.OPEN
                and self.current_load < self.capacity)


class MentorshipRequest(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"
        WITHDRAWN = "withdrawn", "Withdrawn"

    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="mentorship_requests")
    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="mentorship_requests_received")
    project = models.ForeignKey("projects.Project", null=True, blank=True,
                                on_delete=models.CASCADE, related_name="mentorship_requests")
    message = models.TextField(
        max_length=1500, validators=[validate_no_html],
        help_text="What you are working on and what you would like help with. "
                  "A specific ask gets a reply; 'be my mentor' usually does not.",
    )
    status = models.CharField(max_length=12, choices=Status.choices,
                              default=Status.PENDING, db_index=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    response = models.TextField(blank=True, max_length=1000, validators=[validate_no_html])
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Requests lapse rather than sitting unanswered forever. A student "
                  "left waiting with no answer concludes the platform is dead.",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "mentor", "project"],
                condition=models.Q(status="pending"),
                name="uniq_pending_mentorship_request",
            )
        ]

    def __str__(self) -> str:
        return f"{self.requester.display_name} -> {self.mentor.display_name}"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at < timezone.now()
                    and self.status == self.Status.PENDING)


class OfficeHour(BaseModel):
    """
    A published slot where a mentor is available.

    Included because the hardest part of distance mentoring is not willingness
    but coordination, and a published slot removes an entire round of
    scheduling email.
    """

    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="office_hours")
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    capacity = models.PositiveSmallIntegerField(default=1)
    topic = models.CharField(max_length=200, blank=True, validators=[validate_no_html])
    joining_url = models.URLField(
        blank=True,
        help_text="Shared with attendees only, once they have booked.",
    )
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self) -> str:
        return f"{self.mentor.display_name} at {self.starts_at:%d %b %H:%M}"

    @property
    def is_full(self) -> bool:
        return self.bookings.filter(cancelled_at__isnull=True).count() >= self.capacity


class OfficeHourBooking(BaseModel):
    office_hour = models.ForeignKey(OfficeHour, on_delete=models.CASCADE,
                                    related_name="bookings")
    attendee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="office_hour_bookings")
    question = models.TextField(max_length=1000, blank=True, validators=[validate_no_html])
    cancelled_at = models.DateTimeField(null=True, blank=True)
    attended = models.BooleanField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["office_hour", "attendee"],
                condition=models.Q(cancelled_at__isnull=True),
                name="uniq_office_hour_booking",
            )
        ]
