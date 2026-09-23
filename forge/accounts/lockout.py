"""
Account lockout after repeated failed sign-ins.

A rate limit caps how fast somebody can guess. A lockout caps how many guesses
they get at all, which is the property that actually protects a weak password.

The design is deliberately forgiving, because the common cause of five failed
attempts is a student who has forgotten their password, not an attacker:

  * The lock is short and lengthens with repetition, so an honest mistake
    costs a few minutes and a sustained attack costs hours.
  * Counters live in the cache and expire on their own. Nothing has to be
    cleaned up, and a restart releases everybody.
  * A successful sign-in clears the count immediately.
  * The member is told by email the first time it happens, because an
    unexplained lockout is indistinguishable from a broken site -- and if it
    was not them, they need to know somebody is trying.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("forge.accounts")

FAILURE_WINDOW = 15 * 60          # how long failures are remembered
NOTIFY_AFTER = 5                  # failures before we email the account holder

# Attempts allowed, then how long the lock lasts. Repeated lockouts escalate.
BACKOFF = [
    (5, timedelta(minutes=5)),
    (8, timedelta(minutes=30)),
    (12, timedelta(hours=2)),
    (20, timedelta(hours=12)),
]


def _failure_key(email: str) -> str:
    return f"forge:login-failures:{email.lower().strip()}"


def _lock_key(email: str) -> str:
    return f"forge:login-lock:{email.lower().strip()}"


def locked_until(email: str):
    """The moment this account unlocks, or None if it is not locked."""
    value = cache.get(_lock_key(email))
    if value is None:
        return None
    if value <= timezone.now():
        cache.delete(_lock_key(email))
        return None
    return value


def is_locked(email: str) -> bool:
    return locked_until(email) is not None


def record_failure(email: str, *, ip: str = "") -> int:
    """
    Count one failed attempt and lock the account if it has earned it.

    Returns the running failure count.
    """
    email = (email or "").lower().strip()
    if not email:
        return 0

    key = _failure_key(email)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, FAILURE_WINDOW)
        count = 1

    threshold = None
    for attempts, duration in BACKOFF:
        if count >= attempts:
            threshold = duration
    if threshold is not None:
        until = timezone.now() + threshold
        cache.set(_lock_key(email), until, int(threshold.total_seconds()))
        logger.warning("Locked %s until %s after %s failures from %s",
                       email, until, count, ip or "unknown")
        if count == NOTIFY_AFTER:
            _notify(email, count, until)

    return count


def clear(email: str) -> None:
    """Called on a successful sign-in. One good password forgives the rest."""
    email = (email or "").lower().strip()
    cache.delete(_failure_key(email))
    cache.delete(_lock_key(email))


def _notify(email: str, attempts: int, until) -> None:
    from django.utils.formats import date_format

    from forge.accounts.models import User
    from forge.common.mail import send

    user = User.objects.filter(email=email).first()
    if user is None:
        return  # never confirm to an attacker that an address exists
    send(
        to=user.email,
        subject="FORGE: your account was temporarily locked",
        template="account_locked",
        category="security",
        user=user,
        context={
            "user": user,
            "attempts": attempts,
            "until": date_format(timezone.localtime(until), "H:i \\o\\n j F"),
        },
    )


def remaining_attempts(email: str) -> int:
    """How many tries are left before the first lock. Shown to the member."""
    count = cache.get(_failure_key(email)) or 0
    first_threshold = BACKOFF[0][0]
    return max(first_threshold - int(count), 0)


def lock_message(email: str) -> str:
    until = locked_until(email)
    if until is None:
        return ""
    minutes = max(int((until - timezone.now()).total_seconds() // 60), 1)
    return (
        f"Too many failed sign-in attempts. Try again in {minutes} "
        f"minute{'s' if minutes != 1 else ''}, or ask the faculty advisor to "
        f"reset your password."
    )
