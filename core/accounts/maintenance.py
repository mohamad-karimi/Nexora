"""Scheduled (Celery Beat) cleanup of expired authentication data.

Only data that really piles up with nothing else removing it is cleaned
here. What was checked, and what was left alone on purpose:

* Expired email-verification (OTP) codes -- cleaned here. A code row is
  deleted when the user verifies and replaced when they resend, but a user
  who registers and never comes back leaves an expired row behind forever.
* Expired database sessions -- cleaned here. Every visit to the register
  or login page stores the security code in a session, and Django never
  deletes expired sessions by itself (it only ships `clearsessions`).
* Expired JWT refresh tokens -- cleaned here. `token_blacklist` records
  every issued refresh token (rotation issues a new one on each refresh)
  and never prunes them (simplejwt only ships `flushexpiredtokens`).
* Password-reset data -- nothing to clean: reset tokens are stateless JWTs
  (see accounts/tokens.py), no row is ever stored.
* The Redis "email already sent" markers (accounts/tasks.py) carry their
  own TTL, so Redis expires them.

The jobs are scheduled by CELERY_BEAT_SCHEDULE in core/settings.py (one
`beat` process, see docker-compose*.yml).

Safety properties, shared by every job:

* Idempotent -- each one just deletes rows that are already expired, so a
  repeated or overlapping run is harmless.
* Single run at a time -- a short-lived Redis lock makes a second copy
  (for example a second beat by mistake) skip instead of running in
  parallel. If Redis cannot be reached the job runs anyway, since running
  twice is harmless.
* Gentle on the database -- rows go in small batches, each its own short
  transaction (SQLite allows one writer, and the web process must not be
  starved), and a run stops after a time budget so it always ends inside
  Celery's task time limit; whatever is left is picked up by the next run.
* Log lines carry counts only.
"""

import logging
import time
from contextlib import contextmanager
from datetime import timedelta

import redis
from celery import shared_task
from django.contrib.sessions.models import Session
from django.db import OperationalError
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from accounts.models import EmailVerificationCode
from core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# An OTP row is kept for this long after it expires. The verify endpoint
# tells "expired" apart from "no code pending" by finding the row, and the
# pending-verification session lasts only as long as the code does, so this
# grace period is only ever a margin -- not something users depend on.
OTP_RETENTION = timedelta(hours=24)

CLEANUP_BATCH_SIZE = 500
# Stay well under CELERY_TASK_SOFT_TIME_LIMIT (60s).
CLEANUP_TIME_BUDGET_SECONDS = 40
# The lock outlives any normal run; it only expires on its own if a worker
# dies while holding it.
CLEANUP_LOCK_TTL_SECONDS = 30 * 60


@contextmanager
def _single_run(job):
    """Yield True if this run may proceed, False if another run holds it."""
    lock = None
    try:
        lock = get_redis_client().lock(
            f"nexora:lock:{job}",
            timeout=CLEANUP_LOCK_TTL_SECONDS,
        )
        acquired = lock.acquire(blocking=False)
    except redis.exceptions.RedisError:
        logger.warning(
            "Could not take the %s lock (Redis); running without it.", job
        )
        lock, acquired = None, True

    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        if lock is not None:
            try:
                lock.release()
            except redis.exceptions.RedisError:
                # Includes LockError: it already expired on its own.
                pass


def _delete_in_batches(queryset):
    """Delete `queryset`'s rows in small batches.

    Returns (rows_deleted, finished). `finished` is False when the time
    budget ran out first; the next scheduled run continues from there.
    """
    model = queryset.model
    deadline = time.monotonic() + CLEANUP_TIME_BUDGET_SECONDS
    deleted = 0
    while True:
        pks = list(
            queryset.order_by("pk").values_list("pk", flat=True)[
                :CLEANUP_BATCH_SIZE
            ]
        )
        if not pks:
            return deleted, True
        # The count includes rows removed by ON DELETE CASCADE.
        deleted += model.objects.filter(pk__in=pks).delete()[0]
        if len(pks) < CLEANUP_BATCH_SIZE:
            return deleted, True
        if time.monotonic() >= deadline:
            return deleted, False


def _run_cleanup(job, label, queryset):
    with _single_run(job) as may_run:
        if not may_run:
            logger.info(
                "Skipping %s cleanup: another run is in progress.", label
            )
            return
        deleted, finished = _delete_in_batches(queryset)
    logger.info(
        "Cleanup of %s: deleted %s row(s)%s.",
        label,
        deleted,
        "" if finished else "; time budget reached, rest left for next run",
    )


def _cleanup_task(name):
    # A locked/unavailable database is temporary: retry a few times, with
    # backoff, before leaving the work to tomorrow's run. The explicit
    # names are what CELERY_BEAT_SCHEDULE refers to.
    return shared_task(
        name=name,
        bind=True,
        ignore_result=True,
        autoretry_for=(OperationalError,),
        retry_backoff=60,
        retry_backoff_max=600,
        retry_jitter=True,
        max_retries=3,
    )


@_cleanup_task("accounts.cleanup_expired_otp_codes")
def cleanup_expired_otp_codes(self):
    """Delete email-verification codes that expired over OTP_RETENTION ago."""
    _run_cleanup(
        "expired-otp-codes",
        "expired email-verification codes",
        EmailVerificationCode.objects.filter(
            expires_at__lt=timezone.now() - OTP_RETENTION
        ),
    )


@_cleanup_task("accounts.cleanup_expired_sessions")
def cleanup_expired_sessions(self):
    """Delete expired database sessions (what `clearsessions` does)."""
    _run_cleanup(
        "expired-sessions",
        "expired sessions",
        Session.objects.filter(expire_date__lt=timezone.now()),
    )


@_cleanup_task("accounts.cleanup_expired_jwt_tokens")
def cleanup_expired_jwt_tokens(self):
    """Delete expired refresh tokens and their blacklist entries.

    What `flushexpiredtokens` does. An expired token is rejected anyway,
    so dropping its blacklist entry with it loses nothing.
    """
    _run_cleanup(
        "expired-jwt-tokens",
        "expired JWT refresh tokens",
        OutstandingToken.objects.filter(expires_at__lte=timezone.now()),
    )
