"""
6-digit one-time-code email verification.

Replaces the old JWT verification-link flow (see accounts/tokens.py,
now password-reset only). The pending user is never taken from the
request body -- only from this *server-side* session key
(EMAIL_VERIFICATION_SESSION_KEY) -- so a visitor can never verify or
resend a code for an account that isn't the one they just registered
in this browser session.
"""

import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from accounts.constants import (
    EMAIL_OTP_EXP_MINUTES,
    EMAIL_OTP_LENGTH,
    EMAIL_OTP_MAX_ATTEMPTS,
    EMAIL_OTP_RESEND_COOLDOWN_SECONDS,
    EMAIL_VERIFICATION_SESSION_KEY,
)
from accounts.emails import send_verification_email
from accounts.models import EmailVerificationCode


class OTPError(Exception):
    """Raised with a user-facing message for any invalid/expired/
    exhausted/rate-limited verification or resend attempt."""


def _generate_code():
    # secrets.randbelow is a CSPRNG (unlike `random`), so the code is not
    # guessable; zero-padded so e.g. 483 -> "000483".
    upper = 10**EMAIL_OTP_LENGTH
    return str(secrets.randbelow(upper)).zfill(EMAIL_OTP_LENGTH)


def start_email_verification(request, user):
    """
    Generates a fresh code for `user`, replacing any previous one,
    points this session at `user` for the verify/resend endpoints, and
    emails the code. Used by both Register and "Resend Code".
    """
    code = _generate_code()
    now = timezone.now()
    EmailVerificationCode.objects.update_or_create(
        user=user,
        defaults={
            "code_hash": make_password(code),
            "attempts": 0,
            "last_sent_at": now,
            "expires_at": now + timedelta(minutes=EMAIL_OTP_EXP_MINUTES),
        },
    )
    # Only the pk is stored -- the client can read/change the session
    # cookie's identity but not its signed, server-side contents.
    request.session[EMAIL_VERIFICATION_SESSION_KEY] = user.pk
    request.session.set_expiry(EMAIL_OTP_EXP_MINUTES * 60)
    send_verification_email(user, code)


def get_pending_verification_user(request):
    """The User tied to this session's pending verification, or None."""
    user_id = request.session.get(EMAIL_VERIFICATION_SESSION_KEY)
    if not user_id:
        return None
    User = get_user_model()
    return User.objects.filter(pk=user_id, is_verified=False).first()


def verify_email_code(request, raw_code):
    """
    Validates `raw_code` against the pending verification tied to this
    session. On success, marks the user verified, invalidates the code,
    clears the session challenge, and returns the user (the caller is
    responsible for calling django.contrib.auth.login with it).
    Raises OTPError with a user-facing message on any failure.
    """
    user = get_pending_verification_user(request)
    if user is None:
        raise OTPError(
            "Your verification session has expired. Please register again "
            "or request a new code."
        )

    otp = EmailVerificationCode.objects.filter(user=user).first()
    if otp is None:
        raise OTPError(
            "No verification code is pending for this account. Please "
            "request a new code."
        )

    if otp.attempts >= EMAIL_OTP_MAX_ATTEMPTS:
        raise OTPError(
            "Too many incorrect attempts. Please request a new code."
        )

    if otp.is_expired():
        raise OTPError("This code has expired. Please request a new code.")

    if not check_password(raw_code, otp.code_hash):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        remaining = EMAIL_OTP_MAX_ATTEMPTS - otp.attempts
        if remaining <= 0:
            raise OTPError(
                "Too many incorrect attempts. Please request a new code."
            )
        raise OTPError("The code you entered is incorrect.")

    user.is_verified = True
    user.save(update_fields=["is_verified"])
    otp.delete()
    request.session.pop(EMAIL_VERIFICATION_SESSION_KEY, None)
    return user


def resend_email_verification(request):
    """
    Issues a new code for this session's pending user, subject to a
    short cooldown since the previous code was sent. Raises OTPError
    (safe to show to the user) if there's no pending verification or
    the cooldown hasn't elapsed yet.
    """
    user = get_pending_verification_user(request)
    if user is None:
        raise OTPError(
            "Your verification session has expired. Please register again."
        )

    otp = EmailVerificationCode.objects.filter(user=user).first()
    if otp is not None:
        elapsed = (timezone.now() - otp.last_sent_at).total_seconds()
        if elapsed < EMAIL_OTP_RESEND_COOLDOWN_SECONDS:
            wait = max(1, int(EMAIL_OTP_RESEND_COOLDOWN_SECONDS - elapsed))
            raise OTPError(
                f"Please wait {wait} seconds before requesting another code."
            )

    start_email_verification(request, user)
