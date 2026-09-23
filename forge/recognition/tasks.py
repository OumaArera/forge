"""Scheduled recognition work."""

from __future__ import annotations

import logging
from datetime import date

from celery import shared_task
from django.utils import timezone

from forge.accounts.models import DisciplineArea

from .models import LeaderboardSnapshot
from .services import build_leaderboard

logger = logging.getLogger("forge.recognition")


def current_trimester() -> tuple[date, date]:
    """
    The trimester now running.

    Boundaries are approximate and a pilot should replace this with the
    University's published almanac. It is a function rather than a constant
    so that replacing it is a one-place change.
    """
    today = timezone.localdate()
    if today.month <= 4:
        return date(today.year, 1, 1), date(today.year, 4, 30)
    if today.month <= 8:
        return date(today.year, 5, 1), date(today.year, 8, 31)
    return date(today.year, 9, 1), date(today.year, 12, 31)


@shared_task
def rebuild_leaderboards() -> dict:
    """
    Recompute every scoped board.

    Boards are frozen snapshots rather than live queries. A live leaderboard
    is both the most expensive query the platform would run and its most
    addictive feature, and neither is worth encouraging.
    """
    start, end = current_trimester()
    built = 0

    for area in DisciplineArea.objects.filter(is_active=True):
        build_leaderboard(scope=LeaderboardSnapshot.Scope.DISCIPLINE,
                          discipline_area=area, period_start=start, period_end=end)
        built += 1

    for scope in (LeaderboardSnapshot.Scope.COMMUNITY,
                  LeaderboardSnapshot.Scope.MENTORSHIP):
        build_leaderboard(scope=scope, period_start=start, period_end=end)
        built += 1

    return {"boards": built, "period": [start.isoformat(), end.isoformat()]}


@shared_task
def verify_ledger_integrity() -> dict:
    """
    Check the chain on a schedule and shout if it is broken.

    A tamper-evident record nobody checks is just a record.
    """
    from forge.contributions.services import verify_chain

    report = verify_chain()
    if not report["intact"]:
        logger.error("LEDGER INTEGRITY FAILURE: %s", report["problems"][:10])
    return report
