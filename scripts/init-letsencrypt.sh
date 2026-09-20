#!/usr/bin/env bash
# One-time bootstrap for HTTPS on a brand new host.
#
# Nginx's config (docker/nginx/templates/default.conf.template) always
# points at /etc/letsencrypt/live/$DOMAIN/{fullchain,privkey}.pem, so on a
# host with no certificate yet Nginx cannot start at all -- which would
# also block the very HTTP ACME challenge certbot needs to issue the real
# certificate. The standard fix (used here, same approach as the widely
# used wmnnd/nginx-certbot recipe): create a short-lived self-signed
# "dummy" certificate at that exact path first, start Nginx with it, then
# ask certbot for the real certificate over the now-reachable :80 ACME
# path, and finally reload Nginx to pick it up.
#
# Run this ONCE per domain, from the directory containing
# docker-compose.prod.yml, after `.env` (with a real SITE_DOMAIN and a
# real CERTBOT_EMAIL) is in place:
#
#   ./scripts/init-letsencrypt.sh
#
# Safe to re-run: it skips straight to requesting the real certificate if
# one already exists for the domain.
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Copy .env.example to .env and fill it in first." >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

DOMAIN="${SITE_DOMAIN:?SITE_DOMAIN must be set in $ENV_FILE (bare domain, e.g. example.com)}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:?CERTBOT_EMAIL must be set in $ENV_FILE (used for Let's Encrypt expiry notices)}"
STAGING="${CERTBOT_STAGING:-0}"
LIVE_PATH="/etc/letsencrypt/live/$DOMAIN"

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

echo "== Domain: $DOMAIN =="

if compose run --rm --entrypoint "test -f $LIVE_PATH/fullchain.pem" certbot; then
    echo "A certificate already exists for $DOMAIN -- skipping the dummy certificate step."
else
    echo "== Creating a temporary self-signed certificate for $DOMAIN =="
    compose run --rm --entrypoint "mkdir -p $LIVE_PATH" certbot
    compose run --rm --entrypoint "openssl req -x509 -nodes -newkey rsa:2048 -days 1 -keyout $LIVE_PATH/privkey.pem -out $LIVE_PATH/fullchain.pem -subj /CN=$DOMAIN" certbot

    echo "== Starting Nginx with the temporary certificate =="
    compose up -d nginx

    echo "== Deleting the temporary certificate (the ACME webroot stays reachable) =="
    compose run --rm --entrypoint "rm -rf $LIVE_PATH" certbot
fi

STAGING_ARG=""
if [ "$STAGING" = "1" ]; then
    STAGING_ARG="--staging"
    echo "== Using the Let's Encrypt STAGING (test) environment =="
fi

echo "== Requesting the real certificate from Let's Encrypt =="
# shellcheck disable=SC2086
compose run --rm certbot certonly \
    --webroot -w /var/www/certbot \
    -d "$DOMAIN" \
    --email "$CERTBOT_EMAIL" \
    --rsa-key-size 4096 \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    $STAGING_ARG

echo "== Starting/reloading Nginx with the real certificate =="
compose up -d nginx
compose exec nginx nginx -s reload

echo "== Done. Verify with: curl -I https://$DOMAIN/ =="
echo "Next: keep certificates renewed with scripts/renew-certs.sh (see docs/production-deployment.md)."
