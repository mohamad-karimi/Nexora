"""Gunicorn configuration for production (docker-compose.prod.yml).

Every tunable is read from the environment so nothing here is hardcoded
and the same image can be resized (more workers, different timeouts) by
changing `.env` on the server, not the image. Logs go to stdout/stderr so
`docker logs` / the Docker log driver captures them -- see
docker-compose.prod.yml `logging:` options for rotation.

Not used by local dev (docker-compose.yml runs `manage.py runserver`) or
by CI's docker-compose.yml validation job.
"""

import multiprocessing
import os

# Bind
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# Workers: default to (2 * CPU) + 1, the standard Gunicorn recommendation,
# overridable directly for a known deployment size.
workers = int(
    os.environ.get(
        "GUNICORN_WORKERS", str(multiprocessing.cpu_count() * 2 + 1)
    )
)
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "sync")
threads = int(os.environ.get("GUNICORN_THREADS", "1"))

# Timeouts. `graceful_timeout` gives an in-flight request this long to
# finish after a SIGTERM/reload before the worker is killed, so a
# `docker compose up -d` / rolling restart does not cut off requests
# mid-flight.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))

# Recycle workers periodically to bound the effect of any slow memory
# leak; jitter staggers restarts so all workers don't recycle at once.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(
    os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "100")
)

# Logging -- stdout/stderr, picked up by `docker logs`/the log driver.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = (
    '%(h)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sus'
)
