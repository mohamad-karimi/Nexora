#!/usr/bin/env bash
# Renew the Let's Encrypt certificate and reload Nginx so it picks up the
# renewed files. certbot only actually renews when the certificate is
# within its renewal window (default: last 30 days of a 90-day cert), so
# this is safe to run frequently.
#
# Documented cron entry (see docs/production-deployment.md) -- run twice a
# day, e.g. via `crontab -e` on the server:
#   0 3,15 * * * cd /path/to/nexora && ./scripts/renew-certs.sh >> /var/log/nexora-renew.log 2>&1
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

compose run --rm certbot renew --webroot -w /var/www/certbot
compose exec nginx nginx -s reload
