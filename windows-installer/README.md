# Nsaabodee Smart — Windows Setup

The easiest way to run Nsaabodee Smart on a Windows computer, without
needing to install Python, Node.js, PostgreSQL, or Redis yourself —
Docker handles all of that inside containers.

## What you need first

**Docker Desktop** is the only thing you need to install yourself.
`Install-Nsaabodee.bat` will check for it and open the download page
for you if it's missing — but you'll need to actually run the Docker
installer and restart your computer if it asks you to, then come back
and run `Install-Nsaabodee.bat` again.

Docker Desktop requires **Windows 10 or 11, 64-bit**, with virtualization
enabled (most computers have this on by default; if Docker's own
installer tells you virtualization is off, you'll need to enable it in
your computer's BIOS/UEFI settings — Docker's installer will tell you
exactly how for your specific machine).

## First-time setup

1. Unzip this project somewhere on your computer (e.g., your Desktop).
2. Open the `windows-installer` folder.
3. **Double-click `Install-Nsaabodee.bat`.**
4. Follow whatever it tells you on screen. The first run downloads and
   builds everything, which can take several minutes depending on your
   internet connection — this is normal, let it finish.
5. When it's done, your browser will open automatically to
   `http://localhost:3000` with demo login details printed in the
   black window (scroll up if you missed them).

## Using it day to day

- **To start it**: double-click `Start-Nsaabodee.bat`. This is much
  faster than the first-time install, since everything is already built.
- **To stop it**: double-click `Stop-Nsaabodee.bat`. Your data is never
  deleted by this — it's just switching everything off until next time.
- **If something seems wrong**: double-click `View-Logs.bat` to see
  what each part of the system is actually doing. Press `Ctrl+C` to
  stop watching (this does not stop the app itself).

## What to do next

- **Check it's actually working**: [`../docs/verify-local-setup.md`](../docs/verify-local-setup.md)
  walks through confirming the backend and frontend are both really running.
- **See what's actually in the app**: [`../docs/touring-the-interface.md`](../docs/touring-the-interface.md)
  walks through every demo login and what its dashboard shows.
- **Put it online for real use**: [`../docs/hosting-online.md`](../docs/hosting-online.md)
  covers deploying to Railway (backend) and Vercel (frontend), step by step.

## What these files actually do

| File | Purpose |
|---|---|
| `Install-Nsaabodee.bat` | Double-click entry point for first-time setup (and safe to re-run any time) |
| `install.ps1` | The real installation logic — checks/starts Docker, creates a `.env` file with a random secret key, builds and starts everything, seeds demo accounts, opens your browser |
| `Start-Nsaabodee.bat` / `start.ps1` | Fast daily start — assumes you've already run the installer once |
| `Stop-Nsaabodee.bat` | Shuts everything down without deleting any data |
| `View-Logs.bat` | Shows live logs from every service, for troubleshooting |

The `.bat` files exist because Windows doesn't run `.ps1` PowerShell
scripts on double-click by default (a security setting) — each `.bat`
file is a thin wrapper that hands off to the real PowerShell script with
the one-time bypass flag PowerShell's own documentation recommends for
exactly this situation.

## An honest note on how well-tested this actually is

Every one of these scripts was written carefully, using only long-
stable, extensively-documented PowerShell and Docker commands — but
this project was built entirely inside a Linux sandbox with **no
Windows machine and no PowerShell runtime available at all**. It was
not possible to actually run `Install-Nsaabodee.bat` end-to-end the way
the rest of this project's backend was verified (363 real, automated
tests running against a genuine local PostgreSQL and Redis, and a real
`npm run build` for the frontend — all of that is real, executed,
proven). This installer could only be reviewed carefully, not executed.

If something here doesn't work exactly as described on your machine,
please treat that as a real bug to report — not something that was
quietly assumed to be fine. The most likely places for something to
need adjusting, if anything does:

- The Docker Desktop installation path (`C:\Program Files\Docker\Docker\Docker Desktop.exe`)
  — correct for a standard install, but a custom install location would need updating.
- Exact PowerShell version differences between Windows PowerShell 5.1
  (built into Windows) and PowerShell 7+ (a separate, newer install) —
  every command used here should work on both, but this couldn't be
  confirmed on a real machine either way.

## If Docker Desktop isn't an option

Some older or locked-down Windows machines can't run Docker Desktop
(it needs WSL2 or Hyper-V, which some computers have disabled or can't
support). If that's the case for a specific community's computer, the
alternative is installing Python and Node.js directly and running the
backend and frontend natively — see the main project `README.md` for
that path. It's more manual, but doesn't need virtualization support.

## Troubleshooting

**"`'powershell' is not recognized as an internal or external
command"`"** — this happened on a real machine during testing: some
Windows installs have `C:\Windows\System32\WindowsPowerShell\v1.0\`
missing from their PATH (usually from other software editing PATH, or
a corrupted user PATH variable), which breaks the bare `powershell`
command everywhere, not just here. Fixed in these scripts by calling
the full, fixed install path
(`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`) instead
of relying on PATH — if you're on an older copy of this installer and
hit this, either re-download it, or run the fix yourself right now: open
the `windows-installer` folder in a PowerShell window and run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force`
followed by `.\install.ps1` directly.

**"Could not find Docker Desktop automatically"** — also found on a
real machine: Docker Desktop was genuinely installed and working (the
`docker` command and `docker compose` both checked out fine), but its
`Docker Desktop.exe` wasn't in either of the two standard install
folders this script originally checked. Fixed by checking several more
locations (including a per-user install under `%LOCALAPPDATA%`),
Windows' own "App Paths" registry key that installers commonly
register, and the Start Menu shortcut itself, resolved to whatever real
path it points at. If you hit this on an older copy of the installer,
the immediate fix is the same either way: press the Windows key, type
"Docker Desktop", click it, wait for the whale icon to say it's
running, then run the installer again.
