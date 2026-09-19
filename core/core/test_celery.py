from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.test import SimpleTestCase

import core
from core.celery import app


class CeleryConfigurationTests(SimpleTestCase):
    """Covers core.celery + the CELERY_* settings. No broker is needed."""

    def test_app_is_loaded_with_django(self):
        self.assertIs(core.celery_app, app)

    def test_email_tasks_are_registered_under_stable_names(self):
        app.loader.import_default_modules()
        self.assertIn("accounts.send_verification_email", app.tasks)
        self.assertIn("accounts.send_password_reset_email", app.tasks)

    def test_broker_is_the_projects_redis(self):
        url = urlsplit(app.conf.broker_url)
        expected_scheme = "rediss" if settings.REDIS_SSL else "redis"
        self.assertEqual(url.scheme, expected_scheme)
        self.assertEqual(url.hostname, settings.REDIS_HOST)
        self.assertEqual(url.port, settings.REDIS_PORT)
        self.assertEqual(url.path, f"/{settings.REDIS_BROKER_DB}")
        self.assertEqual(
            unquote(url.password or ""), settings.REDIS_PASSWORD
        )

    def test_only_json_is_accepted_and_no_result_is_kept(self):
        self.assertEqual(app.conf.task_serializer, "json")
        self.assertEqual(list(app.conf.accept_content), ["json"])
        self.assertTrue(app.conf.task_ignore_result)
        # No backend means a task result (and anything sensitive in it)
        # can never be stored, whatever a task returns.
        self.assertIsNone(app.conf.result_backend)

    def test_tasks_are_acknowledged_late_so_a_dead_worker_is_recovered(self):
        self.assertTrue(app.conf.task_acks_late)
        self.assertTrue(app.conf.task_reject_on_worker_lost)
        self.assertEqual(app.conf.worker_prefetch_multiplier, 1)

    def test_publishing_never_hangs_a_request(self):
        policy = app.conf.task_publish_retry_policy
        self.assertTrue(app.conf.task_publish_retry)
        self.assertLessEqual(policy["max_retries"], 3)
        self.assertLessEqual(policy["interval_max"], 1)
        self.assertLessEqual(app.conf.broker_connection_timeout, 5)

    def test_smtp_has_a_timeout(self):
        # Django's default is "wait forever", which would pin a worker slot.
        self.assertIsNotNone(settings.EMAIL_TIMEOUT)
        self.assertGreater(settings.EMAIL_TIMEOUT, 0)
