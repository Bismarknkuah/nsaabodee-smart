# Nsaabodee Smart - Windows installer
#
# HONESTY NOTE (read this before relying on this script): this was
# written and reviewed carefully, using only long-stable, well-
# documented PowerShell/Docker commands - but it has never been run on
# an actual Windows machine. The sandbox this project was built in has
# no Windows environment and no PowerShell runtime at all (verified:
# even downloading PowerShell Core itself to test-parse this script was
# blocked by network restrictions), so this could not be tested the
# same rigorous way the rest of this project's backend was (363 real
# automated tests against a real Postgres and Redis). If something here
# doesn't work on your machine, that's a real gap to report, not
# something that was silently assumed away.
#
# What this actually does, in order:
#   1. Checks Docker Desktop is installed (guides you to install it if not)
#   2. Checks "docker compose" actually works (some old installs only have the deprecated "docker-compose")
#   3. Makes sure Docker is actually running (starts it if not)
#   4. Checks the ports this needs (3000, 8000, 5432, 6379) aren't taken by something else
#   5. Creates a .env file at the repo root with a random secret key
#      and database password, if one doesn't already exist
#   6. Builds and starts every service via docker compose
#   7. Waits for the backend to actually respond
#   8. Seeds demo accounts (safe to run more than once)
#   9. Opens the app in your browser
#
# Safe to re-run any time - every step here either checks first or is
# naturally safe to repeat (Docker, and the seed_demo_data command
# itself, are both idempotent).

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Success($msg) {
    Write-Host $msg -ForegroundColor Green
}

function Write-Problem($msg) {
    Write-Host $msg -ForegroundColor Red
}

function Test-CommandExists($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Test-DockerRunning {
    docker info *> $null
    return ($LASTEXITCODE -eq 0)
}

function Find-DockerDesktopExe {
    # Method 1: the usual install locations - covers the vast majority
    # of installs, including a per-user (not just per-machine) install
    # under LOCALAPPDATA, which some Docker Desktop versions use.
    $candidates = @(
        "$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "${Env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
        "$Env:LOCALAPPDATA\Docker\Docker\Docker Desktop.exe",
        "$Env:LOCALAPPDATA\Programs\Docker\Docker\Docker Desktop.exe"
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($found) { return $found }

    # Method 2: Windows' own "App Paths" registry key - installers
    # commonly register their .exe here specifically so Windows itself
    # (and tools like this one) can find it without knowing the exact
    # install folder in advance.
    try {
        $regKeys = @(
            "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Docker Desktop.exe",
            "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Docker Desktop.exe"
        )
        foreach ($key in $regKeys) {
            if (Test-Path $key) {
                $regValue = (Get-Item $key -ErrorAction SilentlyContinue).GetValue("")
                if ($regValue -and (Test-Path $regValue)) { return $regValue }
            }
        }
    } catch {
        # Best-effort - fall through to the next method rather than stop here.
    }

    # Method 3: the Start Menu shortcut Docker Desktop's own installer
    # creates, resolved to whatever real .exe path it actually points at.
    try {
        $shortcutPaths = @(
            "$Env:ProgramData\Microsoft\Windows\Start Menu\Programs\Docker Desktop.lnk",
            "$Env:APPDATA\Microsoft\Windows\Start Menu\Programs\Docker Desktop.lnk"
        )
        foreach ($shortcut in $shortcutPaths) {
            if (Test-Path $shortcut) {
                $shell = New-Object -ComObject WScript.Shell
                $target = $shell.CreateShortcut($shortcut).TargetPath
                if ($target -and (Test-Path $target)) { return $target }
            }
        }
    } catch {
        # Best-effort - if even this fails, Find-DockerDesktopExe just returns nothing below.
    }

    return $null
}

function Test-PortFree($portNumber) {
    $inUse = Test-NetConnection -ComputerName "localhost" -Port $portNumber `
        -WarningAction SilentlyContinue -InformationLevel Quiet
    return (-not $inUse)
}

function Wait-ForPort($portNumber, $maxSeconds) {
    $elapsed = 0
    while ($elapsed -lt $maxSeconds) {
        $reachable = Test-NetConnection -ComputerName "localhost" -Port $portNumber `
            -WarningAction SilentlyContinue -InformationLevel Quiet
        if ($reachable) { return $true }
        Start-Sleep -Seconds 3
        $elapsed += 3
        Write-Host "." -NoNewline
    }
    return $false
}

Write-Host "================================================================" -ForegroundColor Green
Write-Host "  Nsaabodee Smart - Setup" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green

# --- 1. Docker Desktop installed? ---
Write-Step "Checking for Docker Desktop..."
if (-not (Test-CommandExists "docker")) {
    Write-Problem "Docker Desktop was not found on this computer."
    Write-Host ""
    Write-Host "Opening the download page in your browser. Please install Docker Desktop,"
    Write-Host "restart your computer if it asks you to, then run this installer again."
    Start-Process "https://www.docker.com/products/docker-desktop/"
    Read-Host "Press Enter to close this window"
    exit 1
}
Write-Success "Docker Desktop is installed."

# --- 1b. The modern "docker compose" (v2, built into Docker Desktop) actually works ---
# A handful of very old Docker Desktop installs only have the separate,
# now-deprecated "docker-compose" (v1, hyphenated) binary, which does
# NOT understand the "docker compose" (space, v2) syntax this whole
# installer relies on - check this explicitly rather than let it fail
# confusingly several steps later.
Write-Step "Checking Docker Compose..."
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Problem "This computer's Docker Desktop doesn't recognize 'docker compose'."
    Write-Host "This usually means Docker Desktop needs updating - open Docker Desktop,"
    Write-Host "check Settings for an available update, install it, then run this installer again."
    Read-Host "Press Enter to close this window"
    exit 1
}
Write-Success "Docker Compose is working."

# --- 2. Docker actually running? ---
Write-Step "Checking Docker is running..."
if (-not (Test-DockerRunning)) {
    Write-Host "Docker Desktop isn't running yet - starting it now. This can take a minute or two the first time." -ForegroundColor Yellow

    $dockerExe = Find-DockerDesktopExe

    if ($null -eq $dockerExe) {
        Write-Problem "Could not find Docker Desktop automatically."
        Write-Host "Please start Docker Desktop yourself - press the Windows key, type"
        Write-Host "'Docker Desktop', and click it. Wait for the whale icon in your system"
        Write-Host "tray to say it's running, then run this installer again."
        Read-Host "Press Enter to close this window"
        exit 1
    }

    Start-Process $dockerExe
    Write-Host "Waiting for Docker to finish starting..."
    $ready = $false
    $elapsed = 0
    while ($elapsed -lt 180) {
        if (Test-DockerRunning) { $ready = $true; break }
        Start-Sleep -Seconds 3
        $elapsed += 3
        Write-Host "." -NoNewline
    }
    Write-Host ""
    if (-not $ready) {
        Write-Problem "Docker Desktop did not finish starting in time."
        Write-Host "Common causes if this keeps happening:"
        Write-Host " - This is the very first time Docker Desktop has ever been opened, and it's"
        Write-Host "   waiting on a one-time setup step (accepting a license, a Windows restart,"
        Write-Host "   or installing the WSL2 Linux kernel update). Open Docker Desktop directly"
        Write-Host "   from the Start Menu and follow whatever it asks for on screen."
        Write-Host " - WSL2 isn't set up. If Docker Desktop itself shows a WSL2-related error,"
        Write-Host "   run 'wsl --install' in a new PowerShell window (as Administrator), restart"
        Write-Host "   your computer, then try again."
        Read-Host "Press Enter to close this window"
        exit 1
    }
}
Write-Success "Docker is running."

# --- 2b. Are the ports this needs already taken by something else? ---
Write-Step "Checking that ports 3000, 8000, 5432, and 6379 are free..."
$neededPorts = @{ 3000 = "frontend"; 8000 = "backend"; 5432 = "database"; 6379 = "redis" }
$conflicts = @()
foreach ($port in $neededPorts.Keys) {
    if (-not (Test-PortFree $port)) { $conflicts += "$port ($($neededPorts[$port]))" }
}
if ($conflicts.Count -gt 0) {
    Write-Host "Something is already using: $($conflicts -join ', ')" -ForegroundColor Yellow
    Write-Host "If that's an earlier, already-running copy of Nsaabodee Smart, this is fine -"
    Write-Host "docker compose will just reuse it. If it's a DIFFERENT program using that port,"
    Write-Host "close that program first, or this step may fail below."
} else {
    Write-Success "All required ports are free."
}

# --- 3. Move to the repository root (this script lives in windows-installer\, one level below the repo root) ---
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

# --- 4. Configuration ---
# IMPORTANT: this creates a .env file at the REPO ROOT, next to
# docker-compose.yml - that's the one Docker Compose itself actually
# reads for ${VARIABLE} substitution. backend\.env and frontend\.env
# (used for running the app WITHOUT Docker) are a completely separate
# mechanism that docker-compose never looks at, so this deliberately
# does not touch them.
Write-Step "Setting up configuration..."
if (-not (Test-Path ".env")) {
    function New-RandomSecret {
        $chars = (48..57) + (65..90) + (97..122)
        -join (1..40 | ForEach-Object { [char]($chars | Get-Random) })
    }
    $secretKey = New-RandomSecret
    $dbPassword = New-RandomSecret
    @"
DJANGO_SECRET_KEY=$secretKey
POSTGRES_PASSWORD=$dbPassword
PUBLIC_API_URL=http://localhost:8000
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend
"@ | Set-Content -Path ".env" -Encoding UTF8
    Write-Success "Created a .env file with a randomly generated secret key and database password."
} else {
    Write-Host ".env already exists - leaving your settings as they are."
}

# --- 5. Build and start everything ---
Write-Step "Building and starting Nsaabodee Smart (this can take several minutes the first time)..."
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Problem "Something went wrong while starting the containers. Here's what Docker says:"
    Write-Host ""
    docker compose logs --tail=40
    Write-Host ""
    Write-Problem "Scroll up to see the actual error above, or run View-Logs.bat any time for the full picture."
    Read-Host "Press Enter to close this window"
    exit 1
}

# "docker compose up -d" can report success even if a container starts
# and then immediately crashes (a bad .env value, a port grabbed by
# something else after all, etc.) - show the actual container status
# rather than trust the exit code alone.
Start-Sleep -Seconds 2
Write-Host ""
docker compose ps

# --- 6. Wait for the backend to actually respond ---
Write-Step "Waiting for the backend to be ready..."
if (-not (Wait-ForPort -portNumber 8000 -maxSeconds 180)) {
    Write-Host ""
    Write-Problem "The backend didn't respond within 3 minutes. Here's what its log shows:"
    Write-Host ""
    docker compose logs --tail=40 backend
    Write-Host ""
    Write-Problem "Scroll up to see the actual error above, or run View-Logs.bat for the full picture."
    Read-Host "Press Enter to close this window"
    exit 1
}
Write-Host ""
Write-Success "Backend is up."

# --- 7. Seed demo accounts (safe to run every time) ---
Write-Step "Setting up demo accounts for every role..."
docker compose exec -T backend python manage.py seed_demo_data

# --- 8. Open the browser ---
Write-Step "Opening Nsaabodee Smart in your browser..."
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Success "  All done! Nsaabodee Smart is running at http://localhost:3000"
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Demo login details were printed above by 'seed_demo_data' - scroll up to see them."
Write-Host "(The password for every demo account is: demo-password-not-for-real-use)"
Write-Host ""
Write-Host "To stop everything later:      Stop-Nsaabodee.bat"
Write-Host "To start it again another day: Start-Nsaabodee.bat"
Write-Host ""
Read-Host "Press Enter to close this window"
