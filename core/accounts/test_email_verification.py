import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.constants import (
    EMAIL_OTP_MAX_ATTEMPTS,
    EMAIL_VERIFICATION_SESSION_KEY,
    SECURITY_CODE_SESSION_KEY,
)
from accounts.models import EmailVerificationCode

User = get_user_model()

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
VERIFY_URL = "/api/v1/auth/verify-email/"
RESEND_URL = "/api/v1/auth/resend-verification/"
FORGOT_PASSWORD_URL = "/api/v1/auth/forgot-password/"
RESET_PASSWORD_URL = "/api/v1/auth/reset-password/"


class EmailVerificationOTPTestCase(TestCase):
    """
    Mandatory scenarios for the JWT-link -> 6-digit-OTP email verification
    rewrite.
    """

    def setUp(self):
        self.client = APIClient()
        self.register_page_url = reverse("accounts:register")

    def _get_security_code(self):
        self.client.get(self.register_page_url)
        return self.client.session[SECURITY_CODE_SESSION_KEY]

    def _register(self, **overrides):
        payload = {
            "username": "otpuser1",
            "email": "otpuser1@example.com",
            "password": "S3cure!Passw0rd",
            "security_code": self._get_security_code(),
            "agree_terms": True,
            "account_type": "customer",
        }
        payload.update(overrides)
        return self.client.post(REGISTER_URL, payload, format="json")

    def _latest_code(self, user):
        """Pull the real OTP straight out of the email body -- exactly
        what the user would type in, never guessed."""
        body = mail.outbox[-1].body
        match = re.search(r"\b(\d{6})\b", body)
        self.assertIsNotNone(
            match, "verification email did not contain a 6-digit code"
        )
        return match.group(1)

    # 1 & 2: Register -> is_verified=False, and a 6-digit code is emailed.
    def test_register_creates_unverified_user_and_emails_a_6_digit_code(self):
        response = self._register()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="otpuser1")
        self.assertFalse(user.is_verified)

        self.assertEqual(len(mail.outbox), 1)
        code = self._latest_code(user)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

        # The code is hashed at rest, never stored in plaintext.
        otp = EmailVerificationCode.objects.get(user=user)
        self.assertNotEqual(otp.code_hash, code)

        # Registering does not log the user in.
        self.assertNotIn("_auth_user_id", self.client.session)
        # The session instead carries a private reference to the pending
        # account for the verify/resend endpoints.
        self.assertEqual(
            self.client.session[EMAIL_VERIFICATION_SESSION_KEY], user.pk
        )

    # 3: no JWT verification link anywhere in the email.
    def test_verification_email_contains_no_link(self):
        self._register()
        body = mail.outbox[-1].body
        self.assertNotIn("http://", body)
        self.assertNotIn("https://", body)
        self.assertNotIn("verify-email", body)

    # 5, 6/7: correct code verifies + auto-logs in + account is reachable.
    def test_correct_code_verifies_and_logs_in(self):
        self._register()
        user = User.objects.get(username="otpuser1")
        code = self._latest_code(user)

        response = self.client.post(VERIFY_URL, {"code": code}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.is_verified)

        # Auto-login: the session is now authenticated as this user, no
        # separate call to /auth/login/ needed, and the pending-verification
        # challenge has been cleared.
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertNotIn(EMAIL_VERIFICATION_SESSION_KEY, self.client.session)

        # The code is invalidated (one-time use) immediately on success.
        self.assertFalse(
            EmailVerificationCode.objects.filter(user=user).exists()
        )

        # /account/ (and any other verified-only endpoint) is now reachable
        # without hitting the login page again.
        me_response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)

    # 8: wrong code -> clear, generic error; account stays unverified.
    def test_wrong_code_is_rejected_with_clear_error(self):
        self._register()
        user = User.objects.get(username="otpuser1")
        real_code = self._latest_code(user)
        wrong_code = "111111" if real_code != "111111" else "222222"

        response = self.client.post(
            VERIFY_URL, {"code": wrong_code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

        user.refresh_from_db()
        self.assertFalse(user.is_verified)

    # 9: expired code -> rejected.
    def test_expired_code_is_rejected(self):
        self._register()
        user = User.objects.get(username="otpuser1")
        code = self._latest_code(user)

        EmailVerificationCode.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        response = self.client.post(VERIFY_URL, {"code": code}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.data["detail"].lower())

    # 10: a code that already succeeded once can't be replayed.
    def test_used_code_cannot_be_reused(self):
        self._register()
        user = User.objects.get(username="otpuser1")
        code = self._latest_code(user)

        first = self.client.post(VERIFY_URL, {"code": code}, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        # A brand-new, unauthenticated session trying the same, now-dead
        # code (no pending-verification session of its own either way).
        other_client = APIClient()
        second = other_client.post(VERIFY_URL, {"code": code}, format="json")
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    # 11: brute-force protection -- too many wrong attempts locks the code.
    def test_too_many_wrong_attempts_locks_the_code(self):
        self._register()
        user = User.objects.get(username="otpuser1")
        real_code = self._latest_code(user)
        wrong_code = "111111" if real_code != "111111" else "222222"

        for _ in range(EMAIL_OTP_MAX_ATTEMPTS):
            response = self.client.post(
                VERIFY_URL, {"code": wrong_code}, format="json"
            )
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST
            )

        # Even the *correct* code is now rejected -- the code was
        # invalidated by too many failed attempts, not just "still wrong".
        response = self.client.post(
            VERIFY_URL, {"code": real_code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("too many", response.data["detail"].lower())

    # 12: resend invalidates the old code and sends a fresh one.
    def test_resend_invalidates_old_code_and_sends_new_one(self):
        self._register()
        user = User.objects.get(username="otpuser1")
        old_code = self._latest_code(user)

        # Make the previous send look old enough to be past the cooldown.
        EmailVerificationCode.objects.filter(user=user).update(
            last_sent_at=timezone.now() - timedelta(minutes=5)
        )

        response = self.client.post(RESEND_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)

        new_code = self._latest_code(user)
        self.assertNotEqual(old_code, new_code)

        # The old code no longer verifies the account.
        old_attempt = self.client.post(
            VERIFY_URL, {"code": old_code}, format="json"
        )
        self.assertEqual(old_attempt.status_code, status.HTTP_400_BAD_REQUEST)

        # The new code does.
        new_attempt = self.client.post(
            VERIFY_URL, {"code": new_code}, format="json"
        )
        self.assertEqual(new_attempt.status_code, status.HTTP_200_OK)

    def test_resend_is_rate_limited(self):
        self._register()
        # Immediately resending, with no time elapsed, must be refused.
        response = self.client.post(RESEND_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 1)

    # 13: the target account is taken only from the server-side session --
    # never from the request body -- so one account's pending verification
    # can never be used to verify a different account.
    def test_cannot_verify_a_different_account_via_request_body(self):
        self._register(username="victim", email="victim@example.com")
        victim = User.objects.get(username="victim")
        victim_code = self._latest_code(victim)

        # A second, unrelated registration in a fresh (attacker) session.
        attacker_client = APIClient()
        attacker_client.get(self.register_page_url)
        attacker_security_code = attacker_client.session[
            SECURITY_CODE_SESSION_KEY
        ]
        attacker_client.post(
            REGISTER_URL,
            {
                "username": "attacker",
                "email": "attacker@example.com",
                "password": "An0ther!Passw0rd",
                "security_code": attacker_security_code,
                "agree_terms": True,
                "account_type": "customer",
            },
            format="json",
        )
        attacker = User.objects.get(username="attacker")

        # The endpoint only accepts `code` -- there is no field the
        # attacker's client could set to target the victim's account, and
        # trying extra/unexpected fields changes nothing: the attacker's
        # own session still resolves to the attacker's own pending user.
        response = attacker_client.post(
            VERIFY_URL,
            {
                "code": victim_code,
                "user_id": victim.pk,
                "email": victim.email,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        victim.refresh_from_db()
        attacker.refresh_from_db()
        self.assertFalse(victim.is_verified)
        self.assertFalse(attacker.is_verified)

    # 14: unverified users can't log in or reach account-only endpoints.
    def test_unverified_user_cannot_login_or_access_account(self):
        self._register()
        response = self.client.post(
            LOGIN_URL,
            {
                "username": "otpuser1",
                "password": "S3cure!Passw0rd",
                "security_code": "",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        me_response = self.client.get("/api/v1/auth/me/")
        self.assertNotEqual(me_response.status_code, status.HTTP_200_OK)

    # 15: Forgot/Reset Password is untouched by this change.
    def test_forgot_and_reset_password_flow_still_works(self):
        self._register()
        user = User.objects.get(username="otpuser1")
        # Verify first so login-after-reset would be possible too.
        self.client.post(
            VERIFY_URL, {"code": self._latest_code(user)}, format="json"
        )

        mail.outbox = []
        response = self.client.post(
            FORGOT_PASSWORD_URL, {"email": user.email}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        reset_body = mail.outbox[-1].body
        match = re.search(r"token=([^\s&]+)", reset_body)
        self.assertIsNotNone(
            match, "password reset email did not contain a token link"
        )
        token = match.group(1)

        reset_response = self.client.post(
            RESET_PASSWORD_URL,
            {
                "token": token,
                "new_password": "Br4ndNewPassw0rd!",
                "confirm_password": "Br4ndNewPassw0rd!",
            },
            format="json",
        )
        self.assertEqual(
            reset_response.status_code, status.HTTP_204_NO_CONTENT
        )

        user.refresh_from_db()
        self.assertTrue(user.check_password("Br4ndNewPassw0rd!"))
