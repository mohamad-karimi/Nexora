from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from django.test import TestCase

from accounts.constants import (
    LOGIN_SECURITY_CODE_SESSION_KEY,
    SECURITY_CODE_SESSION_KEY,
)

User = get_user_model()


def make_user(username, **kwargs):
    defaults = {
        "email": f"{username}@example.com",
        "password": "StrongPass123!",
        "is_verified": True,
        "role": User.Role.CUSTOMER,
    }
    defaults.update(kwargs)
    password = defaults.pop("password")
    return User.objects.create_user(username=username, password=password, **defaults)


class ChangePasswordAPITests(APITestCase):
    def setUp(self):
        self.user = make_user("pwuser", password="OldPassw0rd!")
        self.url = reverse("api:api_v1:auth-change-password")
        self.client.force_authenticate(user=self.user)

    def test_change_password_succeeds_with_correct_old_password(self):
        response = self.client.post(
            self.url,
            {
                "old_password": "OldPassw0rd!",
                "new_password": "BrandNewPassw0rd!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertNotIn("password", response.data or {})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPassw0rd!"))

    def test_wrong_old_password_is_rejected(self):
        response = self.client.post(
            self.url,
            {"old_password": "nope", "new_password": "BrandNewPassw0rd!"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassw0rd!"))

    def test_weak_new_password_is_rejected(self):
        response = self.client.post(
            self.url, {"old_password": "OldPassw0rd!", "new_password": "123"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_cannot_change_password(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            self.url,
            {
                "old_password": "OldPassw0rd!",
                "new_password": "BrandNewPassw0rd!",
            },
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class LogoutAndMeSecurityTests(APITestCase):
    def setUp(self):
        self.user = make_user("meuser")
        self.client.force_authenticate(user=self.user)

    def test_me_does_not_expose_password(self):
        response = self.client.get(reverse("api:api_v1:auth-me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", response.data)
        self.assertEqual(response.data["username"], "meuser")
        self.assertEqual(response.data["role"], User.Role.CUSTOMER)

    def test_patch_me_cannot_change_username_or_role(self):
        response = self.client.patch(
            reverse("api:api_v1:auth-me"),
            {
                "username": "hacker",
                "role": User.Role.ADMIN,
                "first_name": "Ada",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "meuser")
        self.assertEqual(self.user.role, User.Role.CUSTOMER)
        self.assertEqual(self.user.profile.first_name, "Ada")

    def test_logout_ends_the_session(self):
        client = APIClient()
        user = make_user("logoutuser")
        client.force_login(user)
        self.assertEqual(
            client.get(reverse("api:api_v1:auth-me")).status_code,
            status.HTTP_200_OK,
        )

        response = client.post(reverse("api:api_v1:auth-logout"))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        me = client.get(reverse("api:api_v1:auth-me"))
        self.assertIn(
            me.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_unverified_user_cannot_access_me_even_if_a_session_exists(self):
        unverified = make_user("unvme", is_verified=False)
        self.client.force_authenticate(user=unverified)
        response = self.client.get(reverse("api:api_v1:auth-me"))
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class LoginSecurityCodeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("loginsec")
        self.login_url = "/api/v1/auth/login/"
        self.page_url = reverse("accounts:login")

    def _code(self):
        self.client.get(self.page_url)
        return self.client.session[LOGIN_SECURITY_CODE_SESSION_KEY]

    def test_wrong_security_code_is_rejected(self):
        real = self._code()
        wrong = "0000" if real != "0000" else "1111"
        response = self.client.post(
            self.login_url,
            {
                "username": "loginsec",
                "password": "StrongPass123!",
                "security_code": wrong,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_verified_user_can_login_with_correct_security_code(self):
        code = self._code()
        response = self.client.post(
            self.login_url,
            {
                "username": "loginsec",
                "password": "StrongPass123!",
                "security_code": code,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", response.data)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_unverified_user_is_rejected_after_passing_security_code(self):
        unverified = make_user("unvlogin", is_verified=False)
        code = self._code()
        response = self.client.post(
            self.login_url,
            {
                "username": unverified.username,
                "password": "StrongPass123!",
                "security_code": code,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("verify", response.data["detail"].lower())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        code = self._code()
        response = self.client.post(
            self.login_url,
            {
                "username": "loginsec",
                "password": "StrongPass123!",
                "security_code": code,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RegisterValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/auth/register/"

    def _payload(self, **overrides):
        self.client.get(reverse("accounts:register"))
        payload = {
            "username": "newacct",
            "email": "newacct@example.com",
            "password": "S3cure!Passw0rd",
            "security_code": self.client.session[SECURITY_CODE_SESSION_KEY],
            "agree_terms": True,
            "account_type": "customer",
        }
        payload.update(overrides)
        return payload

    def test_duplicate_username_is_rejected(self):
        make_user("newacct")
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.filter(username="newacct").count(), 1)

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            self.url, self._payload(password="123"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="newacct").exists())


class ForgotPasswordEnumerationTests(APITestCase):
    def setUp(self):
        self.url = reverse("api:api_v1:auth-forgot-password")
        self.user = make_user("forgotuser")

    def test_unknown_email_returns_the_same_success_response(self):
        known = self.client.post(self.url, {"email": self.user.email})
        unknown = self.client.post(self.url, {"email": "missing@example.com"})
        self.assertEqual(known.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown.status_code, status.HTTP_200_OK)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_token_cannot_target_another_user(self):
        victim = make_user("victim")
        self.client.post(self.url, {"email": self.user.email})
        import re

        token = re.search(r"token=([^\s&]+)", mail.outbox[-1].body).group(1)
        response = self.client.post(
            reverse("api:api_v1:auth-reset-password"),
            {
                "token": token,
                "new_password": "N3wSecurePass!",
                "confirm_password": "N3wSecurePass!",
                "user_id": victim.pk,
                "email": victim.email,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        victim.refresh_from_db()
        self.assertTrue(self.user.check_password("N3wSecurePass!"))
        self.assertTrue(victim.check_password("StrongPass123!"))
