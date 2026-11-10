#!/bin/sh
set -e
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Applying database migrations..."
  alembic upgrade head
fi
# ROOT_PATH: public prefix when served behind a proxy path (e.g. /api) so /docs finds openapi.json
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*' \
  ${ROOT_PATH:+--root-path "$ROOT_PATH"}
