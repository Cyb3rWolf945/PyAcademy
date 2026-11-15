#!/bin/sh
# Arranque da app: migrações, bootstrap (professor + problemas) e servidor.
# Em dev (APP_ENV=dev) usa uvicorn com --reload; em produção usa gunicorn.
set -e
alembic upgrade head
python -m app.bootstrap
if [ "$APP_ENV" = "dev" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/backend \
    --ws-max-size 8192 --proxy-headers --forwarded-allow-ips='*'
fi
exec gunicorn app.main:app -k app.realtime.worker.Worker -w "${WEB_CONCURRENCY:-2}" \
  -b 0.0.0.0:8000 --timeout 60 --graceful-timeout 20 --access-logfile - \
  --forwarded-allow-ips='*'
