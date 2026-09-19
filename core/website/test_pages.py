from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import TestCase

from website.models import ContactMessage, HomeBanner, HomeSlide

User = get_user_model()


class PublicPageSmokeTests(TestCase):
    def test_terms_and_privacy_pages_render(self):
        terms = self.client.get(reverse("website:terms"))
        privacy = self.client.get(reverse("website:privacy_policy"))
        self.assertEqual(terms.status_code, 200)
        self.assertEqual(privacy.status_code, 200)
        self.assertTemplateUsed(terms, "website/page-terms.html")
        self.assertTemplateUsed(privacy, "website/page-privacy-policy.html")


class InactiveHomeContentTests(APITestCase):
    def test_inactive_slide_and_banner_are_not_retrievable(self):
        slide = HomeSlide.objects.create(
            title="Hidden Slide",
            image="sliders/hidden-test.png",
            is_active=False,
        )
        banner = HomeBanner.objects.create(
            title="Hidden Banner",
            image="banners/hidden-test.png",
            is_active=False,
        )
        slide_response = self.client.get(
            reverse("api:api_v1:home-slide-detail", kwargs={"pk": slide.pk})
        )
        banner_response = self.client.get(
            reverse("api:api_v1:home-banner-detail", kwargs={"pk": banner.pk})
        )
        self.assertEqual(
            slide_response.status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(
            banner_response.status_code, status.HTTP_404_NOT_FOUND
        )


class PublicContactSourceForgeTests(APITestCase):
    def setUp(self):
        self.url = reverse("api:api_v1:contact-message")
        self.payload = {
            "name": "Jane",
            "email": "jane@example.com",
            "message": "Hello there",
            "source": ContactMessage.Source.VENDOR_GUIDE,
            "user": 999,
        }

    def test_public_contact_cannot_forge_source_or_user(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message = ContactMessage.objects.get()
        self.assertEqual(message.source, ContactMessage.Source.CONTACT_PAGE)
        self.assertIsNone(message.user)

    def test_customer_cannot_submit_vendor_guide_contact(self):
        user = User.objects.create_user(
            username="custcontact",
            email="custcontact@example.com",
            password="StrongPass123!",
            is_verified=True,
        )
        self.client.force_authenticate(user=user)
        response = self.client.post(
            reverse("api:api_v1:contact-message-vendor-guide"),
            {
                "name": "Jane",
                "email": "jane@example.com",
                "message": "Please let me in",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ContactMessage.objects.count(), 0)
