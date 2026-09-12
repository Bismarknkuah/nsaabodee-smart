# Checking the Backend and Frontend Are Actually Working

After `Install-Nsaabodee.bat` (or `Start-Nsaabodee.bat`) finishes, here's
how to actually confirm both sides are working — not just assume it,
the same way everything else in this project was verified rather than
assumed.

## The fastest check: log in

If you can open `http://localhost:3000`, see the login page, log in
with a demo account (see `touring-the-interface.md`), and see a
dashboard with real numbers on it — **both sides are working**. The
frontend rendered a page, which means it's running; the dashboard
showing real data means it successfully talked to the backend, which
means the backend, the database, and the connection between them are
all working too. This one check actually proves more than the
individual checks below — it's the whole chain working end to end.

If that already works for you, you don't need anything else in this
document. The rest of this is for narrowing down *which* piece is
broken if it doesn't.

## Checking each piece separately

### 1. Are the containers even running?

Open the `windows-installer` folder in a terminal and run:

```powershell
docker compose ps
```

You should see five services, each showing **Up** (or "running") in the
Status column — the exact container name prefix depends on which
folder you unzipped this project into, so don't worry if yours doesn't
match this exactly, only whether the Status column says **Up**:

```
NAME                          STATUS
<something>-backend-1        Up 5 minutes
<something>-frontend-1       Up 5 minutes
<something>-db-1             Up 5 minutes (healthy)
<something>-redis-1          Up 5 minutes
<something>-celery_worker-1  Up 5 minutes
```

If anything says **Exited** or **Restarting** instead of **Up**, that
service crashed — skip to "Reading the logs" below and look at that
specific one.

### 2. Is the backend actually responding?

Open `http://localhost:8000/admin/` in your browser (note: `8000`, not
`3000` — this is the backend directly, not the app itself). You should
see Django's built-in administration login page — a plain, unstyled
login form, nothing fancy. Seeing that page at all is the proof: it
means the backend process is running, it successfully connected to the
database, and the database's tables exist (an admin login page can't
render at all if any of those three things failed).

If instead you see a browser error like "This site can't be reached" —
the backend container isn't actually listening on port 8000. Check
`docker compose ps` (above) and the backend's logs (below).

If you see an actual Django error page (a page with a traceback, not
just "can't be reached") — the backend process IS running, but hit a
real error. Read the traceback, or check the backend's logs for the
same error with more context.

### 3. Is the frontend actually responding?

Open `http://localhost:3000` directly. You should see the Nsaabodee
Smart login page, styled properly (the forest-green and gold design,
not a plain unstyled page). If you see "This site can't be reached,"
the frontend container isn't listening on port 3000 — check
`docker compose ps` and its logs.

If the page loads but looks broken/unstyled, or the browser's developer
console (F12) shows red errors mentioning `localhost:8000` or
`NEXT_PUBLIC_API_URL` — the frontend is running, but was built without
correctly knowing where the backend lives. This would need a rebuild:
`docker compose up -d --build frontend`.

### 4. Reading the logs

For a specific service (recommended once you know which one is
misbehaving from the steps above):

```powershell
docker compose logs --tail=100 backend
docker compose logs --tail=100 frontend
docker compose logs --tail=100 db
docker compose logs --tail=100 redis
docker compose logs --tail=100 celery_worker
```

Or double-click `View-Logs.bat` to watch everything live at once.
Press `Ctrl+C` to stop watching (this does not stop the app).

**What a healthy backend log looks like** near the end: lines
mentioning `Watching for file changes`, `Starting ASGI/Daphne version`,
and no lines containing the word `Traceback` or `Error` near the
bottom.

**What a healthy frontend log looks like**: a line saying
`✓ Ready in <some number>ms` or `▲ Next.js` followed by
`- Local: http://localhost:3000`.

### 5. Checking the database has real data

If login works but a page seems to be missing data you'd expect, you
can look directly inside the database:

```powershell
docker compose exec db psql -U nsaabodee -d nsaabodee -c "SELECT username, role FROM accounts_user;"
```

This should list every demo user and their role. An empty result, or a
"relation does not exist" error, means migrations didn't run — check
the backend's logs for a migration error.

## If you're still stuck

Copy the exact text from whichever check above failed — the specific
error message, not just "it didn't work" — and share that. A specific
error from one of these checks is something that can actually be
diagnosed; "it's not working" on its own can't be.
