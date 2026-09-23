"""
Create the founding account: a real student who is also a platform steward.

FORGE is student-led, so the person who administers it is not a separate
administrator persona -- they are a member with a portfolio, a programme and a
public slug, who also holds the standing roles needed to run the platform.
Creating them through this command rather than `createsuperuser` means the
account gets its programme, its verified status and its role grants, and each
grant is recorded with a grantor like any other.

    python manage.py bootstrap_admin \\
        --email st02353422025@students.ouk.ac.ke \\
        --name "John Ouma" \\
        --programme BSC-CSDF \\
        --year 3
"""

from __future__ import annotations

import secrets
import string

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from forge.accounts.models import Programme, RoleGrant, User
from forge.accounts.services import suggest_public_slug

# Everything needed to run the platform end to end: review proposals, mentor,
# moderate, and grant roles to other people.
FOUNDING_ROLES = [
    RoleGrant.Role.FACULTY_ADVISOR,
    RoleGrant.Role.PLATFORM_MAINTAINER,
    RoleGrant.Role.MENTOR,
    RoleGrant.Role.COMMUNITY_LEAD,
    RoleGrant.Role.MODERATOR,
]


def strong_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = "Create or update the founding student-administrator account."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--programme", help="Programme code, e.g. BSC-CSDF")
        parser.add_argument("--year", type=int, default=None)
        parser.add_argument("--slug", default="")
        parser.add_argument("--recovery-email", default="")
        parser.add_argument("--password", default="",
                            help="Leave blank to have one generated and printed.")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].lower().strip()
        if not User.is_university_email(email):
            raise CommandError(
                f"{email} is not on a University domain. Add its domain to "
                f"UNIVERSITY_EMAIL_DOMAINS first, or use a University address."
            )

        programme = None
        if options["programme"]:
            programme = Programme.objects.filter(code=options["programme"]).first()
            if programme is None:
                codes = ", ".join(Programme.objects.values_list("code", flat=True)[:20])
                raise CommandError(
                    f"No programme with code {options['programme']!r}. "
                    f"Run seed_reference_data first. Known codes: {codes}"
                )

        password = options["password"] or strong_password()
        generated = not options["password"]

        user = User.objects.filter(email=email).first()
        created = user is None
        if created:
            user = User(email=email)

        user.full_name = options["name"].strip()
        user.public_slug = (options["slug"] or user.public_slug
                            or suggest_public_slug(options["name"]))
        user.recovery_email = options["recovery_email"].lower().strip()
        user.kind = User.Kind.STUDENT
        user.status = User.Status.ACTIVE
        user.programme = programme or user.programme
        user.school = programme.school if programme else user.school
        user.year_of_study = options["year"] or user.year_of_study
        user.email_verified_at = user.email_verified_at or timezone.now()
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save()

        for role in FOUNDING_ROLES:
            RoleGrant.objects.get_or_create(
                user=user, role=role, discipline_area=None, revoked_at=None,
                defaults={"granted_by": user,
                          "note": "Founding account, created at bootstrap."},
            )

        self.stdout.write(self.style.SUCCESS(
            f"\n{'Created' if created else 'Updated'} founding account\n"))
        self.stdout.write(f"  Name        {user.full_name}")
        self.stdout.write(f"  Email       {user.email}")
        self.stdout.write(f"  Portfolio   /p/{user.public_slug}")
        self.stdout.write(f"  Programme   {user.programme or '(none)'}")
        self.stdout.write(f"  Roles       {', '.join(sorted(user.role_names))}")
        self.stdout.write("  Superuser   yes")

        if generated:
            self.stdout.write(self.style.WARNING(
                f"\n  Password    {password}\n"))
            self.stdout.write(
                "  This was generated and is shown once. Change it after first "
                "sign-in at PATCH /api/v1/accounts/me/password/, or from the "
                "admin.")

        if not user.recovery_email:
            self.stdout.write(self.style.WARNING(
                "\n  No recovery address on file. A University address stops "
                "working at graduation, and without a recovery address this "
                "account loses access to its own portfolio. Set one at "
                "POST /api/v1/accounts/me/recovery-email/."))
