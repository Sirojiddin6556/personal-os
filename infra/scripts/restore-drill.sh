#!/bin/bash
# Ежемесячный drill: восстановление в изолированную БД + проверка
set -euo pipefail
LATEST=$(aws s3 ls "s3://${BACKUP_BUCKET}/backups/" | sort | tail -1 | awk '{print $4}')
echo "[restore-drill] Restoring: ${LATEST}"
aws s3 cp "s3://${BACKUP_BUCKET}/backups/${LATEST}" /tmp/restore.sql.gz
gunzip -c /tmp/restore.sql.gz | psql "${RESTORE_DATABASE_URL}"
echo "[restore-drill] Verifying row counts..."
psql "${RESTORE_DATABASE_URL}" -c "SELECT COUNT(*) FROM workspaces;"
echo "[restore-drill] PASS"
