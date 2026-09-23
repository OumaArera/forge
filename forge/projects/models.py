"""
Projects: proposal, review, team formation, delivery.

The seven-stage lifecycle in the concept proposal is modelled here as an
explicit state machine rather than as a set of booleans. The reason is that
the stages carry rules -- you cannot recruit onto a project nobody has
approved, and you cannot claim recognition for a project that was never
delivered -- and rules scattered across views are rules that get forgotten.
`Project.TRANSITIONS` is the single statement of what may follow what.

The stage numbering in `Stage` maps one-to-one onto the table in section 9 of
the proposal, so that a reader can hold both documents open at once.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

from forge.accounts.models import DisciplineArea, School, Skill
from forge.common.fields import AutoSlugField, validate_no_html
from forge.common.models import BaseModel, SoftDeleteModel, TimeStampedModel


class ProjectQuerySet(models.QuerySet):
    def visible_to(self, user):
        """
        What a given member may see.

        Drafts and declined proposals are private to their author and to
        reviewers. Everything from approval onwards is visible to the
        University community, because a project nobody can see cannot attract
        the teammate it needs.
        """
        if user is None or not user.is_authenticated:
            return self.filter(status__in=Project.PUBLIC_STATUSES, is_listed=True)
        if user.is_superuser or user.can_review_proposals:
            return self
        return self.filter(
            Q(status__in=Project.PUBLIC_STATUSES)
            | Q(lead=user)
            | Q(memberships__user=user, memberships__left_at__isnull=True)
        ).distinct()

    def recruiting(self):
        return self.filter(status=Project.Status.RECRUITING)

    def active(self):
        return self.filter(status__in=Project.ACTIVE_STATUSES)

    def stale(self, days: int | None = None):
        days = days or settings.FORGE_POLICY["PROJECT_STALE_AFTER_DAYS"]
        cutoff = timezone.now() - timedelta(days=days)
        return self.active().filter(last_activity_at__lt=cutoff)

    def with_team_size(self):
        return self.annotate(
            team_size=Count("memberships", filter=Q(memberships__left_at__isnull=True),
                            distinct=True)
        )


class Project(BaseModel, SoftDeleteModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted for review"
        UNDER_REVIEW = "under_review", "Under review"
        RETURNED = "returned", "Returned for revision"
        DECLINED = "declined", "Declined"
        RECRUITING = "recruiting", "Recruiting a team"
        BUILDING = "building", "In build"
        IN_REVIEW = "in_review", "In review and testing"
        DOCUMENTING = "documenting", "Documenting and demonstrating"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"
        ABANDONED = "abandoned", "Abandoned"

    # Stage numbers as printed in section 9 of the concept proposal.
    STAGE_OF_STATUS = {
        Status.DRAFT: 1, Status.SUBMITTED: 1, Status.UNDER_REVIEW: 2,
        Status.RETURNED: 2, Status.DECLINED: 2, Status.RECRUITING: 3,
        Status.BUILDING: 4, Status.IN_REVIEW: 5, Status.DOCUMENTING: 6,
        Status.COMPLETED: 7, Status.ARCHIVED: 7, Status.ABANDONED: 0,
    }

    PUBLIC_STATUSES = [
        Status.RECRUITING, Status.BUILDING, Status.IN_REVIEW,
        Status.DOCUMENTING, Status.COMPLETED, Status.ARCHIVED,
    ]
    ACTIVE_STATUSES = [
        Status.RECRUITING, Status.BUILDING, Status.IN_REVIEW, Status.DOCUMENTING,
    ]

    # The permitted moves. Anything not listed here cannot happen, which is
    # the point: a reviewer cannot mark a proposal complete, and a lead cannot
    # skip review and start recruiting.
    TRANSITIONS: dict[str, tuple[str, ...]] = {
        Status.DRAFT: (Status.SUBMITTED,),
        Status.SUBMITTED: (Status.UNDER_REVIEW, Status.DRAFT),
        Status.UNDER_REVIEW: (Status.RECRUITING, Status.RETURNED, Status.DECLINED),
        Status.RETURNED: (Status.SUBMITTED, Status.ARCHIVED),
        Status.DECLINED: (Status.DRAFT,),
        Status.RECRUITING: (Status.BUILDING, Status.ABANDONED, Status.ARCHIVED),
        Status.BUILDING: (Status.IN_REVIEW, Status.RECRUITING, Status.ABANDONED),
        Status.IN_REVIEW: (Status.DOCUMENTING, Status.BUILDING),
        Status.DOCUMENTING: (Status.COMPLETED, Status.IN_REVIEW),
        Status.COMPLETED: (Status.ARCHIVED,),
        Status.ABANDONED: (Status.RECRUITING, Status.ARCHIVED),
        Status.ARCHIVED: (),
    }

    class Visibility(models.TextChoices):
        UNIVERSITY = "university", "Visible across the University"
        PUBLIC = "public", "Visible to anyone, including employers"

    # -- the proposal (stage 1) --------------------------------------------
    title = models.CharField(max_length=140, validators=[validate_no_html])
    slug = AutoSlugField(populate_from="title", max_length=160)
    summary = models.CharField(
        max_length=300, validators=[validate_no_html],
        help_text="One or two sentences. This is what appears in listings.",
    )
    problem_statement = models.TextField(
        max_length=4000, validators=[validate_no_html],
        help_text="What problem does this address, and for whom?",
    )
    objectives = models.TextField(
        max_length=4000, validators=[validate_no_html],
        help_text="What will exist at the end that does not exist now? Be concrete: "
                  "these are the objectives your delivery will be reviewed against.",
    )
    discipline_areas = models.ManyToManyField(DisciplineArea, related_name="projects")
    lead = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name="projects_led")

    starts_on = models.DateField(null=True, blank=True)
    target_completion_on = models.DateField(
        null=True, blank=True,
        help_text="An indicative date. Nothing punishes you for missing it; it "
                  "exists so that a teammate knows what they are agreeing to.",
    )
    effort_hours_per_week = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(40)],
        help_text="Expected of each team member. Most FORGE members are studying "
                  "at a distance and many are in employment -- say honestly what "
                  "this will cost someone's week.",
    )

    # -- state --------------------------------------------------------------
    status = models.CharField(max_length=16, choices=Status.choices,
                              default=Status.DRAFT, db_index=True)
    visibility = models.CharField(max_length=12, choices=Visibility.choices,
                                  default=Visibility.UNIVERSITY)
    is_listed = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)

    # -- openness (FORGE Open) ---------------------------------------------
    is_open_source = models.BooleanField(
        default=False,
        help_text="Releasing work openly is encouraged and never required. A "
                  "member who intends to commercialise their work keeps that right.",
    )
    licence = models.CharField(
        max_length=40, blank=True,
        help_text="For example MIT, Apache-2.0, CC-BY-4.0. Required if the project "
                  "is marked open.",
    )
    repository_url = models.URLField(blank=True, validators=[URLValidator(schemes=["https"])])

    # -- ownership (section 12) --------------------------------------------
    ownership_agreed_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the team recorded how ownership of the work is shared. "
                  "Agreed at the outset, not at the point of success.",
    )
    ownership_terms = models.TextField(
        blank=True, max_length=2000, validators=[validate_no_html],
        help_text="How the team has agreed to share ownership of what they create.",
    )

    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="projects_mentored",
        help_text="The mentor who reviews delivery and countersigns contributions.",
    )

    objects = ProjectQuerySet.as_manager()
    all_objects = models.Manager.from_queryset(ProjectQuerySet)()

    class Meta:
        ordering = ["-last_activity_at"]
        indexes = [
            models.Index(fields=["status", "-last_activity_at"]),
            models.Index(fields=["lead", "status"]),
        ]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        super().clean()
        if self.is_open_source and not self.licence:
            raise ValidationError({
                "licence": "Name a licence if the project is released openly. "
                           "Work published without one is not usable by anyone."
            })
        if self.starts_on and self.target_completion_on:
            if self.target_completion_on < self.starts_on:
                raise ValidationError({
                    "target_completion_on": "The target date is before the start date."
                })

    # -- derived ------------------------------------------------------------

    @property
    def stage(self) -> int:
        return self.STAGE_OF_STATUS.get(self.status, 0)

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_stale(self) -> bool:
        cutoff = timedelta(days=settings.FORGE_POLICY["PROJECT_STALE_AFTER_DAYS"])
        return self.is_active and (timezone.now() - self.last_activity_at) > cutoff

    def can_transition_to(self, status: str) -> bool:
        return status in self.TRANSITIONS.get(self.status, ())

    @property
    def active_members(self):
        return self.memberships.filter(left_at__isnull=True).select_related("user", "role")

    @property
    def school_spread(self) -> int:
        """
        How many schools the active team is drawn from.

        Surfaced in listings because a cross-disciplinary team is the thing
        the platform exists to make ordinary, and what gets counted gets
        noticed. It carries no score and no reward -- a Nursing project
        staffed entirely by Nursing students is not a lesser project.
        """
        return (
            self.memberships.filter(left_at__isnull=True, user__school__isnull=False)
            .values("user__school").distinct().count()
        )

    @property
    def is_cross_disciplinary(self) -> bool:
        return self.school_spread > 1

    def touch_activity(self) -> None:
        now = timezone.now()
        type(self).all_objects.filter(pk=self.pk).update(last_activity_at=now)
        self.last_activity_at = now

    def is_member(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return self.memberships.filter(user=user, left_at__isnull=True).exists()

    def is_lead(self, user) -> bool:
        return bool(user and user.is_authenticated and self.lead_id == user.id)

    def may_manage(self, user) -> bool:
        return bool(
            user and user.is_authenticated
            and (self.lead_id == user.id or user.is_superuser
                 or (self.mentor_id and self.mentor_id == user.id))
        )


class ProjectRole(BaseModel):
    """
    An advertised position on a project.

    Roles are the unit of team formation: a student applies to a role, not to
    a project in the abstract. That forces the lead to think about what the
    work actually needs before recruiting, and it gives the applicant
    something specific to say yes to.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="roles")
    title = models.CharField(max_length=100, validators=[validate_no_html])
    description = models.TextField(max_length=2000, validators=[validate_no_html])
    required_skills = models.ManyToManyField(Skill, blank=True, related_name="required_by_roles")
    slots = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1),
                                                                    MaxValueValidator(20)])
    is_open = models.BooleanField(default=True)
    open_to_beginners = models.BooleanField(
        default=False,
        help_text="Marks this as a role a first-year with no track record can take. "
                  "Every project is encouraged to carry at least one.",
    )
    preferred_school = models.ForeignKey(School, null=True, blank=True,
                                         on_delete=models.SET_NULL,
                                         related_name="preferred_roles")

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.title} on {self.project.title}"

    @property
    def filled_slots(self) -> int:
        return self.memberships.filter(left_at__isnull=True).count()

    @property
    def has_vacancy(self) -> bool:
        return self.is_open and self.filled_slots < self.slots


class Application(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="applications")
    role = models.ForeignKey(ProjectRole, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="applications")
    statement = models.TextField(
        max_length=1500, validators=[validate_no_html],
        help_text="Why this role, and what you would bring to it. Two paragraphs "
                  "is plenty.",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING,
                              db_index=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="applications_decided")
    decision_note = models.TextField(
        blank=True, max_length=1000, validators=[validate_no_html],
        help_text="Required when declining. A student who is turned down without "
                  "a reason learns nothing and is less likely to apply again.",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "applicant"],
                condition=Q(status__in=["pending", "accepted"]),
                name="uniq_live_application_per_role",
            )
        ]

    def __str__(self) -> str:
        return f"{self.applicant.display_name} -> {self.role.title}"


class Membership(TimeStampedModel):
    """
    Someone's place on a project team, including when they left.

    Departures are recorded, not erased. A member who did three weeks of real
    work and then had to stop keeps the evidence of those three weeks; and a
    team that lost half its people has an honest record of why delivery
    slipped.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="memberships")
    role = models.ForeignKey(ProjectRole, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="memberships")
    is_lead = models.BooleanField(default=False)
    understudy_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="understudies",
        help_text="The member this person is shadowing, so that the role survives "
                  "their departure. The proposal commits every leadership role to "
                  "carrying an identified understudy; this is where that is recorded.",
    )
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    left_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"],
                condition=Q(left_at__isnull=True),
                name="uniq_active_membership",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.display_name} on {self.project.title}"

    @property
    def is_active(self) -> bool:
        return self.left_at is None

    @property
    def days_served(self) -> int:
        end = self.left_at or timezone.now()
        return max((end - self.joined_at).days, 0)


class ProjectReview(BaseModel):
    """
    The stage-two gate.

    Section 9 of the proposal asks a reviewer to check that the scope is
    realistic, lawful, ethical and non-duplicative. Those are four separate
    judgements, so they are four separate fields: a reviewer who has to tick
    each one individually is a reviewer who has actually considered each one.
    """

    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        RETURNED = "returned", "Returned for revision"
        DECLINED = "declined", "Declined"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name="project_reviews")
    decision = models.CharField(max_length=12, choices=Decision.choices)

    scope_is_realistic = models.BooleanField(default=True)
    is_lawful_and_ethical = models.BooleanField(default=True)
    is_not_duplicative = models.BooleanField(default=True)
    has_clear_objectives = models.BooleanField(default=True)

    reasons = models.TextField(
        max_length=3000, validators=[validate_no_html],
        help_text="Required for every decision, including approval. A proposal "
                  "declined without reasons teaches the student nothing.",
    )
    suggested_mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="suggested_for_projects",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_decision_display()} by {self.reviewer.display_name}"

    def clean(self):
        super().clean()
        if not self.reasons.strip():
            raise ValidationError({"reasons": "Give reasons for the decision."})
        if self.decision == self.Decision.APPROVED and not all(
            [self.scope_is_realistic, self.is_lawful_and_ethical,
             self.is_not_duplicative, self.has_clear_objectives]
        ):
            raise ValidationError(
                "A proposal cannot be approved while one of the four checks is "
                "unmet. Return it for revision instead."
            )


class StageTransition(BaseModel):
    """An append-style record of every stage change, with who and why."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="transitions")
    from_status = models.CharField(max_length=16, choices=Project.Status.choices)
    to_status = models.CharField(max_length=16, choices=Project.Status.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="project_transitions")
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.project.title}: {self.from_status} -> {self.to_status}"
