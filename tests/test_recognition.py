"""
Recognition: levels, badges, leaderboards.

Section 10 of the concept proposal is blunt about the stakes -- a voluntary
platform with badly designed recognition fills with worthless activity -- so
the tests here are mostly about what recognition refuses to reward.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from forge.contributions.models import Dimension
from forge.contributions.services import attest, submit
from forge.projects.models import Project
from forge.projects.services import add_member, transition
from forge.recognition.models import LeaderboardSnapshot, Level, Standing
from forge.recognition.services import build_leaderboard, reassess_standing

pytestmark = pytest.mark.django_db


def settle(project, contributor, mentor, dimension=Dimension.DELIVERY, hours=10,
           description="Did the work."):
    contribution = project.contributions.create(
        contributor=contributor, dimension=dimension, description=description,
        occurred_on=timezone.localdate(), effort_hours=hours,
    )
    submit(contribution, actor=contributor)
    attest(contribution, attestor=project.lead, confirm=True)
    attest(contribution, attestor=mentor, confirm=True)
    return contribution


class TestStanding:
    def test_standing_is_derived_from_confirmed_work_only(
        self, approved_project, peer, mentor, levels
    ):
        add_member(approved_project, peer, actor=approved_project.lead)

        unconfirmed = approved_project.contributions.create(
            contributor=peer, dimension=Dimension.DELIVERY,
            description="Not confirmed.", occurred_on=timezone.localdate(),
        )
        submit(unconfirmed, actor=peer)

        standing = reassess_standing(peer)
        assert standing.total_points == 0
        assert standing.confirmed_contributions == 0

        settle(approved_project, peer, mentor)
        peer.refresh_from_db()
        standing = Standing.objects.get(user=peer)
        assert standing.total_points > 0
        assert standing.confirmed_contributions == 1

    def test_standing_rebuilds_identically(self, approved_project, peer, mentor, levels):
        add_member(approved_project, peer, actor=approved_project.lead)
        settle(approved_project, peer, mentor)
        settle(approved_project, peer, mentor, Dimension.DOCUMENTATION)

        before = Standing.objects.get(user=peer).total_points
        Standing.objects.filter(user=peer).update(total_points=99999)
        after = reassess_standing(peer).total_points

        assert after == before

    def test_points_are_broken_down_by_dimension(
        self, approved_project, peer, mentor, levels
    ):
        """
        Without this the platform quietly becomes a leaderboard for whoever
        writes the most code, and the student who ran the documentation or
        taught three juniors appears to have done nothing.
        """
        add_member(approved_project, peer, actor=approved_project.lead)
        settle(approved_project, peer, mentor, Dimension.DELIVERY)
        settle(approved_project, peer, mentor, Dimension.MENTORSHIP)
        settle(approved_project, peer, mentor, Dimension.DOCUMENTATION)

        standing = Standing.objects.get(user=peer)
        assert set(standing.points_by_dimension) == {
            Dimension.DELIVERY, Dimension.MENTORSHIP, Dimension.DOCUMENTATION}

    def test_effort_hours_cannot_be_farmed(self, approved_project, peer, mentor, levels):
        """
        Hours are self-reported. Any scheme that pays out linearly in a
        self-reported number rewards whoever is least scrupulous about it.
        """
        add_member(approved_project, peer, actor=approved_project.lead)
        settle(approved_project, peer, mentor, hours=2000, description="Long week.")

        entry_points = Standing.objects.get(user=peer).total_points
        assert entry_points <= 16   # base 10 + capped effort bonus of 6


class TestLevels:
    def test_the_top_level_requires_having_taught(self, approved_project, peer,
                                                  mentor, levels):
        """
        The highest standing is reserved for those who have both delivered and
        taught. This is what stops the ladder being a pure output count.
        """
        add_member(approved_project, peer, actor=approved_project.lead)

        master = Level.objects.get(slug="master-builder")
        master.min_points = 10
        master.min_confirmed_contributions = 0
        master.min_completed_projects = 0
        master.save()

        settle(approved_project, peer, mentor, Dimension.DELIVERY, hours=100)
        standing = Standing.objects.get(user=peer)
        assert standing.level.slug != "master-builder"

        settle(approved_project, peer, mentor, Dimension.MENTORSHIP,
               description="Taught two juniors to use Git.")
        standing = Standing.objects.get(user=peer)
        assert standing.level.slug == "master-builder"

    def test_reaching_a_level_is_recorded_once(self, approved_project, peer,
                                               mentor, levels):
        from forge.recognition.models import LevelAward

        add_member(approved_project, peer, actor=approved_project.lead)
        settle(approved_project, peer, mentor)
        settle(approved_project, peer, mentor)

        assert LevelAward.objects.filter(user=peer, level__slug="apprentice").count() == 1


class TestBadges:
    def test_a_cross_school_contribution_earns_the_right_badge(
        self, approved_project, role, nurse, mentor, levels, db
    ):
        from forge.recognition.models import Badge, BadgeAward

        Badge.objects.create(name="Crossed the aisle", slug="crossed-the-aisle",
                             kind=Badge.Kind.COMMUNITY,
                             description="Worked across schools.",
                             criteria="Contribute to a cross-school team.")

        add_member(approved_project, nurse, actor=approved_project.lead)
        settle(approved_project, nurse, mentor)

        assert BadgeAward.objects.filter(user=nurse,
                                         badge__slug="crossed-the-aisle").exists()


class TestLeaderboards:
    def test_boards_are_scoped_not_global(self, approved_project, peer, mentor,
                                          area, levels):
        add_member(approved_project, peer, actor=approved_project.lead)
        settle(approved_project, peer, mentor)

        today = timezone.localdate()
        start = today.replace(day=1)
        snapshot = build_leaderboard(
            scope=LeaderboardSnapshot.Scope.DISCIPLINE, discipline_area=area,
            period_start=start, period_end=today,
        )
        assert snapshot.rows
        assert snapshot.rows[0]["display_name"] == peer.display_name
        assert snapshot.rows[0]["rank"] == 1

    def test_a_private_portfolio_is_ranked_but_not_linked(
        self, approved_project, peer, mentor, area, levels
    ):
        """Appearing on a board is not consent to be looked up."""
        add_member(approved_project, peer, actor=approved_project.lead)
        settle(approved_project, peer, mentor)

        peer.portfolio_is_public = False
        peer.save(update_fields=["portfolio_is_public"])

        today = timezone.localdate()
        snapshot = build_leaderboard(
            scope=LeaderboardSnapshot.Scope.DISCIPLINE, discipline_area=area,
            period_start=today.replace(day=1), period_end=today,
        )
        row = snapshot.rows[0]
        assert row["display_name"] == peer.display_name
        assert row["public_slug"] is None

    def test_community_board_counts_only_community_work(
        self, approved_project, peer, nurse, mentor, levels
    ):
        add_member(approved_project, peer, actor=approved_project.lead)
        add_member(approved_project, nurse, actor=approved_project.lead)

        settle(approved_project, peer, mentor, Dimension.DELIVERY)
        settle(approved_project, nurse, mentor, Dimension.COMMUNITY)

        today = timezone.localdate()
        snapshot = build_leaderboard(
            scope=LeaderboardSnapshot.Scope.COMMUNITY,
            period_start=today.replace(day=1), period_end=today,
        )
        names = [r["display_name"] for r in snapshot.rows]
        assert nurse.display_name in names
        assert peer.display_name not in names


class TestVotesDoNotEarnPoints:
    def test_a_popular_post_earns_nothing(self, approved_project, peer, mentor,
                                          nurse, levels, area):
        """
        The platform rewards demonstrated contribution rather than popularity.
        Letting a well-liked post earn points would quietly abandon that.
        """
        from forge.community.models import Post, Space, Thread, Vote

        space = Space.objects.create(name="Software", slug="software",
                                     discipline_area=area)
        thread = Thread.objects.create(space=space, author=peer, title="A question",
                                       body="How do I...")
        post = Post.objects.create(thread=thread, author=peer, author_name=peer.display_name,
                                   body="A very popular answer.")
        Vote.objects.create(post=post, user=nurse, value=1)
        Vote.objects.create(post=post, user=mentor, value=1)

        standing = reassess_standing(peer)
        assert standing.total_points == 0


class TestProjectCompletionCounts:
    def test_completing_a_project_updates_standing(self, approved_project, peer,
                                                   mentor, levels):
        add_member(approved_project, peer, actor=approved_project.lead)
        settle(approved_project, peer, mentor)

        for status in (Project.Status.BUILDING, Project.Status.IN_REVIEW,
                       Project.Status.DOCUMENTING, Project.Status.COMPLETED):
            transition(approved_project, status, actor=approved_project.lead)

        standing = reassess_standing(peer)
        assert standing.completed_projects == 1
