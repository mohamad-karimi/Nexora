from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    """Covers the /health/ endpoint used by CI, Docker healthchecks and
    the CD post-deploy check (see core.health.health)."""

    def test_health_endpoint_returns_200_and_ok_status(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_health_endpoint_reports_database_status(self):
        # A plain request against the real (migrated) test database
        # should always report the database as reachable.
        response = self.client.get(reverse("health"))

        self.assertEqual(response.json()["database"], "ok")
