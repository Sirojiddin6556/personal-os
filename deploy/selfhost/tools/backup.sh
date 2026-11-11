#!/bin/sh
# Daily backup of the self-hosted stack: database (pg_dump -Fc) + uploaded files.
#   tools/backup.sh [backup_dir] [keep_days]
# cron (03:30 daily):
#   30 3 * * * /opt/personal-os/app/deploy/selfhost/tools/backup.sh >> /opt/personal-os/db-backups/backup.log 2>&1
# Restore DB:    docker compose exec -T db pg_restore -U personal_os -d personal_os --clean --if-exists < FILE.dump
# Restore files: docker compose exec -T -u 0 api tar -xzf - -C /app/data < FILE-uploads.tar.gz
set -eu

cd "$(dirname "$0")/.."
DIR="${1:-/opt/personal-os/db-backups}"
KEEP_DAYS="${2:-14}"
PROJECT="${COMPOSE_PROJECT_NAME:-personal-os}"
STAMP="$(date +%Y%m%d-%H%M%S)"
umask 077
mkdir -p "$DIR"

dc() { docker compose -p "$PROJECT" "$@"; }

DB="$DIR/daily-$STAMP.dump"
dc exec -T db pg_dump -U personal_os -d personal_os -Fc > "$DB.part"
# A truncated dump must never replace a good one: check it lists its contents.
dc exec -T db pg_restore --list < "$DB.part" > /dev/null
mv "$DB.part" "$DB"

FILES="$DIR/daily-$STAMP-uploads.tar.gz"
dc exec -T api tar -czf - -C /app/data . > "$FILES.part"
gzip -t "$FILES.part"
mv "$FILES.part" "$FILES"

# Rotation: only our own daily-* files; manual pre-*.dump copies are kept.
find "$DIR" -maxdepth 1 -type f -name 'daily-*' -mtime +"$KEEP_DAYS" -delete
find "$DIR" -maxdepth 1 -type f -name 'daily-*.part' -delete

echo "$(date -Is) ok $(du -h "$DB" | cut -f1) db, $(du -h "$FILES" | cut -f1) files -> $DIR"
