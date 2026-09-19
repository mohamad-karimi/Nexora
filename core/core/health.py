"""Liveness/readiness endpoint for CI, Docker healthchecks and the CD
post-deploy check.

Intentionally unauthenticated and dependency-free beyond the database
connection itself -- it is infrastructure plumbing, not a business
endpoint, so it does not touch app models or business logic.
"""

from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse

from core.redis_client import check_redis


def health(request):
    """Return 200 with {"status": "ok"} when the app is up and the
    database is reachable, otherwise 503."""
    db_ok = True
    try:
        connections["default"].cursor()
    except OperationalError:
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "error",
        "database": "ok" if db_ok else "error",
    }
    return JsonResponse(payload, status=200 if db_ok else 503)


def redis_health(request):
    """Return 200 with {"status": "ok", "redis": "ok"} when Redis is
    reachable (and the configured password is accepted), otherwise 503.

    Kept separate from `health` on purpose: nothing in the app depends
    on Redis yet, so a Redis outage must not flip the main /health/
    check (used by the Docker healthcheck and the CD post-deploy check)
    to unhealthy. The failure reason is logged by `check_redis`, never
    returned to the caller.
    """
    ok = check_redis().ok

    payload = {
        "status": "ok" if ok else "error",
        "redis": "ok" if ok else "error",
    }
    return JsonResponse(payload, status=200 if ok else 503)
