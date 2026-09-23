"""
Populate a development instance with believable data.

Existing only so that the interface can be looked at with something in it. It
refuses to run when DEBUG is off, because a production database with invented
students in it is a database nobody can trust.

    python manage.py seed_demo
    python manage.py seed_demo --wipe     # remove what this command created
"""

from __future__ import annotations

import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from forge.accounts.models import DisciplineArea, Programme, RoleGrant, Skill, User
from forge.community.models import Post, Space, Thread
from forge.contributions.models import Contribution, Dimension
from forge.contributions.services import attest, submit
from forge.projects.models import Project, ProjectReview, ProjectRole
from forge.projects.services import (
    add_member,
    apply_to_role,
    decide_application,
    review_proposal,
    submit_for_review,
    transition,
)
from forge.workspace.models import Milestone, ProgressUpdate, Task

DEMO_DOMAIN = "students.ouk.ac.ke"
DEMO_TAG = "[demo]"

PEOPLE = [
    ("grace.njeri", "Grace Njeri", "BSN", 3),
    ("kevin.otieno", "Kevin Otieno", "BSC-CS", 2),
    ("mary.wanjiru", "Mary Wanjiru", "BSC-DS", 4),
    ("brian.mwangi", "Brian Mwangi", "BED-SCI", 2),
    ("amina.hassan", "Amina Hassan", "BPC", 3),
    ("david.kimani", "David Kimani", "BSC-AGT", 1),
    ("faith.chebet", "Faith Chebet", "BCOM", 3),
]

PROJECTS = [
    {
        "title": "Clinic queue tracker for rural health centres",
        "summary": "Let patients see how long the queue is before they set off.",
        "problem": (
            "Patients at rural health centres travel for hours and then wait without "
            "any idea how long the queue is. Some give up and go home untreated; "
            "others arrive at the worst possible time."
        ),
        "objectives": (
            "A working web tool showing current queue length, trialled at one health "
            "centre for a full month, with a written evaluation of whether it changed "
            "anything."
        ),
        "areas": ["health", "software-and-systems"],
        "roles": [
            ("Backend developer", "Build and run the queue API.",
             ["Django", "PostgreSQL"], 1, False),
            ("Clinical adviser", "Tell us how a clinic queue actually works.",
             ["Clinical assessment"], 1, True),
            ("Field researcher", "Interview patients and staff, write it up.",
             ["Field research"], 1, True),
        ],
        "stage": "building",
    },
    {
        "title": "Soil moisture logging for smallholder farms",
        "summary": "Low-cost sensors and a season of data for two partner farms.",
        "problem": (
            "Smallholder farmers have no record of what worked last season, so every "
            "year's planting decision is made from memory and hearsay."
        ),
        "objectives": (
            "A logger that records soil moisture twice daily, one full season of data "
            "from two partner farms, and a plain-language report each farmer can use."
        ),
        "areas": ["agriculture-and-environment", "data-and-analytics"],
        "roles": [
            ("Data analyst", "Clean and analyse the season's readings.",
             ["Data analysis", "Statistics"], 1, False),
            ("Agronomy lead", "Work with the partner farms.", ["Agronomy"], 1, True),
        ],
        "stage": "recruiting",
    },
    {
        "title": "Accessible learning materials for first-year mathematics",
        "summary": "Rebuild the hardest first-year topics as screen-reader-friendly material.",
        "problem": (
            "First-year mathematics materials are distributed as scanned PDFs, which a "
            "screen reader cannot read at all. Students who rely on one are locked out "
            "of the unit entirely."
        ),
        "objectives": (
            "Three topics rebuilt as accessible HTML with alt text and MathML, checked "
            "against WCAG 2.2 AA, and tested with two students who use a screen reader."
        ),
        "areas": ["education-and-learning", "software-and-systems"],
        "roles": [
            ("Instructional designer", "Restructure the material for the web.",
             ["Curriculum design"], 2, True),
            ("Accessibility reviewer", "Audit against WCAG and test with real users.",
             ["Accessibility"], 1, False),
        ],
        "stage": "completed",
    },
    {
        "title": "Incident response tabletop exercises for student societies",
        "summary": ("Runnable scenarios that teach incident handling without "
                    "touching live systems."),
        "problem": (
            "Students finish a security programme having never run an incident. The "
            "practical exercises that exist all assume infrastructure nobody will give "
            "a student group."
        ),
        "objectives": (
            "Six tabletop scenarios with facilitator notes, run at least twice each, "
            "with feedback collected from participants."
        ),
        "areas": ["cyber-security"],
        "roles": [
            ("Scenario author", "Write and test the scenarios.", ["Incident response"], 2, True),
        ],
        "stage": "submitted",
    },
]

THREADS = [
    ("software-and-systems", "question",
     "What are you using for data collection in rural areas?",
     "I am working on a community health project and would like to know what others "
     "have used for offline-first data capture. Everything I find assumes a "
     "connection."),
    ("health", "discussion",
     "Getting ethical clearance for a student project — what did you have to do?",
     "Our project involves talking to patients. What does the process actually look "
     "like, and how long did it take you?"),
    ("education-and-learning", "show_and_tell",
     "We tested our materials with two screen-reader users and it went badly",
     "Posting this because the failures were more useful than the successes. Three "
     "things we got wrong and what we changed."),
    ("community-and-platform", "question",
     "How do I log a contribution that spanned three weeks?",
     "I did a piece of work in stages. Is that one contribution or three?"),
]


class Command(BaseCommand):
    help = "Populate a development instance with believable demo data."

    def add_arguments(self, parser):
        parser.add_argument("--wipe", action="store_true",
                            help="Remove everything this command created, then stop.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo refuses to run with DEBUG off. A production database with "
                "invented students in it is a database nobody can trust."
            )

        if options["wipe"]:
            return self._wipe()

        random.seed(20260922)
        people = self._people()
        anchor = self._anchor_account()
        self._projects(people, anchor)
        self._community(people)
        self._certificates(anchor)
        self.stdout.write(self.style.SUCCESS("\nDemo data seeded."))
        self.stdout.write("Remove it again with: python manage.py seed_demo --wipe")

    # -- helpers ------------------------------------------------------------

    def _anchor_account(self) -> User | None:
        """The founding account, so the dashboard has something on it."""
        return User.objects.filter(is_superuser=True).order_by("created_at").first()

    def _people(self) -> list[User]:
        created = []
        for handle, name, programme_code, year in PEOPLE:
            programme = Programme.objects.filter(code=programme_code).first()
            user, made = User.objects.get_or_create(
                email=f"{handle}@{DEMO_DOMAIN}",
                defaults={
                    "full_name": name,
                    "public_slug": handle.replace(".", "-"),
                    "programme": programme,
                    "school": programme.school if programme else None,
                    "year_of_study": year,
                    "status": User.Status.ACTIVE,
                    "email_verified_at": timezone.now(),
                    "recovery_email": f"{handle}@personal.invalid",
                    "headline": f"{programme.name if programme else 'Student'}, year {year}",
                    "bio": f"{DEMO_TAG} Demonstration account.",
                },
            )
            if made:
                user.set_password("demo-password-not-secret")
                user.save()
                # Give everyone a couple of plausible skills so matching works.
                for skill in Skill.objects.order_by("?")[:3]:
                    user.skills.get_or_create(skill=skill, defaults={"self_rating": 2})
            created.append(user)
        self.stdout.write(f"  members: {len(created)}")
        return created

    def _mentor(self) -> User:
        mentor, made = User.objects.get_or_create(
            email="dr.achieng@ouk.ac.ke",
            defaults={
                "full_name": "Dr Linet Achieng",
                "public_slug": "linet-achieng",
                "kind": User.Kind.STAFF,
                "status": User.Status.ACTIVE,
                "email_verified_at": timezone.now(),
                "headline": "Lecturer, School of Science and Technology",
                "bio": f"{DEMO_TAG} Demonstration account.",
            },
        )
        if made:
            mentor.set_password("demo-password-not-secret")
            mentor.save()
        RoleGrant.objects.get_or_create(
            user=mentor, role=RoleGrant.Role.MENTOR, discipline_area=None,
            revoked_at=None, defaults={"note": f"{DEMO_TAG}"},
        )
        return mentor

    def _projects(self, people: list[User], anchor: User | None) -> None:
        mentor = self._mentor()
        made = 0

        for index, spec in enumerate(PROJECTS):
            if Project.all_objects.filter(title=spec["title"]).exists():
                continue

            # The founding account leads the first project and is a member of
            # the second, so its dashboard is not empty on first sign-in.
            lead = anchor if (anchor and index == 0) else people[index % len(people)]

            project = Project.objects.create(
                title=spec["title"],
                summary=spec["summary"],
                problem_statement=spec["problem"],
                objectives=spec["objectives"],
                lead=lead,
                effort_hours_per_week=random.choice([4, 6, 8]),
                target_completion_on=timezone.localdate() + timedelta(days=90),
            )
            project.discipline_areas.set(
                DisciplineArea.objects.filter(slug__in=spec["areas"])
            )
            add_member(project, lead, actor=lead, is_lead=True)

            for title, description, skill_names, slots, beginner in spec["roles"]:
                role = ProjectRole.objects.create(
                    project=project, title=title, description=description,
                    slots=slots, open_to_beginners=beginner,
                )
                role.required_skills.set(Skill.objects.filter(name__in=skill_names))

            if spec["stage"] == "draft":
                made += 1
                continue

            submit_for_review(project, actor=lead)
            if spec["stage"] == "submitted":
                made += 1
                continue

            review_proposal(
                project, reviewer=mentor,
                decision=ProjectReview.Decision.APPROVED,
                reasons=(
                    "Scope is realistic for one trimester, the objectives are testable, "
                    "and nothing on FORGE duplicates it."
                ),
            )
            project.refresh_from_db()

            # Staff the team, but deliberately leave the last role of a
            # recruiting project vacant: an instance where every role is full
            # cannot demonstrate role matching or the application flow.
            candidates = [person for person in people if person != lead]
            roles = list(project.roles.all())
            if spec["stage"] == "recruiting":
                roles = roles[:-1]
            for role in roles:
                for _ in range(role.slots):
                    if not candidates:
                        break
                    applicant = candidates.pop(0)
                    application = apply_to_role(
                        role=role, applicant=applicant,
                        statement=(
                            f"I am in year {applicant.year_of_study} and this is close "
                            f"to what I want to do after I graduate."
                        ),
                    )
                    decide_application(application, decider=lead, accept=True)

            if anchor and index == 1 and not project.is_member(anchor):
                add_member(project, anchor, actor=lead)

            if spec["stage"] == "recruiting":
                made += 1
                continue

            transition(project, Project.Status.BUILDING, actor=lead,
                       note="team is complete")
            self._workspace(project, lead)
            self._contributions(project, mentor)

            if spec["stage"] == "completed":
                for status in (Project.Status.IN_REVIEW, Project.Status.DOCUMENTING,
                               Project.Status.COMPLETED):
                    transition(project, status, actor=lead)
            made += 1

        self.stdout.write(f"  projects: {made}")

    def _workspace(self, project: Project, lead: User) -> None:
        milestone = Milestone.objects.create(
            project=project, title="First working version",
            description=f"{DEMO_TAG} Something a real user can try.",
            due_on=timezone.localdate() + timedelta(days=30),
            status=Milestone.Status.IN_PROGRESS,
        )
        members = [m.user for m in project.active_members]
        for index, title in enumerate([
            "Agree the data model",
            "Build the core API",
            "Draft the interview guide",
            "Set up the deployment pipeline",
            "Write the onboarding notes",
        ]):
            Task.objects.create(
                project=project, milestone=milestone, title=title,
                assignee=members[index % len(members)], created_by=lead,
                status=[Task.Status.DONE, Task.Status.IN_PROGRESS,
                        Task.Status.TODO][index % 3],
                due_on=timezone.localdate() + timedelta(days=7 * (index + 1)),
            )

        ProgressUpdate.objects.create(
            project=project, author=lead,
            body=f"{DEMO_TAG} Data model agreed and the first endpoints are up. "
                 "Interviews start next week.",
            blockers="Still waiting on permission from the second site.",
            needs_help=True,
        )

    def _contributions(self, project: Project, mentor: User) -> None:
        """
        Log and fully confirm some work, so the ledger is not empty.

        Runs through the real service functions rather than writing rows, so
        the two-party rule and the hash chain are exercised exactly as they
        would be in use.
        """
        samples = [
            (Dimension.DELIVERY,
             "Built the queue model and the endpoints that read it, with tests.", 14),
            (Dimension.RESEARCH,
             "Interviewed eight patients and two nurses, and wrote up what the queue "
             "actually does.", 11),
            (Dimension.DOCUMENTATION,
             "Wrote the setup guide and the notes a new maintainer needs.", 6),
            (Dimension.DESIGN,
             "Designed the waiting-time screen for a phone on a slow connection.", 9),
        ]
        members = [m.user for m in project.active_members if m.user != project.lead]
        if not members:
            return

        for index, (dimension, description, hours) in enumerate(samples):
            contributor = members[index % len(members)]
            contribution = Contribution.objects.create(
                project=project, contributor=contributor, dimension=dimension,
                description=description, effort_hours=hours,
                occurred_on=timezone.localdate() - timedelta(days=7 * (index + 1)),
            )
            for skill in Skill.objects.order_by("?")[:2]:
                contribution.skills_used.add(skill)
            submit(contribution, actor=contributor)

            # The last one is left entirely unconfirmed, so that whoever leads
            # this project sees the confirmation banner on their dashboard the
            # first time they sign in. Confirmations are the bottleneck in the
            # whole scheme, and an instance that never shows one waiting fails
            # to demonstrate the thing that matters most.
            if index == len(samples) - 1:
                continue
            attest(contribution, attestor=project.lead, confirm=True)
            if index < len(samples) - 2:
                attest(contribution, attestor=mentor, confirm=True)

    def _certificates(self, anchor: User | None) -> None:
        """
        Issue certificates for work that actually happened.

        `issue_certificate` refuses when there is no confirmed contribution
        behind the claim, so this cannot manufacture one -- which is the point.
        Everything here is backed by a ledger entry.
        """
        from forge.contributions.models import LedgerEntry
        from forge.recognition.models import Certificate
        from forge.recognition.services import issue_certificate

        issued = 0
        seen: set[tuple[str, str]] = set()
        for entry in LedgerEntry.objects.select_related("contributor", "project"):
            if entry.contributor is None:
                continue
            key = (str(entry.contributor_id), str(entry.project_id))
            if key in seen:
                continue
            seen.add(key)

            kind = (Certificate.Kind.COMPLETION
                    if entry.project.status == Project.Status.COMPLETED
                    else Certificate.Kind.PARTICIPATION)
            if Certificate.objects.filter(user=entry.contributor,
                                          project=entry.project, kind=kind).exists():
                continue
            issue_certificate(user=entry.contributor, kind=kind,
                              project=entry.project, issued_by=anchor)
            issued += 1

        # The founding account needs one of its own to test the download with,
        # so it gets a confirmed contribution on the project it leads first.
        if anchor is not None:
            self._anchor_contribution(anchor)
            for project in Project.objects.filter(lead=anchor):
                if LedgerEntry.objects.filter(contributor=anchor,
                                              project=project).exists():
                    if not Certificate.objects.filter(
                        user=anchor, project=project,
                        kind=Certificate.Kind.PARTICIPATION,
                    ).exists():
                        issue_certificate(user=anchor,
                                          kind=Certificate.Kind.PARTICIPATION,
                                          project=project, issued_by=anchor)
                        issued += 1
            if not Certificate.objects.filter(
                user=anchor, kind=Certificate.Kind.COMMUNITY
            ).exists():
                issue_certificate(user=anchor, kind=Certificate.Kind.COMMUNITY,
                                  issued_by=anchor)
                issued += 1

        self.stdout.write(f"  certificates: {issued}")

    def _anchor_contribution(self, anchor: User) -> None:
        """
        Give the founding account one confirmed contribution.

        It leads a project, so it cannot attest to its own work -- the mentor
        and a community lead supply the two signatures instead, which is
        exactly the path a lead's own contributions take in real use.
        """
        from forge.contributions.models import Contribution, Dimension, LedgerEntry

        project = Project.objects.filter(lead=anchor).first()
        if project is None or LedgerEntry.objects.filter(contributor=anchor).exists():
            return

        mentor = self._mentor()
        contribution = Contribution.objects.create(
            project=project, contributor=anchor, dimension=Dimension.LEADERSHIP,
            description=(
                "Set up the project, recruited the team across two schools, and ran "
                "the first three weeks of delivery."
            ),
            effort_hours=22,
            occurred_on=timezone.localdate() - timedelta(days=21),
        )
        submit(contribution, actor=anchor)
        # The lead cannot sign their own claim, so the mentor signs in the
        # mentor capacity and a community lead signs in theirs.
        attest(contribution, attestor=mentor, confirm=True)
        community_lead = User.objects.filter(
            role_grants__role=RoleGrant.Role.COMMUNITY_LEAD,
            role_grants__revoked_at__isnull=True,
        ).exclude(pk=anchor.pk).first()
        if community_lead is None:
            community_lead = self._community_lead()
        attest(contribution, attestor=community_lead, confirm=True)

    def _community_lead(self) -> User:
        user, made = User.objects.get_or_create(
            email="community.lead@ouk.ac.ke",
            defaults={
                "full_name": "Peter Mutua",
                "public_slug": "peter-mutua",
                "kind": User.Kind.STAFF,
                "status": User.Status.ACTIVE,
                "email_verified_at": timezone.now(),
                "headline": "Community lead",
                "bio": f"{DEMO_TAG} Demonstration account.",
            },
        )
        if made:
            user.set_password("demo-password-not-secret")
            user.save()
        RoleGrant.objects.get_or_create(
            user=user, role=RoleGrant.Role.COMMUNITY_LEAD, discipline_area=None,
            revoked_at=None, defaults={"note": f"{DEMO_TAG}"},
        )
        return User.objects.get(pk=user.pk)

    def _community(self, people: list[User]) -> None:
        made = 0
        for space_slug, kind, title, body in THREADS:
            space = Space.objects.filter(slug=space_slug).first()
            if space is None or Thread.all_objects.filter(title=title).exists():
                continue
            author = random.choice(people)
            thread = Thread.objects.create(
                space=space, author=author, kind=kind, title=title, body=body,
            )
            replier = random.choice([p for p in people if p != author])
            Post.objects.create(
                thread=thread, author=replier, author_name=replier.display_name,
                body=f"{DEMO_TAG} We hit the same thing. What worked for us was "
                     "starting smaller than felt sensible and adding to it.",
            )
            Thread.objects.filter(pk=thread.pk).update(reply_count=1)
            made += 1
        self.stdout.write(f"  discussions: {made}")

    def _wipe(self) -> None:
        emails = [f"{handle}@{DEMO_DOMAIN}" for handle, *_ in PEOPLE]
        emails.append("dr.achieng@ouk.ac.ke")
        emails.append("community.lead@ouk.ac.ke")
        titles = [spec["title"] for spec in PROJECTS]

        # Projects are removed first: the ledger protects its contributors from
        # deletion, so the entries have to go before the accounts do.
        from forge.contributions.models import Attestation, LedgerEntry
        from forge.recognition.models import Certificate

        projects = Project.all_objects.filter(title__in=titles)
        Certificate.objects.filter(project__in=projects).delete()
        LedgerEntry.objects.filter(project__in=projects).delete()
        Attestation.objects.filter(contribution__project__in=projects).delete()
        Contribution.objects.filter(project__in=projects).delete()
        projects.delete()

        Thread.all_objects.filter(title__in=[t[2] for t in THREADS]).delete()
        removed, _ = User.objects.filter(email__in=emails).delete()
        self.stdout.write(self.style.SUCCESS(f"Demo data removed ({removed} rows)."))
