#!/usr/bin/env bash
# Deploy a specific image tag to production, in the required order:
#   1. pull images
#   2. wait for postgres/redis healthy
#   3. run migrations (one-shot, not inside every Gunicorn worker)
#   4. collectstatic (one-shot)
#   5. sync the django.contrib.sites row (idempotent, see
#      core/website/management/commands/sync_site.py)
#   6. (re)start backend, worker, beat, nginx
#   7. run health checks
#
# Called by .github/workflows/deploy.yml on the server, but also runnable
# by hand:
#   IMAGE=ghcr.io/<owner>/<repo> IMAGE_TAG=<sha> ./scripts/deploy.sh
#
# Records the tag that was running before this deploy in
# .last-deployed-image-tag so scripts/rollback.sh can go back to it.
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
STATE_FILE="${STATE_FILE:-.last-deployed-image-tag}"

IMAGE="${IMAGE:?IMAGE must be set (e.g. ghcr.io/owner/repo)}"
IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG must be set (e.g. the git SHA tag)}"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found on the server." >&2
    exit 1
fi

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

export IMAGE IMAGE_TAG

echo "== [1/7] Recording the currently-running tag for rollback =="
PREVIOUS_TAG="$(cat "$STATE_FILE" 2>/dev/null || echo "")"
if [ -n "$PREVIOUS_TAG" ] && [ "$PREVIOUS_TAG" != "$IMAGE_TAG" ]; then
    echo "$PREVIOUS_TAG" > "${STATE_FILE}.previous"
    echo "Previous tag was: $PREVIOUS_TAG (saved to ${STATE_FILE}.previous)"
else
    echo "No previous recorded tag (first deploy, or redeploying the same tag)."
fi

echo "== [2/7] Pulling images ($IMAGE:$IMAGE_TAG) =="
compose pull backend worker beat

echo "== [3/7] Waiting for PostgreSQL and Redis to be healthy =="
compose up -d postgres redis
for svc in postgres redis; do
    for i in $(seq 1 30); do
        status="$(docker inspect -f '{{.State.Health.Status}}' "$svc" 2>/dev/null || echo starting)"
        [ "$status" = "healthy" ] && break
        echo "  $svc: $status (attempt $i)"
        sleep 3
    done
    [ "$status" = "healthy" ] || { echo "ERROR: $svc did not become healthy"; compose logs "$svc"; exit 1; }
done

echo "== [4/7] Running migrations (one-shot) =="
compose run --rm backend python manage.py migrate --noinput

echo "== [5/7] Collecting static files and syncing the Site row (one-shot) =="
compose run --rm backend python manage.py collectstatic --noinput
compose run --rm backend python manage.py sync_site

echo "== [6/7] Restarting backend, worker, beat, nginx =="
compose up -d backend worker beat nginx

echo "== [7/7] Health checks =="
for svc in backend worker beat nginx; do
    for i in $(seq 1 30); do
        status="$(docker inspect -f '{{.State.Health.Status}}' "$svc" 2>/dev/null || echo starting)"
        [ "$status" = "healthy" ] && break
        echo "  $svc: $status (attempt $i)"
        sleep 3
    done
    if [ "$status" != "healthy" ]; then
        echo "ERROR: $svc did not become healthy after deploy. Logs:"
        compose logs "$svc"
        echo "Deploy FAILED. Consider ./scripts/rollback.sh"
        exit 1
    fi
done

echo "$IMAGE_TAG" > "$STATE_FILE"
echo "== Deploy of $IMAGE:$IMAGE_TAG succeeded =="
