#!/usr/bin/env bash
# Restore a PostgreSQL backup produced by scripts/backup_postgres.sh.
#
# Usage:
#   ./scripts/restore_postgres.sh backups/nexora_20260101T020000Z.sql.gz
#
# DESTRUCTIVE: the dump was taken with --clean --if-exists, so restoring it
# drops and recreates the objects it contains in the target database.
# Stop the app first (or at least accept a brief inconsistency window) --
# see docs/production-deployment.md "Restore".
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_FILE="${1:?Usage: $0 <path-to-backup.sql.gz>}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: backup file not found: $BACKUP_FILE" >&2
    exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found." >&2
    exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${POSTGRES_DB:?POSTGRES_DB must be set in $ENV_FILE}"
: "${POSTGRES_USER:?POSTGRES_USER must be set in $ENV_FILE}"

echo "About to restore '$BACKUP_FILE' into database '$POSTGRES_DB'."
echo "This will DROP existing objects in that database before recreating them."
read -r -p "Type the database name ($POSTGRES_DB) to confirm: " CONFIRM
if [ "$CONFIRM" != "$POSTGRES_DB" ]; then
    echo "Confirmation did not match -- aborting."
    exit 1
fi

echo "== Stopping backend/worker/beat so nothing writes during restore =="
docker compose -f "$COMPOSE_FILE" stop backend worker beat

echo "== Restoring =="
gunzip -c "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo "== Restarting backend/worker/beat =="
docker compose -f "$COMPOSE_FILE" up -d backend worker beat

echo "== Done. Verify with the app's health checks and a spot-check of recent data. =="
