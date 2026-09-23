"""
Rate limits.

Two different problems get solved here and they need different tools.

**Volume.** Somebody hammering the API — deliberately or through a broken
client — is handled by DRF's throttles, keyed on the IP for anonymous callers
and on the account for signed-in ones. This is a speed bump, not a defence:
a real distributed flood has to be stopped upstream, at the reverse proxy or
the CDN, before it reaches Django at all. What these limits actually buy is
protection against the single-host script, which is what a student platform
will meet in practice.

**Credential guessing.** A limit of "ten attempts a minute" still allows
fourteen thousand guesses a day, which is plenty against a weak password. So
sign-in additionally uses a lockout with a backoff (see accounts.lockout),
counted per account *and* per source address. Per account alone lets one
attacker lock every student out by guessing badly on purpose; per address
alone is useless against a botnet. Both, with the account lockout short and
self-healing, is the compromise.
"""

from __future__ import annotations

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


def client_address(request) -> str:
    """
    The caller's address.

    Behind a proxy, REMOTE_ADDR is the proxy, so the left-most entry of
    X-Forwarded-For is used instead. That header is trivially forged when the
    app is exposed directly, which is why the deployment must terminate at a
    proxy that overwrites it. Documented in docs/for-the-ict-directorate.md.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


class BurstAnonThrottle(AnonRateThrottle):
    """Short window: stops a tight loop immediately."""

    scope = "anon-burst"


class SustainedAnonThrottle(AnonRateThrottle):
    """Long window: stops a slow crawl that the burst limit would never see."""

    scope = "anon-sustained"


class BurstUserThrottle(UserRateThrottle):
    scope = "user-burst"


class SustainedUserThrottle(UserRateThrottle):
    scope = "user-sustained"


class LoginRateThrottle(SimpleRateThrottle):
    """
    Sign-in attempts from one address.

    Keyed on the address rather than the submitted email, because an attacker
    working through a list of addresses would otherwise get a fresh budget for
    every account they tried.
    """

    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": client_address(request)}


class LoginEmailThrottle(SimpleRateThrottle):
    """
    Sign-in attempts against one account, from anywhere.

    The complement of the above: this is what makes a distributed guessing
    attack against a single known account expensive.
    """

    scope = "login-email"

    def get_cache_key(self, request, view):
        email = ""
        if hasattr(request, "data") and isinstance(request.data, dict):
            email = str(request.data.get("email", "")).lower().strip()
        if not email:
            return None  # nothing to key on; the address throttle still applies
        return self.cache_format % {"scope": self.scope, "ident": email}


class ExpensiveThrottle(SimpleRateThrottle):
    """
    For endpoints that cost the platform real work: signed exports, PDF
    rendering, ledger verification over the whole chain.
    """

    scope = "expensive"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {"scope": self.scope, "ident": str(request.user.pk)}
        return self.cache_format % {"scope": self.scope, "ident": client_address(request)}
