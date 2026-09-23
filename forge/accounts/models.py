"""
Identity for FORGE.

Three decisions in this module are worth reading before changing anything.

**Data minimisation.** The concept proposal commits the platform to collecting
the minimum necessary: name, University email, programme and year of study,
plus whatever a student voluntarily adds to a portfolio. There is deliberately
no field here for a national identification number, a date of birth, a postal
address or any financial detail, and none should be added without the Advisory
Committee agreeing in writing. Under the Data Protection Act, 2019 the easiest
data to protect is data never collected.

**Portfolio durability.** A student's FORGE record is meant to be shown to an
employer -- including after graduation, which is precisely when the University
email address stops working. So the account is keyed on an internal UUID, the
public record lives at a stable slug the student chooses, and every account
carries a personal recovery email that survives deprovisioning. An account
whose University address is withdrawn becomes an ALUMNUS: it can still sign in
via the recovery address and still serve its portfolio, but it can no longer
join new projects until re-verified.

**Roles are grants, not attributes.** A community lead holds the role for a
trimester, not forever. Roles are therefore rows with a grantor and an expiry,
which also means the platform can answer "who made this person a moderator,
and when" -- a question that always gets asked eventually.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property

from forge.common.models import BaseModel, TimeStampedModel

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


class School(BaseModel):
    """A school of the University. Seeded from the University's own list."""

    name = models.CharField(max_length=160, unique=True)
    code = models.CharField(max_length=16, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Programme(BaseModel):
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="programmes")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=24, unique=True)
    LEVEL_CHOICES = [
        ("certificate", "Certificate"),
        ("diploma", "Diploma"),
        ("undergraduate", "Undergraduate"),
        ("postgraduate", "Postgraduate"),
        ("doctoral", "Doctoral"),
    ]
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="undergraduate")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["school__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_programme_per_school")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.school.code})"


class DisciplineArea(BaseModel):
    """
    A broad field of work, used for project tagging, community spaces and --
    importantly -- separate leaderboards.

    This is intentionally not the same thing as a School. A project on digital
    learning materials for a rural clinic is Health and Education at once, and
    the students on it may come from four different schools. Tying recognition
    to School would have made cross-disciplinary teams invisible in exactly
    the place the platform most wants to celebrate them.
    """

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name


class Skill(BaseModel):
    """
    A tag on the shared skill vocabulary.

    Students propose skills and moderators promote them to `is_approved`. An
    uncontrolled free-text tag cloud makes role matching useless within a
    trimester; a fully closed vocabulary set by staff goes stale just as fast.
    """

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    discipline_areas = models.ManyToManyField(DisciplineArea, blank=True, related_name="skills")
    is_approved = models.BooleanField(default=False)
    usage_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-usage_count", "name"]

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("status", User.Status.ACTIVE)
        extra.setdefault("kind", User.Kind.STAFF)
        extra.setdefault("email_verified_at", timezone.now())
        if extra["is_staff"] is not True or extra["is_superuser"] is not True:
            raise ValueError("A superuser must have is_staff and is_superuser set.")
        return self._create_user(email, password, **extra)


slug_validator = RegexValidator(
    r"^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$",
    "Use 3 to 40 characters: lowercase letters, numbers and hyphens, not "
    "starting or ending with a hyphen.",
)

RESERVED_SLUGS = {
    "admin", "api", "forge", "ouk", "openuniversity", "staff", "support",
    "help", "about", "login", "logout", "register", "settings", "showcase",
    "projects", "community", "portfolio", "verify", "me", "new", "search",
    "moderation", "recognition", "leaderboard", "docs", "status",
}


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    class Kind(models.TextChoices):
        STUDENT = "student", "Student"
        STAFF = "staff", "Academic or administrative staff"
        ALUMNUS = "alumnus", "Alumnus"
        EXTERNAL = "external", "External mentor or partner"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending email verification"
        ACTIVE = "active", "Active"
        ALUMNUS = "alumnus", "Graduated or deprovisioned"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed at the member's request"

    # -- identity -----------------------------------------------------------
    email = models.EmailField(
        unique=True,
        help_text="University email address. Used to establish that you are a "
                  "genuine member of the University.",
    )
    recovery_email = models.EmailField(
        blank=True,
        help_text="A personal address that will still work after you graduate. "
                  "Without it you will lose access to your portfolio when your "
                  "University address is withdrawn.",
    )
    pending_recovery_email = models.EmailField(
        blank=True,
        help_text="An address that has been submitted but not yet confirmed. Kept "
                  "separate so the interface can say 'we are waiting on you' rather "
                  "than showing nothing and looking broken.",
    )
    full_name = models.CharField(max_length=160)
    preferred_name = models.CharField(max_length=80, blank=True)
    public_slug = models.SlugField(
        max_length=40, unique=True, validators=[slug_validator],
        help_text="The stable address of your public portfolio. Choose carefully: "
                  "changing it breaks links you have already shared.",
    )

    # -- academic context (minimal by policy) -------------------------------
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.STUDENT)
    status = models.CharField(max_length=12, choices=Status.choices,
                              default=Status.PENDING, db_index=True)
    school = models.ForeignKey(School, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="members")
    programme = models.ForeignKey(Programme, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="members")
    year_of_study = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(9)]
    )

    # -- voluntary profile --------------------------------------------------
    headline = models.CharField(max_length=140, blank=True)
    bio = models.TextField(blank=True, max_length=2000)
    location = models.CharField(max_length=80, blank=True,
                                help_text="County or town. Optional, and never finer than that.")
    links = models.JSONField(
        default=dict, blank=True,
        help_text='Optional: {"github": "...", "linkedin": "...", "site": "..."}',
    )
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", null=True, blank=True)
    interests = models.ManyToManyField(DisciplineArea, blank=True,
                                       related_name="interested_members")

    # -- portfolio visibility ----------------------------------------------
    portfolio_is_public = models.BooleanField(
        default=True,
        help_text="A public portfolio is the point of FORGE, but it remains your "
                  "choice. Turning this off hides the public page; it does not "
                  "delete anything.",
    )
    show_email_on_portfolio = models.BooleanField(default=False)

    # -- verification and lifecycle ----------------------------------------
    email_verified_at = models.DateTimeField(null=True, blank=True)
    oidc_subject = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text="Subject claim from University single sign-on, when in use.",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deprovisioned_at = models.DateTimeField(null=True, blank=True)
    accepted_conduct_at = models.DateTimeField(null=True, blank=True)
    accepted_conduct_version = models.CharField(max_length=16, blank=True)
    must_change_password = models.BooleanField(
        default=False,
        help_text="Set when the platform generated the password. The member is held "
                  "at the change-password screen until they choose their own, so a "
                  "credential that has travelled through email does not stay valid.",
    )
    invited_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="invitees",
    )

    # -- Django flags -------------------------------------------------------
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["status", "kind"]),
            models.Index(fields=["last_seen_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"

    # -- validation ---------------------------------------------------------

    def clean(self):
        super().clean()
        self.email = (self.email or "").lower().strip()
        self.recovery_email = (self.recovery_email or "").lower().strip()
        if self.public_slug in RESERVED_SLUGS:
            raise ValidationError({"public_slug": "That address is reserved."})
        if self.recovery_email and self.recovery_email == self.email:
            raise ValidationError({
                "recovery_email": "Use a personal address that will outlast your "
                                  "University account."
            })
        if self.kind == self.Kind.STUDENT and not self.is_university_email(self.email):
            # External mentors and partners are invited explicitly and are
            # exempt; a student account must be on a University domain.
            raise ValidationError({
                "email": "A student account must use a University email address."
            })

    @staticmethod
    def is_university_email(email: str) -> bool:
        domain = (email or "").rsplit("@", 1)[-1].lower()
        return any(
            domain == d.lower() or domain.endswith("." + d.lower())
            for d in settings.UNIVERSITY_EMAIL_DOMAINS
        )

    # -- derived state ------------------------------------------------------

    @property
    def display_name(self) -> str:
        return self.preferred_name or self.full_name

    @property
    def is_verified_member(self) -> bool:
        """May this account act on the platform?"""
        return (
            self.is_active
            and self.status in {self.Status.ACTIVE, self.Status.ALUMNUS}
            and (self.email_verified_at is not None or bool(self.oidc_subject))
        )

    @property
    def may_join_projects(self) -> bool:
        """
        An alumnus keeps their portfolio and may mentor, but does not take up
        a project role that a current student could fill.
        """
        return self.is_verified_member and self.status == self.Status.ACTIVE

    @cached_property
    def active_roles(self):
        now = timezone.now()
        return [
            r for r in self.role_grants.all()
            if r.revoked_at is None and (r.expires_at is None or r.expires_at > now)
        ]

    @cached_property
    def role_names(self) -> set[str]:
        return {r.role for r in self.active_roles}

    def has_role(self, role: str) -> bool:
        return role in self.role_names

    @property
    def can_moderate(self) -> bool:
        return bool(self.role_names & {RoleGrant.Role.MODERATOR,
                                       RoleGrant.Role.COMMUNITY_LEAD,
                                       RoleGrant.Role.FACULTY_ADVISOR})

    @property
    def can_review_proposals(self) -> bool:
        return bool(self.role_names & {RoleGrant.Role.MENTOR,
                                       RoleGrant.Role.COMMUNITY_LEAD,
                                       RoleGrant.Role.FACULTY_ADVISOR})

    @property
    def can_attest_as_mentor(self) -> bool:
        return bool(self.role_names & {RoleGrant.Role.MENTOR,
                                       RoleGrant.Role.FACULTY_ADVISOR})

    def touch_last_seen(self) -> None:
        now = timezone.now()
        # Written at most once a quarter hour: this runs on every request and
        # a write per request would be the platform's busiest query by far.
        if self.last_seen_at and (now - self.last_seen_at) < timedelta(minutes=15):
            return
        type(self).objects.filter(pk=self.pk).update(last_seen_at=now)
        self.last_seen_at = now


class RoleGrant(BaseModel):
    """
    A standing capability held by a member, with a grantor and an expiry.

    Every grant records who made it. When someone asks how a particular
    student came to be able to remove another student's post, the answer is
    a row, not a recollection.
    """

    class Role(models.TextChoices):
        MENTOR = "mentor", "Mentor"
        COMMUNITY_LEAD = "community_lead", "Community lead"
        FACULTY_ADVISOR = "faculty_advisor", "Faculty advisor"
        MODERATOR = "moderator", "Moderator"
        PLATFORM_MAINTAINER = "platform_maintainer", "Platform maintainer"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="role_grants")
    role = models.CharField(max_length=32, choices=Role.choices)
    discipline_area = models.ForeignKey(
        DisciplineArea, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="role_grants",
        help_text="Where the role is scoped to one area, for example a community "
                  "lead for Health.",
    )
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="roles_granted")
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Leave blank for an open-ended grant. Student-held roles should "
                  "normally expire at the end of a trimester and be renewed.",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-granted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "discipline_area"],
                condition=models.Q(revoked_at__isnull=True),
                name="uniq_active_role_grant",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.display_name} as {self.get_role_display()}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and (
            self.expires_at is None or self.expires_at > timezone.now()
        )


class UserSkill(TimeStampedModel):
    """
    A claimed skill, and -- separately -- whether anything on the platform
    backs the claim.

    `evidence_count` is derived from confirmed contributions and cannot be
    set by the member. This is the "evidence before claims" principle made
    mechanical: anyone may say they know Django; the portfolio shows whether
    they have ever shipped anything in it.
    """

    class Proficiency(models.IntegerChoices):
        LEARNING = 1, "Learning"
        WORKING = 2, "Working knowledge"
        STRONG = 3, "Strong"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="holders")
    self_rating = models.PositiveSmallIntegerField(choices=Proficiency.choices,
                                                   default=Proficiency.LEARNING)
    wants_to_learn = models.BooleanField(
        default=False,
        help_text="Marks this as a skill you want to practise. Role matching "
                  "weighs it, so beginners are offered a way in rather than "
                  "only ever being matched to what they already know.",
    )
    evidence_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-evidence_count", "skill__name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "skill"], name="uniq_user_skill")
        ]

    def __str__(self) -> str:
        return f"{self.user.display_name}: {self.skill.name}"


class EmailVerification(BaseModel):
    """
    A single-use verification token.

    Only a hash of the token is stored. If the database is ever exposed, the
    contents do not let anyone verify an address they do not control.
    """

    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Registration"
        RECOVERY_EMAIL = "recovery_email", "Recovery address"
        REVERIFICATION = "reverification", "Annual re-verification"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="verifications")
    purpose = models.CharField(max_length=20, choices=Purpose.choices,
                               default=Purpose.REGISTRATION)
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, db_index=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "purpose", "consumed_at"])]

    @classmethod
    def issue(cls, user, email: str, purpose: str = Purpose.REGISTRATION):
        """Create a verification and return (instance, plaintext_token)."""
        from .services import hash_token  # local import: avoids a cycle

        token = secrets.token_urlsafe(32)
        instance = cls.objects.create(
            user=user,
            purpose=purpose,
            email=email.lower(),
            token_hash=hash_token(token),
            expires_at=timezone.now()
            + timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS),
        )
        return instance, token

    @property
    def is_usable(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now() and self.attempts < 10


class Invitation(BaseModel):
    """
    An invitation to join FORGE.

    The platform is open to any student with a University address, so an
    invitation is not how most people arrive. It exists for the cases the open
    route does not cover: a member of staff who is not a student and therefore
    has no students.ouk.ac.ke address, an alumnus returning to mentor, and an
    external partner. Those accounts bypass the domain check, so each one is
    issued deliberately, by a named person, and the row records who.

    Only a hash of the token is stored, for the same reason as
    EmailVerification: a leaked database must not let anybody accept an
    invitation addressed to somebody else.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    email = models.EmailField(db_index=True)
    full_name = models.CharField(max_length=160, blank=True)
    kind = models.CharField(
        max_length=12, choices=User.Kind.choices, default=User.Kind.STUDENT,
        help_text="What sort of account this creates. Anything other than 'student' "
                  "is exempt from the University domain check, which is the whole "
                  "reason invitations exist.",
    )
    role = models.CharField(
        max_length=32, choices=RoleGrant.Role.choices, blank=True,
        help_text="A standing role granted on acceptance. Optional.",
    )
    discipline_area = models.ForeignKey(
        DisciplineArea, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="invitations",
    )
    message = models.TextField(
        max_length=1000, blank=True,
        help_text="Included in the email. An invitation from a stranger with no "
                  "context reads like spam and gets treated as spam.",
    )
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   on_delete=models.SET_NULL,
                                   related_name="invitations_sent")
    invited_by_name = models.CharField(max_length=160, blank=True)

    token_hash = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.PENDING, db_index=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                      on_delete=models.SET_NULL,
                                      related_name="invitation_used")
    revoked_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.PositiveSmallIntegerField(default=1)
    last_sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(status="pending"),
                name="uniq_pending_invitation_per_email",
            )
        ]

    def __str__(self) -> str:
        return f"{self.email} ({self.get_status_display()})"

    @property
    def role_label(self) -> str:
        return self.get_role_display() if self.role else ""

    @property
    def is_usable(self) -> bool:
        return self.status == self.Status.PENDING and self.expires_at > timezone.now()
