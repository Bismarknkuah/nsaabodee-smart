# Hosting Nsaabodee Smart Online — Full Step-by-Step

This walks through every single step to put Nsaabodee Smart on the
real internet, so anyone anywhere can use it — not just your own
laptop. Three services, in this order:

1. **GitHub** — where your code lives online (free)
2. **Railway** — runs the backend, the database ("mypostres"), Redis,
   and the background worker (free to start, small monthly cost later)
3. **Vercel** — runs the frontend, the part people actually see and
   click on (free)

**Why this exact order matters:** the frontend (Vercel) needs to know
the *address* of the backend (Railway) before it can be built. So
Railway has to exist first, even though you might think of the
frontend as "the app" and want to set that up first — if you set up
Vercel before Railway, you'd have to redo the Vercel step afterward
anyway. Getting the order right the first time saves you a repeat.

Each of the three sections below assumes you've completed nothing
before it except what the earlier sections describe. Take it slowly,
one box at a time.

---

## Part 1 — GitHub: getting your code online

GitHub is just a place your code lives on the internet, so Railway and
Vercel can both read it from there. If you already pushed this project
to GitHub, skip to Part 2.

1. Go to [github.com](https://github.com) and create a free account if
   you don't have one (top-right **Sign up**).
2. Once logged in, click the **+** icon in the top-right corner of any
   GitHub page → **New repository**.
3. Give it a name (e.g. `nsaabodee-smart`). Leave everything else as
   its default. **Do not** check "Add a README file" — you already
   have one, and it would conflict.
4. Click **Create repository**. You'll land on an empty repository
   page with a box of commands — ignore those, we'll do this from VS
   Code instead, which is easier.
5. Open this project folder in **VS Code**.
6. Click the Source Control icon in the left sidebar (it looks like a
   branching line, or press `Ctrl+Shift+G`).
7. Click **Initialize Repository** if you see that button.
8. Type a short message in the box at the top (e.g. "first upload")
   and click the **✓ Commit** button.
9. Click **Publish Branch**. VS Code will ask which GitHub account and
   which repository — choose the one you just created.
10. Wait for it to finish uploading. Refresh the GitHub page from step
    4 — you should now see all your project's files listed there.

**From now on**, whenever you make changes and want them reflected
online, repeat steps 8-9 in VS Code (commit, then push) — Railway and
Vercel both watch your GitHub repository and redeploy automatically
every time you push new code.

---

## Part 2 — Railway: the backend, the database, Redis, and the worker

This is the biggest part, because Railway is hosting four separate
pieces. Take each numbered step in order — don't skip ahead.

### 2.1 — Create the Railway account and project

1. Go to [railway.com](https://railway.com) → **Login** → **Login with
   GitHub** (easiest — it links your account automatically).
2. Click **New Project**.
3. Choose **Deploy from GitHub repo**.
4. The first time, Railway asks permission to see your GitHub
   repositories — click **Configure GitHub App**, then either allow
   access to **All repositories** or specifically select the one you
   just created, then **Save**.
5. Back on Railway, click your repository in the list. Railway creates
   a project and starts trying to build it automatically — let it try
   and fail, that's expected and we'll fix it in the next step.

### 2.2 — Point Railway at the `backend` folder specifically

Your repository has three separate folders (`backend`, `frontend`,
`mobile`) — Railway needs to be told which one this particular service
actually is.

1. Click on the service box Railway just created (it'll be named after
   your repository).
2. Click the **Settings** tab.
3. Find **Root Directory** (sometimes under a "Source" or "Build"
   section) and type: `backend`
4. Railway will automatically try rebuilding after you change this —
   let it. This first build may still fail (there's no database yet) —
   that's expected, keep going.

### 2.3 — Add the database ("mypostres" — your PostgreSQL database)

1. In your Railway project (the same screen, zoomed out to see the
   whole project canvas — click your project's name at the top if
   you're still zoomed into one service), click the **+ New** button.
2. Choose **Database** → **Add PostgreSQL**.
3. A new box appears in your project labeled **Postgres**. This is
   your real, permanent database — Railway manages it, backs it up,
   and gives your backend a way to connect to it automatically (you
   never need to remember a password for it yourself).

### 2.4 — Add Redis

1. Click **+ New** again → **Database** → **Add Redis**.
2. A second new box appears, labeled **Redis**.

Your project canvas should now show three boxes: your backend service,
Postgres, and Redis.

### 2.5 — Tell the backend how to find the database and Redis

1. Click back into your backend service (not Postgres, not Redis).
2. Click the **Variables** tab.
3. Click **+ New Variable** for each row below. For values that start
   with `${{`, type exactly that (including the double curly braces) —
   Railway will pop up a suggestion list of every variable from every
   other service in your project; pick the matching one, or just
   finish typing it exactly as shown.

   | Variable name | Value |
   |---|---|
   | `DJANGO_SECRET_KEY` | any long random sentence of letters/numbers — treat it like a password, never share it |
   | `DJANGO_DEBUG` | `False` |
   | `DB_ENGINE` | `django.db.backends.postgresql` |
   | `DB_HOST` | `${{Postgres.PGHOST}}` |
   | `DB_PORT` | `${{Postgres.PGPORT}}` |
   | `DB_NAME` | `${{Postgres.PGDATABASE}}` |
   | `DB_USER` | `${{Postgres.PGUSER}}` |
   | `DB_PASSWORD` | `${{Postgres.PGPASSWORD}}` |
   | `CELERY_BROKER_URL` | `${{Redis.REDIS_URL}}` |
   | `CHANNEL_LAYERS_REDIS_URL` | `${{Redis.REDIS_URL}}` |
   | `CELERY_TASK_ALWAYS_EAGER` | `False` |

   **The `DB_ENGINE` row is the single easiest thing to forget on this
   entire list** — without it, the app quietly keeps using a temporary,
   throwaway database instead of your real Postgres one, with no error
   message telling you that happened.

4. Leave `DJANGO_ALLOWED_HOSTS` out for now — you'll add it in the next
   step, once you have an actual address to put in it.

### 2.6 — Give your backend a real address on the internet

1. Still in your backend service, click **Settings** → look for
   **Networking**.
2. Click **Generate Domain**.
3. Railway shows you an address like
   `nsaabodee-smart-production.up.railway.app` — **copy this**, you'll
   need it twice more below.
4. Go back to **Variables**, add one more:

   | Variable name | Value |
   |---|---|
   | `DJANGO_ALLOWED_HOSTS` | paste the address from step 3, **without** `https://` in front of it |

### 2.7 — Add the background worker (Celery)

This is a second, separate service that handles things like sending
SMS/WhatsApp notifications in the background — it needs its own entry
in Railway, running the exact same code but with a different job.

1. Click **+ New** on your project canvas → **GitHub Repo** → the same
   repository again.
2. Click into this new service → **Settings** → **Root Directory**:
   `backend` (same as before).
3. Still in Settings, find **Deploy** → **Custom Start Command**, and
   enter exactly:
   ```
   celery -A nsaabodeeq worker --loglevel=info
   ```
4. Go to this service's **Variables** tab and add the exact same rows
   as step 2.5 above (you can copy them from your backend service —
   Railway has a "copy variables from another service" option in the
   Variables tab's menu, or just re-type them the same way). This
   service does **not** need `DJANGO_ALLOWED_HOSTS` or a generated
   domain — it never receives web traffic directly.

### 2.8 — Watch it deploy

1. Click the **Deployments** tab on your backend service.
2. Wait for the build to finish — a green checkmark means success, red
   means it failed (click into it to read why; the most common cause
   is a typo in one of the variables from 2.5).
3. Repeat for the Celery worker service.

Once both show green, open the address from step 2.6.3 in your browser
with `/admin/` on the end (e.g.
`https://nsaabodee-smart-production.up.railway.app/admin/`) — you
should see a plain Django login page. That confirms your backend,
database, and Redis are all correctly connected.

---

## Part 3 — Vercel: the frontend (the part people actually see)

1. Go to [vercel.com](https://vercel.com) → **Sign Up** → **Continue
   with GitHub**.
2. Click **Add New...** → **Project**.
3. Find your repository in the list and click **Import** next to it
   (if it's not listed, click **Adjust GitHub App Permissions** and
   grant Vercel access to it, the same way you did for Railway).
4. On the configuration screen that appears, before clicking anything
   else:
   - Find **Root Directory**, click **Edit**, and choose `frontend`.
   - Framework Preset should automatically say **Next.js** — leave it.
5. Expand **Environment Variables** on the same screen and add:

   | Variable name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://` followed by the exact address you copied in step 2.6.3 above |

   Get this right *before* clicking Deploy — Next.js bakes this value
   permanently into the files it builds. If you need to change it
   later, you'll need to trigger a brand new deployment afterward, not
   just edit the variable and expect it to update on its own.
6. Click **Deploy**.
7. Wait a minute or two. When it finishes, Vercel shows you a domain
   like `nsaabodee-smart.vercel.app` with a **Visit** button.
8. Click it — you should see the actual Nsaabodee Smart login page,
   properly styled (forest green and gold), not a plain page.

---

## Part 4 — Create your very first real login

A fresh deployment starts completely empty on purpose — no demo data,
no communities, nothing (the demo accounts you may have used locally
are a local-only convenience). You need one superuser account to create
your first real community.

1. Back in Railway, click your backend service → the **⋮** menu (or a
   button labeled **Shell**/**Connect**, depending on Railway's current
   layout) to open a command line directly inside your running backend.
2. Type:
   ```
   python manage.py createsuperuser
   ```
   and follow the prompts (username, email, password — pick something
   real, this is not a demo account).
3. Go to your Vercel URL, log in with that account, and open
   **Communities** in the navigation.
4. Click **+ New community**, fill in a name and its first admin
   username/password, and create it.
5. Give that admin login to whoever will actually run that community —
   from that point on, they manage their own families, members, and
   funerals entirely on their own, without needing you.

---

## Checking your online deployment actually works

Same logic as checking it locally, just pointed at your real addresses
instead of `localhost`:

- `https://your-railway-address/admin/` should show a plain Django
  login page (proves the backend + database are connected).
- `https://your-vercel-address` should show the styled Nsaabodee Smart
  login page (proves the frontend built correctly).
- Logging in and seeing a dashboard with real data proves both sides
  are correctly talking to each other.

If something's wrong, Railway's **Deployments** tab and the **View
Logs** option on each service show the same kind of real-time logs
`View-Logs.bat` shows locally — read the most recent lines for the
actual error rather than guessing.

---

## Roughly what this costs

Vercel's free tier comfortably covers a single community's frontend
traffic. Railway is usage-based — a backend + Postgres + Redis + a
lightly-used worker for one community will likely land somewhere
around $5-20/month once any free starting credit runs out. Neither
platform requires a credit card just to start.

## An honest note on this guide

Every step above was checked against Railway's and Vercel's own current
documentation and several 2026 walkthroughs — not written purely from
memory. But neither platform was actually clicked through end-to-end
from the environment this project was built in (no live account, no
route to either service's real servers there). If a button turns out
to be labeled slightly differently, or laid out in a different place
than described, that's genuinely useful to report back — the same as
with the Windows installer, this was researched and reviewed carefully,
not executed and proven the way this project's own 363 backend tests
were.
