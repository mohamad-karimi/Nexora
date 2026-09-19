"""Pytest bootstrap for the Django suite.

Environment variables that `core.settings` requires via python-decouple
must be present *before* Django is imported. Locmem email is required so
existing OTP/reset tests can assert against `django.core.mail.outbox`.

Celery runs in eager mode for the suite (see `_celery_eager`):
`.delay()` / `.apply_async()` execute the task inline, so tests see the
outgoing mail exactly as before without needing Redis or a worker. Tests
that care about the *queueing* itself patch `apply_async` (see
accounts/test_email_tasks.py).
"""

import os

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("EMAIL_HOST_USER", "test@example.com")
os.environ.setdefault("EMAIL_HOST_PASSWORD", "test-password")
os.environ.setdefault("DEBUG", "True")


@pytest.fixture(autouse=True)
def _locmem_email(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    # Celery reads its CELERY_* keys live from Django settings, so this
    # fixture (unlike an environment variable, which would be read too
    # late here) can be flipped per test.
    settings.CELERY_TASK_ALWAYS_EAGER = True


class FakeRedis:
    """Just enough of redis-py for the email tasks' "already sent" markers,
    so the suite never touches a real Redis."""

    def __init__(self):
        self.store = {}

    def exists(self, key):
        return int(key in self.store)

    def set(self, key, value, ex=None):
        self.store[key] = value
        return True


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("accounts.tasks.get_redis_client", lambda: fake)
    return fake
