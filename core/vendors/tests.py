from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from vendors.models import Vendor
from website.models import ContactMessage

User = get_user_model()


def make_user(username, role=User.Role.CUSTOMER, **profile_fields):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        role=role,
        is_verified=True,
    )
    if profile_fields:
        # A profile row is created by a signal on user creation, so fill
        # the existing one instead of inserting a second.
        profile = user.profile
        for field, value in profile_fields.items():
            setattr(profile, field, value)
        profile.save()
    return user


class VendorGuidePageAccessTests(TestCase):
    """The page itself is gated in the view, not in the template."""

    def setUp(self):
        self.url = reverse("vendors:guide")

    def test_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_authenticated_non_vendor_gets_403(self):
        self.client.force_login(make_user("carol"))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_vendor_can_open_the_page(self):
        self.client.force_login(make_user("vera", role=User.Role.VENDOR))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "vendors/vendor-guide.html")
        # The form posts to the vendor-only endpoint, not the public one.
        self.assertContains(response, 'data-contact-endpoint="contact/vendor-guide/"')


class VendorGuideContactAPITests(APITestCase):
    """POST /api/v1/contact/vendor-guide/"""

    def setUp(self):
        self.url = reverse("api:api_v1:contact-message-vendor-guide")
        self.payload = {
            "name": "Vera",
            "email": "vera@example.com",
            "phone": "123456789",
            "subject": "Store question",
            "message": "How do I add a product?",
        }

    def test_anonymous_submission_is_rejected(self):
        response = self.client.post(self.url, self.payload)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_non_vendor_submission_is_rejected(self):
        self.client.force_authenticate(user=make_user("carol"))
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_vendor_submission_is_stored_with_user_vendor_and_source(self):
        user = make_user("vera", role=User.Role.VENDOR)
        vendor = Vendor.objects.create(user=user, store_name="Vera Store")
        self.client.force_authenticate(user=user)

        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message = ContactMessage.objects.get()
        self.assertEqual(message.user, user)
        self.assertEqual(message.vendor, vendor)
        self.assertEqual(message.source, ContactMessage.Source.VENDOR_GUIDE)
        self.assertEqual(message.message, self.payload["message"])

    def test_vendor_without_store_row_still_submits(self):
        user = make_user("vera", role=User.Role.VENDOR)
        self.client.force_authenticate(user=user)

        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message = ContactMessage.objects.get()
        self.assertEqual(message.user, user)
        self.assertIsNone(message.vendor)
        self.assertEqual(message.source, ContactMessage.Source.VENDOR_GUIDE)

    def test_source_cannot_be_forged_from_the_request_body(self):
        user = make_user("vera", role=User.Role.VENDOR)
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url, dict(self.payload, source="contact", user=999)
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message = ContactMessage.objects.get()
        self.assertEqual(message.source, ContactMessage.Source.VENDOR_GUIDE)
        self.assertEqual(message.user, user)

    def test_validation_errors_are_returned_per_field(self):
        self.client.force_authenticate(user=make_user("vera", role=User.Role.VENDOR))

        response = self.client.post(self.url, {"email": "not-an-email"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
        self.assertIn("email", response.data)
        self.assertIn("message", response.data)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_public_contact_endpoint_still_records_source_contact(self):
        response = self.client.post(
            reverse("api:api_v1:contact-message"), self.payload
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message = ContactMessage.objects.get()
        self.assertEqual(message.source, ContactMessage.Source.CONTACT_PAGE)
        self.assertIsNone(message.vendor)


class VendorGuidePrefillDataTests(APITestCase):
    """
    The form is prefilled client-side from /api/v1/auth/me/, so what
    matters server-side is that the endpoint exposes first_name / email /
    phone - and that it does not break when the profile is empty.
    """

    def test_me_exposes_prefill_fields_for_a_vendor(self):
        user = make_user(
            "vera",
            role=User.Role.VENDOR,
            first_name="Vera",
            last_name="Smith",
            display_name="Vera",
            phone="09120000000",
            address="",
            description="",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("api:api_v1:auth-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], user.email)
        self.assertEqual(response.data["profile"]["first_name"], "Vera")
        self.assertEqual(response.data["profile"]["phone"], "09120000000")

    def test_me_with_an_empty_profile_does_not_error(self):
        user = make_user("vera", role=User.Role.VENDOR)
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("api:api_v1:auth-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile = response.data.get("profile") or {}
        # Empty, not missing -> the form leaves the field blank instead of
        # erroring.
        self.assertEqual(profile.get("first_name", ""), "")
        self.assertEqual(profile.get("phone", ""), "")
