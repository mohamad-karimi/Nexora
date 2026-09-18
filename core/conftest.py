"""Pytest bootstrap for the Django suite.

Environment variables that `core.settings` requires via python-decouple
must be present *before* Django is imported. Locmem email is required so
existing OTP/reset tests can assert against `django.core.mail.outbox`.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("EMAIL_HOST_USER", "test@example.com")
os.environ.setdefault("EMAIL_HOST_PASSWORD", "test-password")
os.environ.setdefault("DEBUG", "True")

import pytest


@pytest.fixture(autouse=True)
def _locmem_email(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
