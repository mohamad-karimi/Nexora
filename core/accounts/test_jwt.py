"""
Tests for JWT authentication (POST /api/v1/auth/token/, .../refresh/,
.../verify/), added alongside the existing session authentication.

These only exercise the new JWT surface; the existing session-based
auth/login/ tests continue to live in accounts/tests.py and are
untouched by this change (see RegisterAPITests etc. there, and
test_session_login_still_works below for a direct regression check).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.constants import LOGIN_SECURITY_CODE_SESSION_KEY
from orders.models import Address

User = get_user_model()


class JWTTokenObtainTests(TestCase):
    """POST /api/v1/auth/token/"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/auth/token/"
        self.password = "S3cure!Passw0rd"
        self.verified_user = User.objects.create_user(
            username="jwtuser",
            email="jwtuser@example.com",
            password=self.password,
            is_verified=True,
        )
        self.unverified_user = User.objects.create_user(
            username="jwtunverified",
            email="jwtunverified@example.com",
            password=self.password,
            is_verified=False,
        )

    def test_valid_credentials_return_access_and_refresh_tokens(self):
        response = self.client.post(
            self.url,
            {"username": "jwtuser", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            self.url,
            {"username": "jwtuser", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)

    def test_unverified_user_is_rejected(self):
        response = self.client.post(
            self.url,
            {"username": "jwtunverified", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)

    def test_inactive_user_is_rejected(self):
        self.verified_user.is_active = False
        self.verified_user.save(update_fields=["is_active"])
        response = self.client.post(
            self.url,
            {"username": "jwtuser", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_token_does_not_contain_password_or_email(self):
        response = self.client.post(
            self.url,
            {"username": "jwtuser", "password": self.password},
            format="json",
        )
        access = AccessToken(response.data["access"])
        self.assertNotIn("password", access.payload)
        self.assertNotIn("email", access.payload)
        self.assertEqual(access.payload["user_id"], self.verified_user.pk)


class JWTProtectedAccessTests(TestCase):
    """Access Token behaviour on a JWT-protected endpoint (auth/me/)."""

    def setUp(self):
        self.client = APIClient()
        self.me_url = "/api/v1/auth/me/"
        self.password = "S3cure!Passw0rd"
        self.user = User.objects.create_user(
            username="jwtme",
            email="jwtme@example.com",
            password=self.password,
            is_verified=True,
        )

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_valid_access_token_grants_access(self):
        token = AccessToken.for_user(self.user)
        self._auth(str(token))
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "jwtme")

    def test_invalid_access_token_is_rejected(self):
        self._auth("this-is-not-a-real-token")
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_access_token_is_rejected(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))
        self._auth(str(token))
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_credentials_is_rejected(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class JWTTokenRefreshTests(TestCase):
    """POST /api/v1/auth/token/refresh/"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/auth/token/refresh/"
        self.user = User.objects.create_user(
            username="jwtrefresh",
            email="jwtrefresh@example.com",
            password="S3cure!Passw0rd",
            is_verified=True,
        )

    def test_valid_refresh_token_returns_new_access_token(self):
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(self.url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        # The refreshed access token must still resolve to the same user.
        new_access = AccessToken(response.data["access"])
        self.assertEqual(new_access.payload["user_id"], self.user.pk)

    def test_invalid_refresh_token_is_rejected(self):
        response = self.client.post(
            self.url, {"refresh": "not-a-real-refresh-token"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_refresh_token_is_rejected(self):
        refresh = RefreshToken.for_user(self.user)
        refresh.set_exp(lifetime=timedelta(seconds=-1))
        response = self.client.post(self.url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class JWTTokenVerifyTests(TestCase):
    """POST /api/v1/auth/token/verify/"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/auth/token/verify/"
        self.user = User.objects.create_user(
            username="jwtverify",
            email="jwtverify@example.com",
            password="S3cure!Passw0rd",
            is_verified=True,
        )

    def test_valid_token_verifies_successfully(self):
        token = AccessToken.for_user(self.user)
        response = self.client.post(self.url, {"token": str(token)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_token_fails_verification(self):
        response = self.client.post(self.url, {"token": "garbage-token"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_fails_verification(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))
        response = self.client.post(self.url, {"token": str(token)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class JWTRolePermissionTests(TestCase):
    """
    JWT identity must flow through to the project's real, DB-backed
    role/ownership permissions (IsVendor, IsOwner-style querysets) --
    a JWT must never grant access it wouldn't grant under session auth.
    """

    def setUp(self):
        self.client = APIClient()
        self.password = "S3cure!Passw0rd"
        self.customer = User.objects.create_user(
            username="jwtcustomer",
            email="jwtcustomer@example.com",
            password=self.password,
            is_verified=True,
            role=User.Role.CUSTOMER,
        )
        self.vendor = User.objects.create_user(
            username="jwtvendor",
            email="jwtvendor@example.com",
            password=self.password,
            is_verified=True,
            role=User.Role.VENDOR,
        )
        self.other_customer = User.objects.create_user(
            username="jwtothercustomer",
            email="jwtothercustomer@example.com",
            password=self.password,
            is_verified=True,
            role=User.Role.CUSTOMER,
        )

    def _auth_as(self, user):
        token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_customer_can_access_own_protected_endpoint(self):
        self._auth_as(self.customer)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], User.Role.CUSTOMER)

    def test_vendor_can_access_vendor_dashboard(self):
        self._auth_as(self.vendor)
        response = self.client.get("/api/v1/vendors/dashboard/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_customer_cannot_access_vendor_dashboard(self):
        self._auth_as(self.customer)
        response = self.client.get("/api/v1/vendors/dashboard/products/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_see_another_users_address_via_jwt(self):
        address = Address.objects.create(
            user=self.other_customer,
            full_name="Other Customer",
            phone="0000000000",
            country="Iran",
            city="Tehran",
            postal_code="12345",
            address_line1="Some street",
        )
        self._auth_as(self.customer)
        response = self.client.get(f"/api/v1/addresses/{address.pk}/")
        # Scoped out of the requester's own queryset -> not found, not
        # merely forbidden, so its existence isn't even confirmed.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_see_own_address_via_jwt(self):
        address = Address.objects.create(
            user=self.customer,
            full_name="JWT Customer",
            phone="0000000000",
            country="Iran",
            city="Tehran",
            postal_code="12345",
            address_line1="Some street",
        )
        self._auth_as(self.customer)
        response = self.client.get(f"/api/v1/addresses/{address.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SessionLoginStillWorksTests(TestCase):
    """
    Regression check: adding JWT must not touch or break the existing
    session-based login flow used by page-login.html.
    """

    def setUp(self):
        self.client = APIClient()
        self.login_url = "/api/v1/auth/login/"
        self.page_url = reverse("accounts:login")
        self.password = "S3cure!Passw0rd"
        self.user = User.objects.create_user(
            username="sessionuser",
            email="sessionuser@example.com",
            password=self.password,
            is_verified=True,
        )

    def _get_security_code(self):
        self.client.get(self.page_url)
        return self.client.session[LOGIN_SECURITY_CODE_SESSION_KEY]

    def test_session_login_still_works(self):
        code = self._get_security_code()
        response = self.client.post(
            self.login_url,
            {
                "username": "sessionuser",
                "password": self.password,
                "security_code": code,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # The resulting session (cookie), not a JWT, is what authenticates
        # the very next request -- no Authorization header is sent.
        me_response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["username"], "sessionuser")
