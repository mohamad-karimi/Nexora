import tempfile
from copy import copy
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlsplit

from celery.beat import PersistentScheduler, Scheduler
from celery.schedules import crontab
from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import SimpleTestCase, TestCase
from django.utils import timezone as dj_timezone

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


EXPECTED_SCHEDULE = {
    "cleanup-expired-otp-codes": "accounts.cleanup_expired_otp_codes",
    "cleanup-expired-sessions": "accounts.cleanup_expired_sessions",
    "cleanup-expired-jwt-tokens": "accounts.cleanup_expired_jwt_tokens",
}


class BeatScheduleTests(SimpleTestCase):
    """The CELERY_BEAT_SCHEDULE that the `beat` process loads."""

    def setUp(self):
        app.loader.import_default_modules()
        self.schedule = app.conf.beat_schedule

    def test_only_the_intended_jobs_are_scheduled(self):
        # Guards against schedules being added "just because": every new
        # entry has to be a deliberate change to this test too.
        self.assertEqual(
            {name: e["task"] for name, e in self.schedule.items()},
            EXPECTED_SCHEDULE,
        )

    def test_every_scheduled_task_is_registered_with_the_worker(self):
        for entry in self.schedule.values():
            self.assertIn(entry["task"], app.tasks)

    def test_beat_adds_no_schedules_of_its_own(self):
        # What the beat process really loads (its default scheduler, backed
        # by a schedule file): our entries plus anything Celery injects by
        # default, e.g. a daily "celery.backend_cleanup".
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = PersistentScheduler(
                app=app, schedule_filename=f"{tmp}/celerybeat-schedule"
            )
            try:
                loaded = set(scheduler.schedule)
            finally:
                scheduler.close()
        self.assertEqual(loaded, set(EXPECTED_SCHEDULE))

    def test_the_email_tasks_are_not_scheduled(self):
        # They are triggered by user actions, never by the clock.
        scheduled = {e["task"] for e in self.schedule.values()}
        self.assertFalse({t for t in scheduled if "email" in t})

    def test_beat_uses_the_project_timezone(self):
        self.assertEqual(str(app.timezone), settings.TIME_ZONE)
        self.assertTrue(app.conf.enable_utc)

    def test_each_job_runs_once_a_day_off_peak_and_never_at_the_same_time(
        self,
    ):
        times = []
        for entry in self.schedule.values():
            cron = entry["schedule"]
            self.assertIsInstance(cron, crontab)
            self.assertEqual(len(cron.hour), 1)
            self.assertEqual(len(cron.minute), 1)
            self.assertEqual(len(cron.day_of_week), 7)  # every day
            (hour,), (minute,) = cron.hour, cron.minute
            self.assertIn(hour, (2, 3, 4))
            times.append((hour, minute))
        self.assertEqual(len(set(times)), len(times))

    def test_a_dispatched_run_expires_instead_of_piling_up(self):
        for entry in self.schedule.values():
            expires = entry["options"]["expires"]
            self.assertGreater(expires, 0)
            self.assertLessEqual(expires, 24 * 60 * 60)

    def test_crontab_fires_at_the_scheduled_time_in_the_project_timezone(self):
        cron = copy(self.schedule["cleanup-expired-otp-codes"]["schedule"])
        tz = timezone.utc  # TIME_ZONE is UTC
        self.assertEqual(settings.TIME_ZONE, "UTC")

        def due_at(now, last_run):
            cron.nowfun = lambda: now
            return cron.is_due(last_run).is_due

        before = datetime(2026, 9, 19, 3, 14, 30, tzinfo=tz)
        at = datetime(2026, 9, 19, 3, 15, 5, tzinfo=tz)
        self.assertFalse(due_at(before, before - timedelta(minutes=1)))
        self.assertTrue(due_at(at, before))
        # Once it has run, it is not due again until the next day.
        self.assertFalse(due_at(at + timedelta(hours=5), at))


class BeatDispatchTests(TestCase):
    def test_a_due_entry_is_dispatched_to_its_task_and_runs(self):
        """What beat does at 03:30: hand the entry to Celery, which (eager
        here, a worker in production) runs the task."""
        Session.objects.create(
            session_key="expired",
            session_data="x",
            expire_date=dj_timezone.now() - timedelta(days=1),
        )
        Session.objects.create(
            session_key="live",
            session_data="x",
            expire_date=dj_timezone.now() + timedelta(days=1),
        )
        scheduler = Scheduler(app=app)
        entry = scheduler.schedule["cleanup-expired-sessions"]

        scheduler.apply_async(entry, advance=False)

        self.assertEqual(
            list(Session.objects.values_list("session_key", flat=True)),
            ["live"],
        )
