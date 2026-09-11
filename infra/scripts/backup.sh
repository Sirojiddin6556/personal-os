#!/bin/bash
# Резервное копирование PostgreSQL + загрузка в S3
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="personal_os_backup_${TIMESTAMP}.sql.gz"

echo "[backup] Starting PostgreSQL dump..."
pg_dump "$DATABASE_URL" | gzip > "/tmp/${BACKUP_FILE}"

echo "[backup] Uploading to S3..."
aws s3 cp "/tmp/${BACKUP_FILE}" "s3://${BACKUP_BUCKET}/backups/${BACKUP_FILE}"

echo "[backup] Cleanup local file..."
rm "/tmp/${BACKUP_FILE}"

echo "[backup] Done: ${BACKUP_FILE}"
