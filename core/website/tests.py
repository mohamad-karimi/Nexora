from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from website.models import ContactMessage

User = get_user_model()


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
            username="jane", email="jane@example.com", password="StrongPass123!"
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
