# Production Deployment (Nexora)

This document covers deploying the `stage`/`main` production stack:
Nginx + Gunicorn + PostgreSQL + Redis + Celery Worker + Celery Beat,
behind HTTPS, with backups and rollback.

It does **not** cover local development -- see the project `README.md`
and `docker-compose.yml` for that (SQLite, `runserver`, unchanged by any
of this).

## 1. Server prerequisites

- A Linux server (Debian/Ubuntu assumed below) with a public IP.
- A domain name (e.g. `example.com`) with an **A record pointing at that
  IP**. This must resolve before requesting a TLS certificate (step 5).
- Docker Engine + the Docker Compose plugin installed:
  ```bash
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"   # log out/in afterwards
  docker compose version            # sanity check
  ```
- Git (to pull this repository onto the server), or just `scp` the files
  listed below.

## 2. Firewall / ports

Only two ports need to be open to the internet:

| Port | Purpose                          |
|------|-----------------------------------|
| 80   | HTTP (redirects to HTTPS, and the Let's Encrypt ACME challenge) |
| 443  | HTTPS (the actual site)          |
| 22   | SSH (restrict to your IP/VPN if possible) |

PostgreSQL (5432) and Redis (6379) are **never** published to the host --
`docker-compose.prod.yml` does not map them to any host port, so no
firewall rule can accidentally expose them either.

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 3. DNS / domain configuration

Point your domain's A (and AAAA, if using IPv6) record at the server's IP
address before continuing. `SITE_DOMAIN` in `.env` (step 4) must be that
**bare** domain, e.g. `example.com` -- no `https://`, no port. This is the
same value Nginx uses for `server_name` and certbot uses for the
certificate (see `docker/nginx/templates/default.conf.template` and
`scripts/init-letsencrypt.sh`).

## 4. `.env`

On the server, create a directory (e.g. `~/nexora`) containing:
- `docker-compose.prod.yml`
- `docker/` (Nginx templates)
- `scripts/` (`chmod +x scripts/*.sh`)
- a real `.env` file, created from `.env.example` -- **never commit this
  file or copy it into a Docker image.**

Fill in at least:

```dotenv
DEBUG=False
SECRET_KEY=<generate a long random value, e.g. `openssl rand -base64 48`>
ALLOWED_HOSTS=example.com
CSRF_TRUSTED_ORIGINS=https://example.com

SITE_DOMAIN=example.com
SITE_DISPLAY_NAME=Nexora

CERTBOT_EMAIL=you@example.com

POSTGRES_DB=nexora
POSTGRES_USER=nexora
POSTGRES_PASSWORD=<long random password>
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_PASSWORD=<long random password>

EMAIL_HOST_USER=<gmail address used for SMTP>
EMAIL_HOST_PASSWORD=<gmail App Password -- see "Gmail SMTP" below>

MAPBOX_ACCESS_TOKEN=<your Mapbox token, if the contact-page map is used>
```

Leave `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
and `SECURE_HSTS_SECONDS` at their commented-out defaults for the very
first deploy -- see step 7.

### Gmail SMTP

Use a Gmail **App Password** (not the account password) for
`EMAIL_HOST_PASSWORD` -- requires 2-Step Verification enabled on the
Google account, then Google Account -> Security -> App passwords.

> **If a real Gmail address/App Password was ever committed, shared, or
> otherwise exposed (e.g. pasted into a chat, an issue, a screen share),
> treat it as compromised: revoke it from Google Account -> Security ->
> App passwords immediately and issue a new one.** This applies
> regardless of whether the value ever reached this server or Git.

### GHCR (GitHub Container Registry)

`docker-compose.prod.yml` pulls the `backend`/`worker`/`beat` image from
GHCR (`ghcr.io/<owner>/<repo>`), built by `.github/workflows/deploy.yml`
from `dockerfile.prod`. On the server:

```bash
echo "<a GitHub PAT with read:packages, or a deploy token>" | \
  docker login ghcr.io -u <github-username> --password-stdin
```

The CD workflow itself authenticates with the built-in `GITHUB_TOKEN` and
needs these **GitHub Actions secrets** configured on the repository
(Settings -> Secrets and variables -> Actions), used by
`.github/workflows/deploy.yml`:

| Secret            | Value                                   |
|-------------------|------------------------------------------|
| `DEPLOY_HOST`     | server IP/hostname                       |
| `DEPLOY_USER`     | SSH user (with Docker permissions)       |
| `DEPLOY_SSH_KEY`  | private key for that user                |
| `DEPLOY_PORT`     | SSH port, optional (default 22)          |

## 5. First deployment

```bash
cd ~/nexora
docker compose -f docker-compose.prod.yml pull postgres redis nginx certbot
IMAGE=ghcr.io/<owner>/<repo> IMAGE_TAG=<a tag already pushed by CI> \
  docker compose -f docker-compose.prod.yml pull backend worker beat
```

### 5a. Bootstrap HTTPS (once per domain)

```bash
./scripts/init-letsencrypt.sh
```

This creates a temporary self-signed certificate, starts Nginx, requests
the real Let's Encrypt certificate over the now-reachable ACME path, and
reloads Nginx with it. See the script's comments for exactly what it
does. Use `CERTBOT_STAGING=1 ./scripts/init-letsencrypt.sh` first if you
want to test against Let's Encrypt's staging environment (higher rate
limits, untrusted certs) before doing it for real.

### 5b. Migrate, collect static, start everything

```bash
IMAGE=ghcr.io/<owner>/<repo> IMAGE_TAG=<tag> ./scripts/deploy.sh
```

This runs, in order: pull -> wait for Postgres/Redis healthy -> migrate
-> collectstatic -> sync the Site row -> start/restart
backend/worker/beat/nginx -> health checks. See `scripts/deploy.sh`.

Every subsequent deploy is the same command (with a new `IMAGE_TAG`) --
in practice this is what `.github/workflows/deploy.yml` runs on `main`.

### 5c. Verify HTTPS end-to-end before enabling HSTS

```bash
curl -I https://example.com/            # expect HTTP/2 200 (or a redirect to a real page)
curl -I http://example.com/             # expect 301 to https://
```

Once this is confirmed working (including logging in, checkout, etc. --
see the smoke-test list at the end of this document), set in `.env`:

```dotenv
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
```

then redeploy (`./scripts/deploy.sh` again, same `IMAGE_TAG`) to pick it
up. **Do not set `SECURE_HSTS_SECONDS` until HTTPS is fully verified** --
browsers cache HSTS and it cannot be undone remotely.

## 6. Certificate renewal

Let's Encrypt certificates last 90 days. Add a cron job on the host:

```bash
crontab -e
# Twice a day is the standard recommendation (certbot only actually
# renews within the last 30 days of expiry, so extra runs are no-ops):
0 3,15 * * * cd ~/nexora && ./scripts/renew-certs.sh >> /var/log/nexora-renew.log 2>&1
```

`scripts/renew-certs.sh` runs `certbot renew` and reloads Nginx.

## 7. Backups

```bash
crontab -e
0 2 * * * cd ~/nexora && ./scripts/backup_postgres.sh >> /var/log/nexora-backup.log 2>&1
```

- Writes a timestamped, gzip-compressed `pg_dump` to `./backups/` on the
  **host** (configurable via `BACKUP_DIR`), independent of the
  `postgres_data` Docker volume.
- Deletes backups older than `BACKUP_RETENTION_DAYS` (default 14).
- **Copy `./backups/` to separate storage** (another host, object
  storage, etc.) on your own schedule -- a backup that only exists on the
  same disk as the database it backs up is not a real backup. This
  script only produces the file; shipping it elsewhere is a separate,
  infrastructure-specific step this repository does not assume for you.

Redis is not backed up: it is only used for the cache, the Celery broker,
and (see section 11 of the original request) never stores anything that
isn't reconstructible from PostgreSQL, which is the source of truth.

### Restore

```bash
./scripts/restore_postgres.sh backups/nexora_20260101T020000Z.sql.gz
```

This stops `backend`/`worker`/`beat`, asks you to type the database name
to confirm (the dump is destructive: `--clean --if-exists`), restores,
then restarts the three services.

## 8. Logs

```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml logs -f worker beat
```

All containers log to stdout/stderr with `json-file` logging and
`max-size: 10m, max-file: 5` (see `docker-compose.prod.yml`), so Docker
itself rotates and caps log growth -- nothing to configure on the host.

## 9. Restart / redeploy

```bash
./scripts/deploy.sh          # same IMAGE/IMAGE_TAG env vars as before
# or, to just restart without changing the image:
docker compose -f docker-compose.prod.yml restart backend worker beat nginx
```

## 10. Rollback

```bash
IMAGE=ghcr.io/<owner>/<repo> ./scripts/rollback.sh
```

Rolls back to the tag recorded by the previous `deploy.sh` run
(`.last-deployed-image-tag.previous`), or pass `IMAGE_TAG=<sha>`
explicitly. **Never touches PostgreSQL, Redis, or media data** -- only
the application image/config is changed. `.github/workflows/deploy.yml`
also runs this automatically if a deploy's health checks fail.

## 11. Health checks

- `https://example.com/health/` -- database connectivity
- `https://example.com/health/redis/` -- Redis connectivity
- Docker-level healthchecks on every service (`docker compose -f
  docker-compose.prod.yml ps` shows `healthy`/`unhealthy` per container)

Neither endpoint returns secrets or credentials in its response.

## 12. Common failures

| Symptom | Likely cause / fix |
|---|---|
| Nginx container won't start | Missing certificate at `/etc/letsencrypt/live/$SITE_DOMAIN/` -- run `scripts/init-letsencrypt.sh` first on a new host. |
| `docker compose ... up` fails with "POSTGRES_PASSWORD must be set" (or similar) | `.env` is missing a required variable -- compare against `.env.example`. |
| 502 from Nginx | `backend` isn't healthy yet or crashed -- `docker compose logs backend`. |
| Emails not sending | Check `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` (Gmail App Password) and `docker compose logs worker` (emails are sent via Celery, not inline). |
| Scheduled tasks not running | Confirm exactly one `beat` container is running (`docker compose ps beat`) -- never scale it. |
| Certificate renewal fails | Confirm port 80 is still reachable from the internet (not blocked by a firewall change) and DNS still points at this server. |
| 413 on image upload | Raise `client_max_body_size` in `docker/nginx/templates/default.conf.template` (default 20m). |

## 13. Manual smoke test after any deploy

- `/`, `/admin/`, `/api/v1/`
- `/static/...`, `/media/...`
- `/sitemap.xml`, `/robots.txt`, the blog/shop RSS feed
- Login, registration + e-mail verification, password reset (check the
  emailed link is `https://...`)
- Cart, checkout
- Vendor dashboard, product upload (exercises the Nginx upload size limit
  and media volume)
