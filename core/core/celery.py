"""Celery application for the Nexora project.

Web and worker are separate processes that share only this configuration:

    web     ->  gunicorn / runserver      (enqueues tasks, never sends mail)
    worker  ->  celery -A core worker     (consumes tasks, talks to SMTP)

The broker is the project's existing Redis (see core.redis_client and the
CELERY_* block in core/settings.py). No result backend is configured on
purpose: tasks return nothing, so nothing sensitive can end up stored as
a task result.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")

# Read every CELERY_* setting from Django settings (namespace="CELERY"),
# e.g. CELERY_BROKER_URL -> broker_url.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Finds `tasks.py` in every app listed in INSTALLED_APPS (accounts.tasks).
app.autodiscover_tasks()
