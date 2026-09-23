"""Shared fixtures."""

from __future__ import annotations

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from forge.accounts.models import (
    DisciplineArea,
    Programme,
    RoleGrant,
    School,
    Skill,
    User,
)
from forge.projects.models import Membership, Project, ProjectRole
from forge.recognition.models import Level


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def school(db):
    return School.objects.create(name="School of Science and Technology", code="SST")


@pytest.fixture
def other_school(db):
    return School.objects.create(name="School of Health Sciences", code="SHS")


@pytest.fixture
def programme(school):
    return Programme.objects.create(
        school=school, name="BSc. Cyber Security and Digital Forensics",
        code="BSC-CSDF",
    )


@pytest.fixture
def area(db):
    return DisciplineArea.objects.create(name="Software and Systems",
                                         slug="software-and-systems")


@pytest.fixture
def skill(db):
    return Skill.objects.create(name="Django", slug="django", is_approved=True)


@pytest.fixture
def levels(db):
    Level.objects.create(name="Apprentice", slug="apprentice", rank=1, min_points=0)
    Level.objects.create(name="Builder", slug="builder", rank=2, min_points=60,
                         min_confirmed_contributions=5, min_completed_projects=1)
    Level.objects.create(name="Master Builder", slug="master-builder", rank=4,
                         min_points=600, requires_teaching=True)


def make_user(email: str, name: str, *, school=None, programme=None,
              kind=User.Kind.STUDENT, status=User.Status.ACTIVE, slug=None):
    user = User(
        email=email, full_name=name, kind=kind, status=status,
        public_slug=slug or email.split("@")[0].replace(".", "-"),
        school=school, programme=programme,
        email_verified_at=timezone.now() if status != User.Status.PENDING else None,
        recovery_email=f"{email.split('@')[0]}@personal.example",
    )
    user.set_password("a-long-enough-password")
    user.save()
    return user


@pytest.fixture
def user_factory(db):
    """Make an arbitrary member. Exposed as a fixture so test modules do not
    have to import across the tests package."""
    return make_user


@pytest.fixture
def student(school, programme):
    return make_user("amina.wanjiru@ouk.ac.ke", "Amina Wanjiru",
                     school=school, programme=programme)


@pytest.fixture
def peer(school, programme):
    return make_user("brian.otieno@ouk.ac.ke", "Brian Otieno",
                     school=school, programme=programme)


@pytest.fixture
def nurse(other_school):
    return make_user("cynthia.mwangi@ouk.ac.ke", "Cynthia Mwangi", school=other_school)


@pytest.fixture
def mentor(db, school):
    user = make_user("dr.kamau@ouk.ac.ke", "Dr Joseph Kamau", school=school,
                     kind=User.Kind.STAFF)
    RoleGrant.objects.create(user=user, role=RoleGrant.Role.MENTOR)
    return user


@pytest.fixture
def advisor(db):
    user = make_user("advisor@ouk.ac.ke", "Faculty Advisor", kind=User.Kind.STAFF)
    RoleGrant.objects.create(user=user, role=RoleGrant.Role.FACULTY_ADVISOR)
    return user


@pytest.fixture
def project(student, area):
    project = Project.objects.create(
        title="Clinic queue tracker",
        summary="A tool for tracking patient queues at a rural clinic.",
        problem_statement="Patients wait without knowing how long.",
        objectives="A working web tool used by at least one clinic.",
        lead=student,
    )
    project.discipline_areas.add(area)
    Membership.objects.create(project=project, user=student, is_lead=True)
    return project


@pytest.fixture
def role(project, skill):
    role = ProjectRole.objects.create(project=project, title="Backend developer",
                                      description="Build the API.", slots=2)
    role.required_skills.add(skill)
    return role


@pytest.fixture
def approved_project(project, role, mentor):
    """A project past review, recruiting, with a mentor attached."""
    from forge.projects.models import ProjectReview
    from forge.projects.services import review_proposal, submit_for_review

    submit_for_review(project, actor=project.lead)
    review_proposal(project, reviewer=mentor,
                    decision=ProjectReview.Decision.APPROVED,
                    reasons="Scope is realistic and the objectives are clear.")
    project.refresh_from_db()
    return project


def auth(client: APIClient, user: User) -> APIClient:
    client.force_authenticate(user=user)
    return client
