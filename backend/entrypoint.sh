#!/bin/sh
set -e

# Only meaningful when DB_HOST is actually set (Postgres in
# docker-compose/production); local sqlite has nothing to wait for.
if [ -n "$DB_HOST" ]; then
  echo "Waiting for database at $DB_HOST:${DB_PORT:-5432}..."
  until python -c "
import socket, sys, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1)
try:
    s.connect((os.environ['DB_HOST'], int(os.environ.get('DB_PORT', 5432))))
    sys.exit(0)
except Exception:
    sys.exit(1)
"; do
    sleep 1
  done
  echo "Database is up."
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput
# Idempotent (get_or_create-keyed on caption) — safe to run on every
# deploy. Seeds the homepage carousel's starting set of photos once;
# does nothing on every subsequent deploy after that.
python manage.py seed_homepage_images

exec "$@"
