#!/usr/bin/env bash
# Deploy a specific image tag to production, in the required order:
#   1. pull images
#   2. wait for postgres/redis healthy
#   3. run migrations (one-shot, not inside every Gunicorn worker)
#   4. seed initial store/blog data (idempotent, safe to run on every
#      deploy -- see core/orders/management/commands/seed_store.py and
#      core/blog/management/commands/seed_blog.py; both skip silently if
#      their data already exists and never touch anything else)
#   5. collectstatic (one-shot)
#   6. sync the django.contrib.sites row (idempotent, see
#      core/website/management/commands/sync_site.py)
#   7. (re)start backend, worker, beat, nginx
#   8. run health checks
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

echo "== [1/8] Recording the currently-running tag for rollback =="
PREVIOUS_TAG="$(cat "$STATE_FILE" 2>/dev/null || echo "")"
if [ -n "$PREVIOUS_TAG" ] && [ "$PREVIOUS_TAG" != "$IMAGE_TAG" ]; then
    echo "$PREVIOUS_TAG" > "${STATE_FILE}.previous"
    echo "Previous tag was: $PREVIOUS_TAG (saved to ${STATE_FILE}.previous)"
else
    echo "No previous recorded tag (first deploy, or redeploying the same tag)."
fi

echo "== [2/8] Pulling images ($IMAGE:$IMAGE_TAG) =="
compose pull backend worker beat

echo "== [3/8] Waiting for PostgreSQL and Redis to be healthy =="
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

echo "== [4/8] Running migrations (one-shot) =="
compose run --rm backend python manage.py migrate --noinput

echo "== [5/8] Seeding initial store/blog data (one-shot, idempotent) =="
# Never passed --flush here: that flag deletes previously-seeded rows,
# which must stay a deliberate, manual, interactive action -- never
# something a routine deploy can trigger. Each command checks its own
# marker (a known vendor/category) and exits immediately if it already
# ran, so this is safe to leave in the pipeline on every future deploy.
compose run --rm backend python manage.py seed_store
compose run --rm backend python manage.py seed_blog

echo "== [6/8] Collecting static files and syncing the Site row (one-shot) =="
compose run --rm backend python manage.py collectstatic --noinput
compose run --rm backend python manage.py sync_site

echo "== [7/8] Restarting backend, worker, beat, nginx =="
compose up -d backend worker beat nginx

echo "== [8/8] Health checks =="
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
