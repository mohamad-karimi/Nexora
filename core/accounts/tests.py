from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.constants import SECURITY_CODE_SESSION_KEY

User = get_user_model()


class RegisterAPITests(TestCase):
    """
    Regression tests for the /api/v1/auth/register/ endpoint covering the
    page-register.html fixes:

    - the security code is validated for real (not cosmetic)
    - registration is rejected when Terms & Policy is not accepted
    - "I am a customer" / "I am a vendor" is actually persisted as the
      user's role
    - the raw password is never stored in profile.first_name or
      profile.display_name, first_name stays empty when not supplied, and
      display_name defaults to the username
    """

    def setUp(self):
        self.client = APIClient()
        self.register_url = "/api/v1/auth/register/"
        self.page_url = reverse("accounts:register")

    def _get_security_code(self):
        # Visiting the register page stores a freshly generated code in the
        # session, exactly like a real browser would before submitting.
        self.client.get(self.page_url)
        return self.client.session[SECURITY_CODE_SESSION_KEY]

    def _payload(self, security_code, **overrides):
        payload = {
            "username": "newuser1",
            "email": "newuser1@example.com",
            "password": "S3cure!Passw0rd",
            "security_code": security_code,
            "agree_terms": True,
            "account_type": "customer",
        }
        payload.update(overrides)
        return payload

    def test_wrong_security_code_is_rejected(self):
        real_code = self._get_security_code()
        wrong_code = "1111" if real_code != "1111" else "2222"
        response = self.client.post(
            self.register_url, self._payload(wrong_code), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="newuser1").exists())

    def test_missing_terms_agreement_is_rejected(self):
        code = self._get_security_code()
        response = self.client.post(
            self.register_url,
            self._payload(code, agree_terms=False),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="newuser1").exists())

    def test_vendor_account_type_is_persisted(self):
        code = self._get_security_code()
        response = self.client.post(
            self.register_url,
            self._payload(
                code,
                username="vendoruser",
                email="vendor@example.com",
                account_type="vendor",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="vendoruser")
        self.assertEqual(user.role, User.Role.VENDOR)
        # Regression: registering as a vendor must also create the
        # Vendor row (vendors.signals), or product creation later has
        # no vendor to attach to (see vendors/tests.py for the rest of
        # this invariant's coverage).
        self.assertTrue(hasattr(user, "vendor_profile"))
        self.assertEqual(user.vendor_profile.user_id, user.id)

    def test_customer_account_type_is_persisted(self):
        code = self._get_security_code()
        response = self.client.post(
            self.register_url,
            self._payload(
                code,
                username="customeruser",
                email="customer@example.com",
                account_type="customer",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="customeruser")
        self.assertEqual(user.role, User.Role.CUSTOMER)

    def test_password_is_never_stored_in_first_name_or_display_name(self):
        """
        Regression test for the critical bug report: registering must never
        leak the raw password into profile.first_name or profile.display_name,
        the password must never be echoed back in the API response, and it
        must never be stored in plaintext.
        """
        code = self._get_security_code()
        password = "Sup3rSecretPassw0rd!"
        # Intentionally omit first_name/last_name, exactly like the HTML form.
        response = self.client.post(
            self.register_url,
            self._payload(
                code,
                username="safeuser",
                email="safeuser@example.com",
                password=password,
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)

        user = User.objects.get(username="safeuser")
        profile = user.profile

        self.assertNotEqual(profile.first_name, password)
        self.assertNotEqual(profile.display_name, password)
        self.assertEqual(profile.first_name, "")
        # display_name must default to the username when none was supplied.
        self.assertEqual(profile.display_name, user.username)

        # The stored password must be a hash, never the plaintext value.
        self.assertNotEqual(user.password, password)
        self.assertTrue(user.check_password(password))

    def test_first_name_and_display_name_are_set_when_provided(self):
        code = self._get_security_code()
        response = self.client.post(
            self.register_url,
            self._payload(
                code,
                username="nameduser",
                email="named@example.com",
                first_name="Ali",
                last_name="Rezai",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="nameduser")
        self.assertEqual(user.profile.first_name, "Ali")
        self.assertEqual(user.profile.display_name, "Ali Rezai")
