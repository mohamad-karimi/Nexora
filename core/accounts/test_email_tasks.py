"""Tests for the Celery-backed account emails (accounts.tasks).

The suite runs Celery in eager mode (see conftest.py), so a queued task
executes inline and the usual `mail.outbox` assertions keep working. The
tests below that care about *queueing* patch `apply_async`, which is
exactly the call the web process makes -- with it patched nothing can
reach SMTP from the request, which is what they assert.
"""

import json
import re
import smtplib
import ssl
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

import redis
from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from kombu.exceptions import OperationalError
from rest_framework import status
from rest_framework.test import APIClient

from accounts import tasks
from accounts.constants import (
    EMAIL_VERIFICATION_SESSION_KEY,
    SECURITY_CODE_SESSION_KEY,
)
from accounts.models import EmailVerificationCode
from accounts.otp import derive_email_code
from accounts.tokens import get_user_for_password_reset_token

User = get_user_model()

REGISTER_URL = "/api/v1/auth/register/"
VERIFY_URL = "/api/v1/auth/verify-email/"
RESEND_URL = "/api/v1/auth/resend-verification/"
FORGOT_PASSWORD_URL = "/api/v1/auth/forgot-password/"
RESET_PASSWORD_URL = "/api/v1/auth/reset-password/"
PASSWORD = "S3cure!Passw0rd"

VERIFICATION_TASK = tasks.send_verification_email_task
RESET_TASK = tasks.send_password_reset_email_task


# Celery only re-runs a retried task inside apply() (eager mode) when
# exceptions are NOT propagated; the suite default is to propagate them so
# a bug in a task shows up as a failing request.
retries_run_inline = override_settings(CELERY_TASK_EAGER_PROPAGATES=False)


def _apply_kwargs(task, kwargs):
    """Run a task the way a worker would (synchronously, no broker)."""
    return task.apply(kwargs=kwargs)


class _RegistersUsers:
    def _register(self, client=None, **overrides):
        client = client or self.client
        client.get("/register/")
        payload = {
            "username": "taskuser",
            "email": "taskuser@example.com",
            "password": PASSWORD,
            "security_code": client.session[SECURITY_CODE_SESSION_KEY],
            "agree_terms": True,
            "account_type": "customer",
        }
        payload.update(overrides)
        return client.post(REGISTER_URL, payload, format="json")

    @staticmethod
    def _code_from_mail(message=None):
        message = message or mail.outbox[-1]
        return re.search(r"\b(\d{6})\b", message.body).group(1)


class QueueingFromTheRequestTests(_RegistersUsers, TestCase):
    """The web process must only enqueue; SMTP belongs to the worker."""

    def setUp(self):
        self.client = APIClient()

    def test_register_queues_the_email_and_never_touches_smtp(self):
        with mock.patch.object(
            VERIFICATION_TASK, "apply_async"
        ) as queued, mock.patch(
            "accounts.tasks.send_verification_email",
            side_effect=AssertionError("SMTP must not run in a request"),
        ) as smtp:
            response = self._register()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        queued.assert_called_once()
        smtp.assert_not_called()
        self.assertEqual(mail.outbox, [])

        # Everything the verify step needs is already in place.
        user = User.objects.get(username="taskuser")
        self.assertFalse(user.is_verified)
        self.assertTrue(EmailVerificationCode.objects.filter(user=user))
        self.assertEqual(
            self.client.session[EMAIL_VERIFICATION_SESSION_KEY], user.pk
        )

    def test_task_arguments_contain_no_secrets(self):
        with mock.patch.object(VERIFICATION_TASK, "apply_async") as queued:
            self._register()
        kwargs = queued.call_args.kwargs["kwargs"]
        user = User.objects.get(username="taskuser")

        self.assertEqual(set(kwargs), {"user_id", "nonce", "issued_at"})
        self.assertEqual(kwargs["user_id"], user.pk)

        # Run it like a worker would and compare against what was emailed.
        _apply_kwargs(VERIFICATION_TASK, kwargs)
        code = self._code_from_mail()
        serialized = json.dumps(kwargs)
        self.assertNotIn(code, serialized)
        self.assertNotIn(PASSWORD, serialized)
        self.assertNotIn(user.password, serialized)

    def test_worker_sends_the_code_whose_hash_was_stored(self):
        with mock.patch.object(VERIFICATION_TASK, "apply_async") as queued:
            self._register()
        _apply_kwargs(VERIFICATION_TASK, queued.call_args.kwargs["kwargs"])

        code = self._code_from_mail()
        otp = EmailVerificationCode.objects.get(user__username="taskuser")
        self.assertTrue(check_password(code, otp.code_hash))
        # The code is never stored in the clear.
        self.assertNotEqual(otp.code_hash, code)

    def test_register_still_succeeds_when_the_broker_is_down(self):
        with mock.patch.object(
            VERIFICATION_TASK,
            "apply_async",
            side_effect=OperationalError("broker unreachable"),
        ):
            response = self._register()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="taskuser").exists())
        self.assertEqual(mail.outbox, [])

    def test_resend_queues_a_new_task_and_supersedes_the_old_one(self):
        with mock.patch.object(VERIFICATION_TASK, "apply_async") as queued:
            self._register()
            first = queued.call_args.kwargs["kwargs"]
            EmailVerificationCode.objects.update(
                last_sent_at=timezone.now() - timedelta(minutes=5)
            )
            response = self.client.post(RESEND_URL, {}, format="json")
            second = queued.call_args.kwargs["kwargs"]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(queued.call_count, 2)
        self.assertNotEqual(first["nonce"], second["nonce"])
        self.assertEqual(mail.outbox, [])

        # A delayed retry of the first request must not email a code that
        # the Resend has already invalidated ...
        _apply_kwargs(VERIFICATION_TASK, first)
        self.assertEqual(mail.outbox, [])

        # ... while the current one goes out and works.
        _apply_kwargs(VERIFICATION_TASK, second)
        self.assertEqual(len(mail.outbox), 1)
        verify = self.client.post(
            VERIFY_URL, {"code": self._code_from_mail()}, format="json"
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

    def test_resend_reports_an_error_when_the_broker_is_down(self):
        with mock.patch.object(VERIFICATION_TASK, "apply_async"):
            self._register()
        EmailVerificationCode.objects.update(
            last_sent_at=timezone.now() - timedelta(minutes=5)
        )
        with mock.patch.object(
            VERIFICATION_TASK,
            "apply_async",
            side_effect=OperationalError("broker unreachable"),
        ):
            response = self.client.post(RESEND_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_forgot_password_only_queues_and_arguments_are_safe(self):
        user = User.objects.create_user(
            username="forgetful",
            email="forgetful@example.com",
            password=PASSWORD,
        )
        with mock.patch.object(
            RESET_TASK, "apply_async"
        ) as queued, mock.patch(
            "accounts.tasks.send_password_reset_email",
            side_effect=AssertionError("SMTP must not run in a request"),
        ) as smtp:
            response = self.client.post(
                FORGOT_PASSWORD_URL, {"email": user.email}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queued.assert_called_once()
        smtp.assert_not_called()
        kwargs = queued.call_args.kwargs["kwargs"]
        self.assertEqual(set(kwargs), {"user_id", "origin", "request_id"})
        self.assertEqual(kwargs["user_id"], user.pk)
        self.assertEqual(kwargs["origin"], "http://testserver")
        serialized = json.dumps(kwargs)
        self.assertNotIn("token", serialized)
        self.assertNotIn(PASSWORD, serialized)
        self.assertNotIn(user.password, serialized)

    def test_forgot_password_for_unknown_email_queues_nothing(self):
        with mock.patch.object(RESET_TASK, "apply_async") as queued:
            response = self.client.post(
                FORGOT_PASSWORD_URL,
                {"email": "nobody@example.com"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queued.assert_not_called()

    def test_forgot_password_answers_normally_when_the_broker_is_down(self):
        user = User.objects.create_user(
            username="forgetful",
            email="forgetful@example.com",
            password=PASSWORD,
        )
        with mock.patch.object(
            RESET_TASK,
            "apply_async",
            side_effect=OperationalError("broker unreachable"),
        ):
            response = self.client.post(
                FORGOT_PASSWORD_URL, {"email": user.email}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class DeriveEmailCodeTests(TestCase):
    def test_is_deterministic_six_digits(self):
        code = derive_email_code(7, "some-nonce")
        self.assertEqual(code, derive_email_code(7, "some-nonce"))
        self.assertRegex(code, r"^\d{6}$")

    def test_depends_on_user_and_nonce(self):
        self.assertNotEqual(
            derive_email_code(7, "nonce-a"), derive_email_code(7, "nonce-b")
        )
        self.assertNotEqual(
            derive_email_code(7, "nonce-a"), derive_email_code(8, "nonce-a")
        )

    def test_is_keyed_by_the_secret_key(self):
        before = derive_email_code(7, "nonce-a")
        with self.settings(SECRET_KEY="a-different-secret-key"):
            after = derive_email_code(7, "nonce-a")
        self.assertNotEqual(before, after)

    def test_keeps_leading_zeros(self):
        codes = (derive_email_code(1, f"n{i}") for i in range(500))
        self.assertTrue(any(code.startswith("0") for code in codes))


class VerificationEmailTaskTests(_RegistersUsers, TestCase):
    def setUp(self):
        self.client = APIClient()
        with mock.patch.object(VERIFICATION_TASK, "apply_async") as queued:
            self._register()
        self.kwargs = queued.call_args.kwargs["kwargs"]
        self.user = User.objects.get(username="taskuser")

    def test_sends_the_verification_email(self):
        _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Verify your Nexora account")
        self.assertEqual(message.to, ["taskuser@example.com"])
        self.assertIn("Hi taskuser,", message.body)
        self.assertNotIn("http", message.body)

    def test_is_idempotent_for_a_redelivered_task(self):
        _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(len(mail.outbox), 1)

    def test_still_sends_when_redis_is_unreachable(self):
        with mock.patch(
            "accounts.tasks.get_redis_client",
            side_effect=redis.exceptions.ConnectionError("down"),
        ):
            _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(len(mail.outbox), 1)

    def test_skips_when_the_user_is_already_verified(self):
        EmailVerificationCode.objects.filter(user=self.user).delete()
        _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(mail.outbox, [])

    def test_skips_when_the_code_has_expired(self):
        EmailVerificationCode.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(mail.outbox, [])

    def test_skips_a_task_for_a_deleted_user(self):
        self.user.delete()
        _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(mail.outbox, [])

    @retries_run_inline
    def test_temporary_smtp_error_is_retried_until_it_succeeds(self):
        with mock.patch(
            "accounts.tasks.send_verification_email",
            side_effect=[smtplib.SMTPServerDisconnected("dropped"), None],
        ) as smtp:
            result = _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(smtp.call_count, 2)
        self.assertTrue(result.successful())

    @retries_run_inline
    def test_retry_sends_the_same_code_as_the_first_attempt(self):
        # Same (user, nonce) -> same code, so a retry can never email a
        # code that differs from the stored hash.
        seen = []

        def flaky(user, code):
            seen.append(code)
            if len(seen) == 1:
                raise smtplib.SMTPServerDisconnected("dropped")

        with mock.patch("accounts.tasks.send_verification_email", flaky):
            _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1])
        otp = EmailVerificationCode.objects.get(user=self.user)
        self.assertTrue(check_password(seen[0], otp.code_hash))

    def test_permanent_smtp_error_is_not_retried(self):
        with mock.patch(
            "accounts.tasks.send_verification_email",
            side_effect=smtplib.SMTPAuthenticationError(535, b"bad creds"),
        ) as smtp:
            result = _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(smtp.call_count, 1)
        self.assertTrue(result.successful())

    @retries_run_inline
    def test_gives_up_after_the_maximum_number_of_retries(self):
        with mock.patch(
            "accounts.tasks.send_verification_email",
            side_effect=TimeoutError("smtp timed out"),
        ) as smtp:
            result = _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        self.assertEqual(smtp.call_count, tasks.EMAIL_TASK_MAX_RETRIES + 1)
        self.assertTrue(result.successful())

    @retries_run_inline
    def test_logs_never_contain_the_code_or_the_address(self):
        code = derive_email_code(self.user.pk, self.kwargs["nonce"])
        failures = [
            smtplib.SMTPRecipientsRefused(
                {"taskuser@example.com": (550, b"no such user")}
            ),
            smtplib.SMTPServerDisconnected("taskuser@example.com hung up"),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with mock.patch(
                    "accounts.tasks.send_verification_email",
                    side_effect=failure,
                ), self.assertLogs("accounts.tasks", level="INFO") as logs:
                    _apply_kwargs(VERIFICATION_TASK, self.kwargs)
                output = "\n".join(logs.output)
                self.assertNotIn(code, output)
                self.assertNotIn("taskuser@example.com", output)
                self.assertNotIn(self.kwargs["nonce"], output)
                # Cleared between subtests so retries/markers don't leak.
                mail.outbox.clear()

    def test_success_logs_never_contain_the_code_or_the_address(self):
        code = derive_email_code(self.user.pk, self.kwargs["nonce"])
        with self.assertLogs("accounts.tasks", level="INFO") as logs:
            _apply_kwargs(VERIFICATION_TASK, self.kwargs)
        output = "\n".join(logs.output)
        self.assertNotIn(code, output)
        self.assertNotIn("taskuser@example.com", output)


class PasswordResetEmailTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="resetter",
            email="resetter@example.com",
            password=PASSWORD,
        )
        self.kwargs = {
            "user_id": self.user.pk,
            "origin": "https://shop.example.com",
            "request_id": "req-1",
        }

    def test_sends_the_reset_link_with_a_valid_token(self):
        _apply_kwargs(RESET_TASK, self.kwargs)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Reset your Nexora password")
        self.assertEqual(message.to, ["resetter@example.com"])
        match = re.search(
            r"(https://shop\.example\.com/reset-password/\?token=)([^\s&]+)",
            message.body,
        )
        self.assertIsNotNone(match, "no reset link in the email body")
        self.assertEqual(
            get_user_for_password_reset_token(match.group(2)), self.user
        )

    def test_is_idempotent_for_a_redelivered_task(self):
        _apply_kwargs(RESET_TASK, self.kwargs)
        _apply_kwargs(RESET_TASK, self.kwargs)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_new_request_sends_a_new_email(self):
        _apply_kwargs(RESET_TASK, self.kwargs)
        _apply_kwargs(RESET_TASK, {**self.kwargs, "request_id": "req-2"})
        self.assertEqual(len(mail.outbox), 2)

    def test_skips_inactive_and_missing_users(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        _apply_kwargs(RESET_TASK, self.kwargs)
        _apply_kwargs(RESET_TASK, {**self.kwargs, "user_id": 999999})
        self.assertEqual(mail.outbox, [])

    def test_refuses_an_invalid_origin(self):
        bad_origins = (
            "",
            "javascript:alert(1)",
            "shop.example.com",
            "ftp://x",
        )
        for origin in bad_origins:
            with self.subTest(origin=origin):
                _apply_kwargs(
                    RESET_TASK,
                    {**self.kwargs, "origin": origin, "request_id": origin},
                )
        self.assertEqual(mail.outbox, [])

    @retries_run_inline
    def test_temporary_error_is_retried_and_permanent_is_not(self):
        with mock.patch(
            "accounts.tasks.send_password_reset_email",
            side_effect=[ConnectionResetError("reset"), None],
        ) as smtp:
            _apply_kwargs(RESET_TASK, self.kwargs)
        self.assertEqual(smtp.call_count, 2)

        with mock.patch(
            "accounts.tasks.send_password_reset_email",
            side_effect=smtplib.SMTPSenderRefused(550, b"no", "from@x.com"),
        ) as smtp:
            _apply_kwargs(RESET_TASK, {**self.kwargs, "request_id": "req-9"})
        self.assertEqual(smtp.call_count, 1)

    def test_logs_never_contain_the_token_or_the_address(self):
        with mock.patch(
            "accounts.tasks.send_password_reset_email",
            side_effect=smtplib.SMTPRecipientsRefused(
                {"resetter@example.com": (550, b"no such user")}
            ),
        ), self.assertLogs("accounts.tasks", level="INFO") as logs:
            _apply_kwargs(RESET_TASK, self.kwargs)
        self.assertNotIn("resetter@example.com", "\n".join(logs.output))

    def test_full_flow_through_the_api_still_resets_the_password(self):
        client = APIClient()
        client.post(
            FORGOT_PASSWORD_URL, {"email": self.user.email}, format="json"
        )
        self.assertEqual(len(mail.outbox), 1)
        token = re.search(r"token=([^\s&]+)", mail.outbox[0].body).group(1)
        response = client.post(
            RESET_PASSWORD_URL,
            {
                "token": token,
                "new_password": "Br4ndNewPassw0rd!",
                "confirm_password": "Br4ndNewPassw0rd!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Br4ndNewPassw0rd!"))


class TransientErrorClassificationTests(TestCase):
    def test_temporary_errors(self):
        temporary = [
            smtplib.SMTPServerDisconnected("closed"),
            smtplib.SMTPConnectError(421, b"try later"),
            smtplib.SMTPDataError(451, b"local error"),
            smtplib.SMTPSenderRefused(452, b"insufficient storage", "a@b.c"),
            smtplib.SMTPAuthenticationError(454, b"temporary auth failure"),
            smtplib.SMTPRecipientsRefused({"a@b.c": (450, b"mailbox busy")}),
            ConnectionRefusedError("refused"),
            ConnectionResetError("reset"),
            TimeoutError("timed out"),
            OSError("network unreachable"),
            ssl.SSLError("handshake failure"),
            SoftTimeLimitExceeded(),
        ]
        for exc in temporary:
            with self.subTest(exc=repr(exc)):
                self.assertTrue(tasks.is_transient_email_error(exc))

    def test_permanent_errors(self):
        permanent = [
            smtplib.SMTPAuthenticationError(535, b"bad credentials"),
            smtplib.SMTPSenderRefused(550, b"sender rejected", "a@b.c"),
            smtplib.SMTPDataError(554, b"rejected as spam"),
            smtplib.SMTPRecipientsRefused({"a@b.c": (550, b"no mailbox")}),
            smtplib.SMTPRecipientsRefused({}),
            smtplib.SMTPNotSupportedError("no AUTH"),
            smtplib.SMTPException("something else"),
            ssl.SSLCertVerificationError("bad certificate"),
            ValueError("bad header"),
            RuntimeError("bug"),
        ]
        for exc in permanent:
            with self.subTest(exc=repr(exc)):
                self.assertFalse(tasks.is_transient_email_error(exc))


class RetryBackoffTests(TestCase):
    def _countdown_for(self, retries):
        task = SimpleNamespace(
            request=SimpleNamespace(retries=retries),
            max_retries=tasks.EMAIL_TASK_MAX_RETRIES,
            retry=mock.Mock(side_effect=Retry()),
        )
        with self.assertRaises(Retry):
            tasks._deliver(
                task,
                kind="verification",
                user_id=1,
                request_id=f"backoff-{retries}",
                send=mock.Mock(side_effect=TimeoutError("slow")),
            )
        (call,) = task.retry.call_args_list
        self.assertNotIn("exc", call.kwargs)  # never log the raw error
        return call.kwargs["countdown"]

    def test_backoff_grows_and_is_capped(self):
        base = tasks.EMAIL_TASK_RETRY_BASE_SECONDS
        cap = tasks.EMAIL_TASK_RETRY_MAX_SECONDS
        for retries in range(tasks.EMAIL_TASK_MAX_RETRIES):
            expected = min(base * 2**retries, cap)
            countdown = self._countdown_for(retries)
            self.assertGreaterEqual(countdown, expected)
            self.assertLessEqual(countdown, expected + 5)
