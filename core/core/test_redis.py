from unittest import mock

import redis
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core import redis_client
from core.redis_client import RedisStatus, check_redis


class RedisClientTests(SimpleTestCase):
    """Covers core.redis_client. No real Redis is needed: the redis-py
    client is mocked, so this runs in the plain backend CI job."""

    def setUp(self):
        redis_client._build_client.cache_clear()
        self.addCleanup(redis_client._build_client.cache_clear)

    @override_settings(
        REDIS_HOST="redis-host",
        REDIS_PORT=6380,
        REDIS_DB=2,
        REDIS_PASSWORD="from-settings",
        REDIS_SSL=True,
        REDIS_SOCKET_CONNECT_TIMEOUT=1.5,
        REDIS_SOCKET_TIMEOUT=2.5,
    )
    def test_client_is_built_from_settings(self):
        with mock.patch("core.redis_client.redis.Redis") as redis_cls:
            client = redis_client.get_redis_client()

        redis_cls.assert_called_once_with(
            host="redis-host",
            port=6380,
            db=2,
            password="from-settings",
            ssl=True,
            socket_connect_timeout=1.5,
            socket_timeout=2.5,
            decode_responses=True,
        )
        self.assertIs(client, redis_cls.return_value)

    @override_settings(REDIS_PASSWORD="")
    def test_empty_password_means_no_authentication(self):
        with mock.patch("core.redis_client.redis.Redis") as redis_cls:
            redis_client.get_redis_client()

        self.assertIsNone(redis_cls.call_args.kwargs["password"])

    def test_client_is_shared_between_calls(self):
        with mock.patch("core.redis_client.redis.Redis") as redis_cls:
            first = redis_client.get_redis_client()
            second = redis_client.get_redis_client()

        self.assertIs(first, second)
        redis_cls.assert_called_once()

    def test_check_redis_reports_ok_when_ping_succeeds(self):
        client = mock.Mock()
        client.ping.return_value = True
        with mock.patch(
            "core.redis_client.get_redis_client", return_value=client
        ):
            status = check_redis()

        self.assertEqual(status, RedisStatus(True, "ok"))

    def test_check_redis_reports_failures_and_logs_them(self):
        failures = [
            (redis.exceptions.ConnectionError("refused"), "refused"),
            (
                redis.exceptions.AuthenticationError("bad password"),
                "authentication failed",
            ),
            (redis.exceptions.TimeoutError("slow"), "timed out"),
            (redis.exceptions.RedisError("boom"), "boom"),
        ]
        for exc, expected in failures:
            with self.subTest(exc=type(exc).__name__):
                client = mock.Mock()
                client.ping.side_effect = exc
                with mock.patch(
                    "core.redis_client.get_redis_client",
                    return_value=client,
                ):
                    with self.assertLogs(
                        "core.redis_client", level="ERROR"
                    ) as logs:
                        status = check_redis()

                self.assertFalse(status.ok)
                self.assertIn(expected, status.detail)
                self.assertIn("Redis check failed", logs.output[0])

    @override_settings(REDIS_PASSWORD="super-secret-value")
    def test_password_is_never_logged_or_returned(self):
        client = mock.Mock()
        client.ping.side_effect = redis.exceptions.ConnectionError("refused")
        with mock.patch(
            "core.redis_client.get_redis_client", return_value=client
        ):
            with self.assertLogs("core.redis_client", level="ERROR") as logs:
                status = check_redis()

        self.assertNotIn("super-secret-value", status.detail)
        self.assertNotIn("super-secret-value", "".join(logs.output))


class RedisHealthEndpointTests(TestCase):
    """Covers /health/redis/ (core.health.redis_health)."""

    def test_returns_200_when_redis_is_reachable(self):
        with mock.patch(
            "core.health.check_redis", return_value=RedisStatus(True, "ok")
        ):
            response = self.client.get(reverse("health-redis"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "redis": "ok"})

    def test_returns_503_without_leaking_details_when_unreachable(self):
        with mock.patch(
            "core.health.check_redis",
            return_value=RedisStatus(False, "connection failed: internal"),
        ):
            response = self.client.get(reverse("health-redis"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(), {"status": "error", "redis": "error"}
        )
        self.assertNotIn(b"internal", response.content)

    def test_main_health_endpoint_is_unaffected_by_redis(self):
        # Redis is not a dependency of the app yet, so /health/ (used by
        # the Docker healthcheck and CD) must stay green without it.
        with mock.patch(
            "core.health.check_redis",
            return_value=RedisStatus(False, "down"),
        ):
            response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
