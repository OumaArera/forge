"""Operational endpoints. Deliberately not part of the versioned API."""

from django.db import connection, transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache

# ATOMIC_REQUESTS wraps every view in a transaction, which for these two would
# mean a liveness probe opening a transaction on the database every few
# seconds. Worse, it would make liveness fail whenever the database is
# unreachable -- and liveness failing is what gets a healthy process killed and
# restarted, which fixes nothing when the problem is the database. Liveness
# says the process is up; readiness is where database trouble belongs.


@never_cache
@transaction.non_atomic_requests
def health(request):
    """Liveness: the process is up. Deliberately touches nothing."""
    return JsonResponse({"status": "ok", "service": "forge-api"})


@never_cache
@transaction.non_atomic_requests
def readiness(request):
    """Readiness: the process can actually serve traffic."""
    checks = {}
    ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - depends on infrastructure
        checks["database"] = f"error: {exc.__class__.__name__}"
        ok = False
    return JsonResponse({"status": "ok" if ok else "degraded", "checks": checks},
                        status=200 if ok else 503)
