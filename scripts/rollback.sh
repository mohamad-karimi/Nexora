#!/usr/bin/env bash
# Roll back to the previously deployed image tag.
#
# Only the application image/config is changed -- PostgreSQL, Redis and
# media data (all in named volumes: postgres_data, redis_data, media_data,
# static_data) are never touched by this script.
#
# Usage:
#   ./scripts/rollback.sh                 # rolls back to the tag recorded
#                                          # by the last scripts/deploy.sh
#   IMAGE_TAG=<sha> ./scripts/rollback.sh  # rolls back to an explicit tag
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
STATE_FILE="${STATE_FILE:-.last-deployed-image-tag}"

IMAGE="${IMAGE:?IMAGE must be set (e.g. ghcr.io/owner/repo)}"

if [ -z "${IMAGE_TAG:-}" ]; then
    IMAGE_TAG="$(cat "${STATE_FILE}.previous" 2>/dev/null || true)"
fi
IMAGE_TAG="${IMAGE_TAG:?No previous tag recorded (${STATE_FILE}.previous missing) -- set IMAGE_TAG explicitly}"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found on the server." >&2
    exit 1
fi

echo "== Rolling back to $IMAGE:$IMAGE_TAG =="
IMAGE="$IMAGE" IMAGE_TAG="$IMAGE_TAG" "$(dirname "$0")/deploy.sh"

echo "== Rollback to $IMAGE_TAG complete =="
