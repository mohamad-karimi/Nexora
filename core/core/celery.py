"""Celery application for the Nexora project.

Web, worker and beat are separate processes that share only this
configuration:

    web     ->  gunicorn / runserver      (enqueues tasks, never sends mail)
    worker  ->  celery -A core worker     (consumes tasks, talks to SMTP/DB)
    beat    ->  celery -A core beat       (a clock: at the times in
                                           CELERY_BEAT_SCHEDULE it puts a
                                           task on the queue; runs nothing)

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

# Finds `tasks.py` in every app listed in INSTALLED_APPS (accounts.tasks:
# the account emails) ...
app.autodiscover_tasks()
# ... and `maintenance.py` (accounts.maintenance: the scheduled cleanups
# that Celery Beat dispatches, see CELERY_BEAT_SCHEDULE in settings).
app.autodiscover_tasks(related_name="maintenance")
