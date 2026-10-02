#!/bin/bash
# One script to rebuild and start the whole local dev environment from
# scratch, handling every recurring issue hit during setup: missing
# venv, missing start_backend.sh, missing node_modules, missing
# .env.local, stray processes on the wrong ports, and an unseeded or
# stale database. Run this from anywhere — it finds its own location.
#
# Usage: ./reset_dev.sh

set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "=== 1. Clearing any stray processes on ports 3000/3001/3002/8000 ==="
lsof -ti :3000,3001,3002,8000 2>/dev/null | xargs kill -9 2>/dev/null || true
pkill -9 -f "manage.py runserver" 2>/dev/null || true
sleep 1

echo "=== 2. Backend: venv ==="
cd "$ROOT/backend"
if [ ! -d "venv" ]; then
  echo "  venv missing — creating it (this project needs Python 3.12+)"
  PYTHON_BIN="$(command -v python3.12 || echo /opt/homebrew/bin/python3.12)"
  "$PYTHON_BIN" -m venv venv
fi
source venv/bin/activate

echo "=== 3. Backend: dependencies ==="
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "=== 4. Backend: environment + migrate ==="
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
export DJANGO_SECRET_KEY=local-dev-secret-key-change-for-real-use
export CELERY_TASK_ALWAYS_EAGER=True
export FRONTEND_BASE_URL=http://localhost:3000
export DEMO_MODE_ENABLED=True
python manage.py migrate --verbosity 0

echo "=== 5. Backend: seed demo data ==="
python manage.py seed_demo_data

echo "=== 6. Starting backend in the background ==="
nohup python manage.py runserver 8000 > /tmp/nsaabodee_backend.log 2>&1 &
BACKEND_PID=$!
sleep 4

echo "=== 7. Verifying the backend actually answers (this is the part that's failed silently before) ==="
RESULT=$(curl -s -X POST http://localhost:8000/api/auth/demo-login/ -H "Content-Type: application/json" -d '{"role": "platform_admin"}')
if echo "$RESULT" | grep -q '"access"'; then
  echo "  ✔ Backend confirmed working — demo login returns a real token."
else
  echo "  ✘ Backend did NOT return a valid login. Raw response below — stop here and share this:"
  echo "  $RESULT"
  echo "  Log file: /tmp/nsaabodee_backend.log"
  exit 1
fi

echo "=== 8. Frontend: dependencies ==="
cd "$ROOT/frontend"
if [ ! -d "node_modules" ]; then
  echo "  node_modules missing — running npm install (this takes a minute)"
  npm install --silent
fi

echo "=== 9. Frontend: .env.local ==="
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

echo "=== 10. Frontend: clearing any stale build cache ==="
# NEXT_PUBLIC_* values are baked into the compiled client bundle. A
# .next cache from before .env.local existed (or from before it
# changed) will keep serving the OLD baked-in value silently — no
# error, just requests quietly going to the wrong place. Always clear
# this, every run, not just on a first-time setup.
rm -rf .next

echo ""
echo "=== All checks passed. Backend is running in the background (PID $BACKEND_PID, log at /tmp/nsaabodee_backend.log). ==="
echo "=== Starting frontend now — this will take over this terminal. Press Ctrl+C to stop both when you're done. ==="
echo ""

trap "kill $BACKEND_PID 2>/dev/null" EXIT
npm run dev
