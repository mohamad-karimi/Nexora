"""Celery tasks that send the account emails in the background.

Why this exists
---------------
Sending mail means talking to an SMTP server, which can be slow or down.
Doing that inside a request made Register / Resend Code / Forgot Password
wait on the mail server. The views now only *queue* a task (a few
milliseconds against Redis) and answer immediately; a separate worker
process (`celery -A core worker`) does the SMTP work.

What travels through the queue -- and what never does
-----------------------------------------------------
Task arguments are stored in Redis in clear text, so they carry only
identifiers, never secrets:

* verification email: `user_id`, a random `nonce`, and the time the code
  was issued. The 6-digit code is NOT an argument. It is derived from
  (user_id, nonce) with an HMAC keyed by SECRET_KEY (accounts.otp.
  derive_email_code), so the worker can rebuild exactly the code whose
  hash was stored, while the queue only ever sees a nonce that is useless
  without SECRET_KEY.
* password-reset email: `user_id`, the site `origin`, and a random
  `request_id`. The reset token is created by the worker at send time.
* the password is never involved at all.

Tasks return None and no result backend is configured, so nothing is
stored as a result; log lines contain user ids and error class names only
(no email address, code, token or password).

Delivery guarantees
-------------------
Workers acknowledge late (a crashed worker's task is redelivered), so
every task is idempotent:

* it first checks that the work is still wanted (the code is still the
  live one, not superseded by a newer Resend, not expired, user not
  already verified);
* it records a "sent" marker in Redis once the SMTP call succeeded, so a
  redelivered or duplicated task does not email the user again (if Redis
  is unreachable the marker is skipped and at worst one duplicate email
  is sent -- a duplicate is better than a lost verification email).

Only temporary failures are retried (network errors, dropped connections,
SMTP 4xx replies) with exponential backoff and jitter; permanent ones
(bad credentials, rejected sender/recipient, SMTP 5xx, misconfiguration)
are logged once and dropped.
"""

import logging
import random
import smtplib
import ssl
import uuid
from datetime import datetime
from urllib.parse import urlsplit

import redis
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth import get_user_model

from accounts.emails import send_password_reset_email, send_verification_email
from accounts.models import EmailVerificationCode
from core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

EMAIL_TASK_MAX_RETRIES = 5
EMAIL_TASK_RETRY_BASE_SECONDS = 15
EMAIL_TASK_RETRY_MAX_SECONDS = 300
# How long a "this email was already sent" marker is remembered. Far longer
# than any retry / redelivery window.
EMAIL_SENT_MARKER_TTL_SECONDS = 24 * 60 * 60


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------


def is_transient_email_error(exc):
    """True if sending might succeed if tried again later.

    Retrying a permanent error (wrong SMTP password, rejected recipient...)
    only delays the inevitable and hammers the mail server, so anything not
    positively known to be temporary is treated as permanent.
    """
    if isinstance(exc, SoftTimeLimitExceeded):
        return True

    # smtplib.SMTPException is itself an OSError subclass, so the SMTP
    # cases must be decided before the generic network-error check below.
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [code for code, _ in exc.recipients.values()]
        return bool(codes) and all(400 <= code < 500 for code in codes)
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return True
    if isinstance(exc, smtplib.SMTPResponseException):
        # 4xx = "try again later"; 5xx (including 535 bad credentials,
        # 550 mailbox unavailable, 554 rejected) = permanent.
        return 400 <= exc.smtp_code < 500
    if isinstance(exc, smtplib.SMTPException):
        return False

    # A certificate problem is a configuration error, not a blip.
    if isinstance(exc, ssl.SSLCertVerificationError):
        return False
    # DNS failures, refused/reset connections, timeouts, TLS hiccups.
    return isinstance(exc, (OSError, TimeoutError))


def _describe(exc):
    """Log-safe description of an error: class (and SMTP code) only.

    The message is deliberately left out -- SMTP errors often echo the
    recipient's address back.
    """
    code = getattr(exc, "smtp_code", None)
    name = type(exc).__name__
    return f"{name} (SMTP {code})" if code else name


# ---------------------------------------------------------------------------
# Idempotency ("already sent") markers
# ---------------------------------------------------------------------------


def _sent_key(kind, request_id):
    return f"nexora:email-sent:{kind}:{request_id}"


def _already_sent(key):
    try:
        return bool(get_redis_client().exists(key))
    except redis.exceptions.RedisError:
        logger.warning("Could not check the email 'sent' marker (Redis).")
        return False


def _mark_sent(key):
    try:
        get_redis_client().set(key, "1", ex=EMAIL_SENT_MARKER_TTL_SECONDS)
    except redis.exceptions.RedisError:
        logger.warning("Could not store the email 'sent' marker (Redis).")


# ---------------------------------------------------------------------------
# Shared delivery flow
# ---------------------------------------------------------------------------


def _deliver(task, *, kind, user_id, request_id, send):
    """Run `send()` once per `request_id`, retrying temporary failures.

    Returns None. Raises celery.exceptions.Retry to reschedule; every other
    outcome (sent, skipped, permanent failure, out of retries) just returns.
    """
    key = _sent_key(kind, request_id)
    if _already_sent(key):
        logger.info(
            "Skipping %s email for user %s: already sent.", kind, user_id
        )
        return

    failure = None
    try:
        send()
    except Exception as exc:  # classified below
        failure = exc

    if failure is None:
        _mark_sent(key)
        logger.info("Sent %s email for user %s.", kind, user_id)
        return

    detail = _describe(failure)
    if not is_transient_email_error(failure):
        logger.error(
            "Permanent failure sending %s email for user %s: %s. "
            "Not retrying.",
            kind,
            user_id,
            detail,
        )
        return

    retries = task.request.retries
    if retries >= task.max_retries:
        logger.error(
            "Giving up on %s email for user %s after %s retries: %s.",
            kind,
            user_id,
            retries,
            detail,
        )
        return

    countdown = min(
        EMAIL_TASK_RETRY_BASE_SECONDS * (2**retries),
        EMAIL_TASK_RETRY_MAX_SECONDS,
    ) + random.uniform(0, 5)
    logger.warning(
        "Temporary failure sending %s email for user %s: %s. "
        "Retry %s/%s in %.0fs.",
        kind,
        user_id,
        detail,
        retries + 1,
        task.max_retries,
        countdown,
    )
    # No `exc=`: Celery would log the exception's repr, which can contain
    # the recipient's address.
    raise task.retry(countdown=countdown)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    name="accounts.send_verification_email",
    ignore_result=True,
    max_retries=EMAIL_TASK_MAX_RETRIES,
)
def send_verification_email_task(self, user_id, nonce, issued_at):
    """Email the 6-digit verification code issued at `issued_at`.

    Used by Register and by Resend Code (both go through
    accounts.otp.start_email_verification).
    """
    # Imported here because accounts.otp imports this module to queue the
    # task; by the time a task runs both modules are fully loaded.
    from accounts.otp import derive_email_code

    otp = (
        EmailVerificationCode.objects.select_related("user")
        .filter(user_id=user_id)
        .first()
    )
    if otp is None or otp.user.is_verified:
        logger.info(
            "Skipping verification email for user %s: nothing pending.",
            user_id,
        )
        return
    # `last_sent_at` is stamped by every issue (Register / Resend), so it
    # tells whether this task's code is still the live one.
    if otp.last_sent_at != datetime.fromisoformat(issued_at):
        logger.info(
            "Skipping verification email for user %s: superseded by a "
            "newer code.",
            user_id,
        )
        return
    if otp.is_expired():
        logger.info(
            "Skipping verification email for user %s: code expired.",
            user_id,
        )
        return
    user = otp.user
    if not user.email:
        logger.warning("User %s has no email address.", user_id)
        return

    code = derive_email_code(user_id, nonce)
    _deliver(
        self,
        kind="verification",
        user_id=user_id,
        request_id=nonce,
        send=lambda: send_verification_email(user, code),
    )


@shared_task(
    bind=True,
    name="accounts.send_password_reset_email",
    ignore_result=True,
    max_retries=EMAIL_TASK_MAX_RETRIES,
)
def send_password_reset_email_task(self, user_id, origin, request_id):
    """Email a password-reset link (Forgot Password)."""
    parts = urlsplit(origin)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        logger.error(
            "Not sending password reset email for user %s: invalid origin.",
            user_id,
        )
        return

    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None or not user.email:
        logger.info(
            "Skipping password reset email for user %s: no active "
            "account with an email address.",
            user_id,
        )
        return

    _deliver(
        self,
        kind="password-reset",
        user_id=user_id,
        request_id=request_id,
        send=lambda: send_password_reset_email(user, origin),
    )


# ---------------------------------------------------------------------------
# Queueing helpers (called from the web process)
# ---------------------------------------------------------------------------
# These only publish a message to the broker. They raise (kombu's
# OperationalError) if the broker is unreachable; callers decide whether
# that should fail the request.


def queue_verification_email(user_id, nonce, issued_at):
    send_verification_email_task.apply_async(
        kwargs={
            "user_id": user_id,
            "nonce": nonce,
            "issued_at": issued_at.isoformat(),
        }
    )


def queue_password_reset_email(request, user):
    send_password_reset_email_task.apply_async(
        kwargs={
            "user_id": user.pk,
            # scheme://host the user is on, no trailing slash.
            "origin": request.build_absolute_uri("/").rstrip("/"),
            "request_id": uuid.uuid4().hex,
        }
    )
