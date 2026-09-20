#!/usr/bin/env bash
# PostgreSQL backup for production.
#
# Dumps the database from the running `postgres` service (via
# docker-compose.prod.yml) into a timestamped, gzip-compressed file, and
# deletes backups older than BACKUP_RETENTION_DAYS.
#
# The backup lands on the HOST at BACKUP_DIR (default: ./backups next to
# docker-compose.prod.yml) -- NOT inside the postgres container/volume --
# so it survives even if that container or its volume is destroyed. Copy
# BACKUP_DIR to separate storage (another host, object storage, etc.) on a
# schedule; this script only produces the file, it does not ship it
# anywhere by itself (see docs/production-deployment.md).
#
# Suggested daily cron entry:
#   0 2 * * * cd /path/to/nexora && ./scripts/backup_postgres.sh >> /var/log/nexora-backup.log 2>&1
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found." >&2
    exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${POSTGRES_DB:?POSTGRES_DB must be set in $ENV_FILE}"
: "${POSTGRES_USER:?POSTGRES_USER must be set in $ENV_FILE}"

mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$BACKUP_DIR/${POSTGRES_DB}_${TIMESTAMP}.sql.gz"

echo "== Backing up '$POSTGRES_DB' to $OUT_FILE =="
docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --clean --if-exists \
    | gzip > "$OUT_FILE"

echo "== Backup written: $(du -h "$OUT_FILE" | cut -f1) =="

echo "== Removing backups older than $BACKUP_RETENTION_DAYS days from $BACKUP_DIR =="
find "$BACKUP_DIR" -maxdepth 1 -name "${POSTGRES_DB}_*.sql.gz" -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete

echo "== Done =="
