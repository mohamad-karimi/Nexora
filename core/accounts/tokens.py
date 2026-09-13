"""
Stateless JWT helpers used by the email-verification and forgot/reset
password flows.

Design notes
------------
- Signed with the project's existing SECRET_KEY (django-decouple env
  config) -- no new secret is introduced.
- Every token carries only the minimum needed to identify the user and
  the purpose it was issued for: `uid`, `purpose`, `exp`. Never the
  password or any other sensitive data.
- Password-reset tokens additionally carry a `pwd` "stamp": a one-way
  hash fragment derived from the user's *current hashed* password
  (hashing an already-hashed value, never the plaintext). Because
  Django's password hash changes completely every time set_password()
  is called, using a reset link invalidates every other outstanding
  reset link for that user -- including itself if replayed -- without
  needing a database-backed token/blacklist table.
"""

import hashlib
from datetime import datetime, timedelta, timezone as dt_timezone

import jwt
from django.conf import settings

from accounts.constants import (
    EMAIL_VERIFY_TOKEN_EXP_MINUTES,
    EMAIL_VERIFY_TOKEN_PURPOSE,
    PASSWORD_RESET_TOKEN_EXP_MINUTES,
    PASSWORD_RESET_TOKEN_PURPOSE,
)

JWT_ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised for any missing/invalid/expired/wrong-purpose token."""


def _password_stamp(user):
    """A short, one-way fingerprint of the user's current password hash.

    Never the password itself, and never the raw password hash either --
    just a digest of it, purely so we can tell whether the password has
    changed since the token was issued.
    """
    return hashlib.sha256(user.password.encode()).hexdigest()[:16]


def _encode(payload):
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode(token, expected_purpose):
    if not token:
        raise TokenError("Missing token.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("This link has expired.")
    except jwt.InvalidTokenError:
        raise TokenError("This link is invalid.")

    if payload.get("purpose") != expected_purpose:
        raise TokenError("This link is invalid.")
    return payload


def make_email_verification_token(user):
    now = datetime.now(dt_timezone.utc)
    payload = {
        "uid": user.pk,
        "purpose": EMAIL_VERIFY_TOKEN_PURPOSE,
        "iat": now,
        "exp": now + timedelta(minutes=EMAIL_VERIFY_TOKEN_EXP_MINUTES),
    }
    return _encode(payload)


def get_user_for_email_verification_token(token):
    """Decode + validate an email-verification token and return its user.

    Raises TokenError if the token is missing/invalid/expired or the
    user no longer exists.
    """
    from django.contrib.auth import get_user_model

    payload = _decode(token, EMAIL_VERIFY_TOKEN_PURPOSE)
    User = get_user_model()
    user = User.objects.filter(pk=payload.get("uid")).first()
    if user is None:
        raise TokenError("This link is invalid.")
    return user


def make_password_reset_token(user):
    now = datetime.now(dt_timezone.utc)
    payload = {
        "uid": user.pk,
        "purpose": PASSWORD_RESET_TOKEN_PURPOSE,
        "pwd": _password_stamp(user),
        "iat": now,
        "exp": now + timedelta(minutes=PASSWORD_RESET_TOKEN_EXP_MINUTES),
    }
    return _encode(payload)


def get_user_for_password_reset_token(token):
    """Decode + validate a password-reset token and return its user.

    Raises TokenError if the token is missing/invalid/expired, the user
    no longer exists, or the token has already been used (its password
    stamp no longer matches the user's current password hash).
    """
    from django.contrib.auth import get_user_model

    payload = _decode(token, PASSWORD_RESET_TOKEN_PURPOSE)
    User = get_user_model()
    user = User.objects.filter(pk=payload.get("uid")).first()
    if user is None:
        raise TokenError("This link is invalid.")
    if payload.get("pwd") != _password_stamp(user):
        # Either the password was already changed with this token (or a
        # newer one), or the token was tampered with.
        raise TokenError("This link has already been used or is no longer valid.")
    return user
