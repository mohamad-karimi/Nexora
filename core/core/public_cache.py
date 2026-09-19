"""Redis cache for PUBLIC storefront query results.

What goes in, and what never does
---------------------------------
Only results that are the same for every visitor are cached: published
products, categories, tags, approved vendors, home slides/banners,
published blog posts. What is cached is the *query result* (model
instances / plain data) -- never a finished HTTP response. The API
serializers still run on every request, so everything that depends on who
is asking (`is_wishlisted`, `is_liked`, `is_bookmarked`, absolute media
URLs built from the request's host, pagination links) is computed fresh
per request and cannot leak from one user to another. Cart, checkout,
orders, account, dashboard, wishlist, profile and session/JWT state are
never routed through this module.

Freshness: versioned keys
-------------------------
Entries live under `pubcache:<domain>:<version>:<hash of the query>`. Each
domain ("catalog", "home", "blog") has a version number in Redis; every
relevant model change bumps it (core/cache_invalidation.py), which makes
every entry of that domain unreachable at once -- no key scanning or
pattern deletes. A lookup remembers the version it read and stores its
result under that same version, so a result computed while a change
happened is stored under the old version and is never served. Entries
also carry a TTL (settings.PUBLIC_CACHE_TTL) as a backstop for writes that
bypass Django signals.

Redis failure: always fall back to the database
-----------------------------------------------
Every Redis call here is wrapped. On a connection/timeout error the cache
is skipped for PUBLIC_CACHE_FAILURE_COOLDOWN seconds (so a dead Redis
costs one short timeout, not one per request) and callers simply run the
real query. An invalidation that could not reach Redis is retried as soon
as Redis is back, and no cached data is served in the meantime.
"""

import hashlib
import json
import logging
import time

import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction

logger = logging.getLogger(__name__)

MISS = object()

# Errors that mean "Redis is unreachable or unhealthy".
_REDIS_ERRORS = (redis.exceptions.RedisError, OSError)

_state = {"down_until": 0.0}
# Domains whose version bump could not be delivered yet.
_pending_bumps = set()


class Slot:
    """Result of a lookup: the cached value (or MISS) and where to store.

    `key` is None when the cache cannot be used right now (disabled or
    Redis down); `store()` then does nothing.
    """

    __slots__ = ("key", "value")

    def __init__(self, key, value=MISS):
        self.key = key
        self.value = value

    @property
    def hit(self):
        return self.value is not MISS


def available():
    """True if the cache may be used right now."""
    return (
        bool(settings.PUBLIC_CACHE_ENABLED)
        and time.monotonic() >= _state["down_until"]
    )


def reset_state():
    """Forget failures and pending invalidations (used by the tests)."""
    _state["down_until"] = 0.0
    _pending_bumps.clear()


def _trip(action, exc):
    cooldown = settings.PUBLIC_CACHE_FAILURE_COOLDOWN
    _state["down_until"] = time.monotonic() + cooldown
    logger.warning(
        "Public cache unavailable during %s (%s); using the database "
        "for %ss.",
        action,
        type(exc).__name__,
        cooldown,
    )


def _version_key(domain):
    return f"pubcache:version:{domain}"


def _new_version():
    # Time-based, so a version that was lost (eviction, flush) is
    # re-created as a value that can never equal an older one.
    return time.time_ns()


def _bump_now(domain):
    key = _version_key(domain)
    try:
        cache.incr(key)
    except ValueError:
        # No version yet: creating one already makes every older entry
        # unreachable.
        cache.add(key, _new_version(), timeout=None)


def _flush_pending():
    for domain in list(_pending_bumps):
        _bump_now(domain)
        _pending_bumps.discard(domain)


def get_version(domain):
    """The domain's current version, or None if the cache is unusable."""
    if not available():
        return None
    try:
        _flush_pending()
        key = _version_key(domain)
        version = cache.get(key)
        if version is None:
            cache.add(key, _new_version(), timeout=None)
            version = cache.get(key)
        return version
    except _REDIS_ERRORS as exc:
        _trip("version lookup", exc)
    except Exception:
        logger.exception("Public cache version lookup failed.")
    return None


def _entry_key(domain, version, parts):
    payload = json.dumps(
        parts, sort_keys=True, separators=(",", ":"), default=str
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:40]
    return f"pubcache:{domain}:{version}:{digest}"


def lookup(domain, *parts):
    """Look up the entry for `parts` (JSON-serializable, e.g. names/ids)."""
    version = get_version(domain)
    if version is None:
        return Slot(None)
    key = _entry_key(domain, version, list(parts))
    try:
        wrapped = cache.get(key)
    except _REDIS_ERRORS as exc:
        _trip("read", exc)
        return Slot(None)
    except Exception:
        # e.g. an entry pickled by an older version of the code.
        logger.exception("Unreadable public cache entry; treating as a miss.")
        return Slot(key)
    if wrapped is None:
        return Slot(key)
    # Values are wrapped in a 1-tuple so that a legitimate None/empty
    # value is distinguishable from "not cached".
    return Slot(key, wrapped[0])


def store(slot, value, ttl_name):
    """Store `value` for `slot` for settings.PUBLIC_CACHE_TTL[ttl_name]."""
    if slot.key is None or not available():
        return
    try:
        cache.set(slot.key, (value,), settings.PUBLIC_CACHE_TTL[ttl_name])
    except _REDIS_ERRORS as exc:
        _trip("write", exc)
    except Exception:
        logger.exception("Could not store a public cache entry.")


def cached(domain, parts, producer, ttl_name):
    """`producer()`'s result, served from / stored in the cache."""
    slot = lookup(domain, *parts)
    if slot.hit:
        return slot.value
    value = producer()
    store(slot, value, ttl_name)
    return value


def bump(domain):
    """Invalidate every cached entry of `domain`.

    Done right away, and once more when the surrounding transaction
    commits: a request that repopulates the cache between the two would
    otherwise store the old data under the new version.
    """
    _bump_safely(domain)
    if connection.in_atomic_block:
        transaction.on_commit(lambda: _bump_safely(domain))


def _bump_safely(domain):
    # Attempted even when PUBLIC_CACHE_ENABLED is off, so that data written
    # while the cache was switched off cannot resurface when it is back on.
    if time.monotonic() < _state["down_until"]:
        _pending_bumps.add(domain)
        return
    try:
        _flush_pending()
        _bump_now(domain)
    except _REDIS_ERRORS as exc:
        _pending_bumps.add(domain)
        _trip("invalidation", exc)
    except Exception:
        logger.exception("Public cache invalidation failed for %s.", domain)
