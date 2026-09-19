"""Redis connection helpers.

Nothing in the app uses Redis yet (no cache, Celery or rate limiting).
This module only provides a configured client plus a connectivity check
so that a Redis outage or misconfiguration is easy to detect.

All connection details come from Django settings, which read them from
the environment via python-decouple -- no host, port or password is
hardcoded here.
"""

import logging
from functools import lru_cache
from typing import NamedTuple

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


class RedisStatus(NamedTuple):
    ok: bool
    detail: str


@lru_cache(maxsize=None)
def _build_client(host, port, db, password, ssl, connect_timeout, timeout):
    # Keyed on the setting values so a changed setting (e.g. under
    # override_settings in tests) never returns a stale client.
    return redis.Redis(
        host=host,
        port=port,
        db=db,
        password=password or None,
        ssl=ssl,
        socket_connect_timeout=connect_timeout,
        socket_timeout=timeout,
        decode_responses=True,
    )


def get_redis_client():
    """Return the shared Redis client built from the REDIS_* settings.

    The client is lazy: creating it opens no connection, and it manages
    its own connection pool, so it is safe to call on every use.
    """
    return _build_client(
        settings.REDIS_HOST,
        settings.REDIS_PORT,
        settings.REDIS_DB,
        settings.REDIS_PASSWORD,
        settings.REDIS_SSL,
        settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        settings.REDIS_SOCKET_TIMEOUT,
    )


def check_redis():
    """PING Redis and return a RedisStatus(ok, detail).

    Never raises. On failure the reason is logged at ERROR level (host,
    port and db only -- never the password) and returned in `detail`.
    """
    target = (
        f"{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    )
    try:
        get_redis_client().ping()
    except redis.exceptions.AuthenticationError:
        detail = "authentication failed (check REDIS_PASSWORD)"
    except redis.exceptions.TimeoutError:
        detail = "timed out"
    except redis.exceptions.ConnectionError as exc:
        detail = f"connection failed: {exc}"
    except redis.exceptions.RedisError as exc:
        detail = f"{type(exc).__name__}: {exc}"
    else:
        return RedisStatus(True, "ok")

    logger.error("Redis check failed for %s: %s", target, detail)
    return RedisStatus(False, detail)
