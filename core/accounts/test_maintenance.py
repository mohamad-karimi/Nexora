"""Tests for the scheduled cleanup tasks (accounts.maintenance).

They run the tasks the way a worker would (Celery is eager in the suite,
see conftest.py) against real rows: real OTP rows created through the
register API, real sessions created by visiting the register page, real
refresh tokens from simplejwt.
"""

import re
from datetime import timedelta
from unittest import mock

import redis
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from accounts import maintenance
from accounts.constants import SECURITY_CODE_SESSION_KEY
from accounts.models import EmailVerificationCode

User = get_user_model()

OTP_TASK = maintenance.cleanup_expired_otp_codes
SESSION_TASK = maintenance.cleanup_expired_sessions
JWT_TASK = maintenance.cleanup_expired_jwt_tokens

PASSWORD = "S3cure!Passw0rd"

# A retried task is only re-run inside apply() when exceptions are not
# propagated (same reason as in test_email_tasks.py).
retries_run_inline = override_settings(CELERY_TASK_EAGER_PROPAGATES=False)


def make_user(name):
    return User.objects.create_user(
        username=name, email=f"{name}@example.com", password=PASSWORD
    )


def make_otp(user, *, expired_ago=None, expires_in=None):
    now = timezone.now()
    expires_at = (
        now - expired_ago if expired_ago is not None else now + expires_in
    )
    return EmailVerificationCode.objects.create(
        user=user,
        code_hash="hash",
        last_sent_at=now - timedelta(days=3),
        expires_at=expires_at,
    )


def make_session(key, *, expires_in):
    return Session.objects.create(
        session_key=key,
        session_data="x",
        expire_date=timezone.now() + expires_in,
    )


def make_token(user, *, expires_in, blacklisted=False):
    refresh = RefreshToken.for_user(user)
    outstanding = OutstandingToken.objects.get(jti=refresh["jti"])
    outstanding.expires_at = timezone.now() + expires_in
    outstanding.save(update_fields=["expires_at"])
    if blacklisted:
        BlacklistedToken.objects.create(token=outstanding)
    return outstanding


class ExpiredOtpCleanupTests(TestCase):
    def test_removes_only_codes_expired_beyond_the_retention(self):
        users = {n: make_user(n) for n in ("old", "recent", "live", "gone")}
        make_otp(users["old"], expired_ago=timedelta(days=3))
        make_otp(users["gone"], expired_ago=maintenance.OTP_RETENTION * 2)
        make_otp(users["recent"], expired_ago=timedelta(hours=1))
        make_otp(users["live"], expires_in=timedelta(minutes=5))

        OTP_TASK.apply()

        self.assertEqual(
            set(
                EmailVerificationCode.objects.values_list(
                    "user__username", flat=True
                )
            ),
            {"recent", "live"},
        )
        # Only the code rows go -- never the accounts themselves.
        self.assertEqual(User.objects.count(), 4)

    def test_is_idempotent(self):
        make_otp(make_user("old"), expired_ago=timedelta(days=3))
        OTP_TASK.apply()
        OTP_TASK.apply()
        self.assertFalse(EmailVerificationCode.objects.exists())

    def test_verification_flow_still_works_after_the_cleanup(self):
        """A user whose expired code was swept can just request a new one."""
        client = APIClient()
        client.get("/register/")
        client.post(
            "/api/v1/auth/register/",
            {
                "username": "sweepme",
                "email": "sweepme@example.com",
                "password": PASSWORD,
                "security_code": client.session[SECURITY_CODE_SESSION_KEY],
                "agree_terms": True,
                "account_type": "customer",
            },
            format="json",
        )
        self.assertEqual(len(mail.outbox), 1)
        EmailVerificationCode.objects.update(
            last_sent_at=timezone.now() - timedelta(days=3),
            expires_at=timezone.now() - timedelta(days=3),
        )

        OTP_TASK.apply()
        self.assertFalse(EmailVerificationCode.objects.exists())

        response = client.post(
            "/api/v1/auth/resend-verification/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        verify = client.post(
            "/api/v1/auth/verify-email/", {"code": code}, format="json"
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)


class ExpiredSessionCleanupTests(TestCase):
    def test_removes_only_expired_sessions(self):
        make_session("expired-1", expires_in=-timedelta(seconds=1))
        make_session("expired-2", expires_in=-timedelta(days=30))
        make_session("live", expires_in=timedelta(days=1))

        SESSION_TASK.apply()

        self.assertEqual(
            list(Session.objects.values_list("session_key", flat=True)),
            ["live"],
        )

    def test_cleans_sessions_created_by_real_visits(self):
        client = APIClient()
        client.get("/register/")
        client.get("/login/")
        self.assertEqual(Session.objects.count(), 1)  # one visitor
        other = APIClient()
        other.get("/register/")
        self.assertEqual(Session.objects.count(), 2)

        # The first visitor never came back: their session expires.
        Session.objects.filter(
            session_key=client.session.session_key
        ).update(expire_date=timezone.now() - timedelta(minutes=1))
        SESSION_TASK.apply()

        self.assertEqual(
            list(Session.objects.values_list("session_key", flat=True)),
            [other.session.session_key],
        )

    def test_matches_djangos_clearsessions(self):
        for i in range(3):
            make_session(f"e{i}", expires_in=-timedelta(hours=i + 1))
        make_session("live", expires_in=timedelta(hours=1))
        SESSION_TASK.apply()
        ours = set(Session.objects.values_list("session_key", flat=True))

        Session.objects.all().delete()
        for i in range(3):
            make_session(f"e{i}", expires_in=-timedelta(hours=i + 1))
        make_session("live", expires_in=timedelta(hours=1))
        call_command("clearsessions")
        theirs = set(Session.objects.values_list("session_key", flat=True))
        self.assertEqual(ours, theirs)


class ExpiredJwtCleanupTests(TestCase):
    def test_removes_expired_tokens_with_their_blacklist_entries(self):
        user = make_user("jwtuser")
        expired = make_token(user, expires_in=-timedelta(minutes=1))
        expired_bl = make_token(
            user, expires_in=-timedelta(days=2), blacklisted=True
        )
        live = make_token(user, expires_in=timedelta(days=1))
        live_bl = make_token(
            user, expires_in=timedelta(days=1), blacklisted=True
        )

        JWT_TASK.apply()

        self.assertEqual(
            set(OutstandingToken.objects.values_list("pk", flat=True)),
            {live.pk, live_bl.pk},
        )
        self.assertFalse(
            BlacklistedToken.objects.filter(
                token__in=[expired.pk, expired_bl.pk]
            ).exists()
        )
        # A still-valid token that was blacklisted (e.g. after rotation)
        # must stay blacklisted, or it could be replayed.
        self.assertTrue(
            BlacklistedToken.objects.filter(token=live_bl).exists()
        )
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_logs_contain_counts_only(self):
        user = make_user("jwtuser")
        token = make_token(user, expires_in=-timedelta(days=1))
        raw, jti = token.token, token.jti
        with self.assertLogs("accounts.maintenance", level="INFO") as logs:
            JWT_TASK.apply()
        output = "\n".join(logs.output)
        self.assertIn("deleted 1 row(s)", output)
        self.assertNotIn(raw, output)
        self.assertNotIn(jti, output)
        self.assertNotIn(user.email, output)


class BatchingAndBudgetTests(TestCase):
    def setUp(self):
        for i in range(5):
            make_session(f"e{i}", expires_in=-timedelta(days=1))

    def test_deletes_everything_across_several_batches(self):
        with mock.patch.object(maintenance, "CLEANUP_BATCH_SIZE", 2):
            with self.assertLogs("accounts.maintenance", level="INFO") as logs:
                SESSION_TASK.apply()
        self.assertFalse(Session.objects.exists())
        self.assertIn("deleted 5 row(s).", "\n".join(logs.output))

    def test_time_budget_stops_a_run_and_the_next_run_continues(self):
        with mock.patch.object(
            maintenance, "CLEANUP_BATCH_SIZE", 2
        ), mock.patch.object(maintenance, "CLEANUP_TIME_BUDGET_SECONDS", 0):
            with self.assertLogs("accounts.maintenance", level="INFO") as logs:
                SESSION_TASK.apply()
            self.assertEqual(Session.objects.count(), 3)
            self.assertIn("time budget reached", "\n".join(logs.output))
            SESSION_TASK.apply()
            SESSION_TASK.apply()
        self.assertFalse(Session.objects.exists())


class SingleRunAndFailureTests(TestCase):
    LOCK = "nexora:lock:expired-sessions"

    def setUp(self):
        make_session("expired", expires_in=-timedelta(days=1))

    def test_a_second_run_while_one_is_in_progress_is_skipped(self):
        fake_redis = maintenance.get_redis_client()
        fake_redis.store[self.LOCK] = "held by another run"

        with self.assertLogs("accounts.maintenance", level="INFO") as logs:
            SESSION_TASK.apply()

        self.assertIn("another run is in progress", "\n".join(logs.output))
        self.assertEqual(Session.objects.count(), 1)  # untouched
        # The skipped run must not release the other run's lock.
        self.assertIn(self.LOCK, fake_redis.store)

    def test_the_lock_is_released_after_a_run(self):
        SESSION_TASK.apply()
        self.assertNotIn(self.LOCK, maintenance.get_redis_client().store)

    def test_the_lock_is_released_when_the_work_fails(self):
        with mock.patch.object(
            maintenance, "_delete_in_batches", side_effect=RuntimeError("bug")
        ):
            result = SESSION_TASK.apply(throw=False)
        self.assertTrue(result.failed())
        self.assertNotIn(self.LOCK, maintenance.get_redis_client().store)

    def test_runs_anyway_when_redis_is_unreachable(self):
        with mock.patch.object(
            maintenance,
            "get_redis_client",
            side_effect=redis.exceptions.ConnectionError("down"),
        ):
            SESSION_TASK.apply()
        self.assertFalse(Session.objects.exists())

    @retries_run_inline
    def test_a_locked_database_is_retried(self):
        with mock.patch.object(
            maintenance,
            "_delete_in_batches",
            side_effect=[OperationalError("database is locked"), (1, True)],
        ) as work:
            result = SESSION_TASK.apply()
        self.assertEqual(work.call_count, 2)
        self.assertTrue(result.successful())

    @retries_run_inline
    def test_other_errors_are_not_retried(self):
        with mock.patch.object(
            maintenance, "_delete_in_batches", side_effect=ValueError("bug")
        ) as work:
            result = SESSION_TASK.apply()
        self.assertEqual(work.call_count, 1)
        self.assertTrue(result.failed())
