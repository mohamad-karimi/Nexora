from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from website.models import ContactMessage, HomeBanner, HomeSlide

User = get_user_model()


class HomeSlideAPITests(APITestCase):
    """Tests for GET /api/v1/home-slides/, consumed by the homepage
    hero slider (static/js/pages/home.js -> loadHeroSlider)."""

    def setUp(self):
        self.url = reverse("api:api_v1:home-slide-list")

    def test_only_active_slides_are_returned_in_order(self):
        # The 0004 data migration seeds 2 default slides matching the
        # site's original static markup, so this table is never truly
        # empty -- assert on relative order/exclusion, not the full list.
        HomeSlide.objects.create(
            title="Second\nSlide", image="sliders/second.png", ordering=101
        )
        HomeSlide.objects.create(
            title="First\nSlide", image="sliders/first.png", ordering=100
        )
        HomeSlide.objects.create(
            title="Hidden\nSlide",
            image="sliders/hidden.png",
            ordering=102,
            is_active=False,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data]
        self.assertNotIn("Hidden\nSlide", titles)
        self.assertLess(titles.index("First\nSlide"), titles.index("Second\nSlide"))

    def test_slide_exposes_title_description_and_image(self):
        HomeSlide.objects.create(
            title="Don\u2019t miss amazing\ngrocery deals",
            description="Sign up for the daily newsletter",
            image="sliders/slider-1.png",
        )

        response = self.client.get(self.url)

        item = response.data[0]
        self.assertEqual(item["title"], "Don\u2019t miss amazing\ngrocery deals")
        self.assertEqual(item["description"], "Sign up for the daily newsletter")
        self.assertIn("slider-1.png", item["image"])


class HomeBannerAPITests(APITestCase):
    """Tests for GET /api/v1/home-banners/, consumed by the homepage
    banners section (static/js/pages/home.js -> loadBanners)."""

    def setUp(self):
        self.url = reverse("api:api_v1:home-banner-list")

    def test_only_active_banners_are_returned_in_order(self):
        # Same as slides above -- 0004 seeds 3 default banners, so
        # assert on relative order/exclusion, not the full list.
        HomeBanner.objects.create(
            title="Second\nBanner", image="banners/second.png", ordering=101
        )
        HomeBanner.objects.create(
            title="First\nBanner", image="banners/first.png", ordering=100
        )
        HomeBanner.objects.create(
            title="Hidden\nBanner",
            image="banners/hidden.png",
            ordering=102,
            is_active=False,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data]
        self.assertNotIn("Hidden\nBanner", titles)
        self.assertLess(titles.index("First\nBanner"), titles.index("Second\nBanner"))

    def test_banner_link_url_is_optional(self):
        HomeBanner.objects.create(title="No link", image="banners/x.png")
        HomeBanner.objects.create(
            title="With link",
            image="banners/y.png",
            link_url="/shop/filter/?category=fruit",
        )

        response = self.client.get(self.url)

        by_title = {item["title"]: item["link_url"] for item in response.data}
        self.assertEqual(by_title["No link"], "")
        self.assertEqual(by_title["With link"], "/shop/filter/?category=fruit")


class ContactMessageAPITests(APITestCase):
    """Tests for POST /api/v1/contact/ (the "Drop Us a Line" form)."""

    def setUp(self):
        self.url = reverse("api:api_v1:contact-message")
        self.payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "123456789",
            "subject": "Question about an order",
            "message": "Hello, I have a question about my order.",
        }

    def test_anonymous_user_can_submit_contact_message(self):
        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ContactMessage.objects.count(), 1)
        message = ContactMessage.objects.first()
        self.assertIsNone(message.user)
        self.assertEqual(message.name, self.payload["name"])
        self.assertEqual(message.email, self.payload["email"])

    def test_authenticated_user_submission_is_linked_to_their_account(self):
        user = User.objects.create_user(
            username="jane",
            email="jane@example.com",
            password="StrongPass123!",
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message = ContactMessage.objects.get()
        self.assertEqual(message.user, user)

    def test_missing_required_fields_returns_400(self):
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
        self.assertIn("email", response.data)
        self.assertIn("message", response.data)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_invalid_email_returns_400(self):
        payload = dict(self.payload, email="not-an-email")

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_phone_and_subject_are_optional(self):
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "message": "Hello, just a quick question.",
        }

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
