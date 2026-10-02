# Nsaabodee Smart - daily start
# Use this after Install-Nsaabodee.bat has already been run once.
# This just starts the already-built containers (fast) and opens the browser.

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Test-DockerRunning {
    docker info *> $null
    return ($LASTEXITCODE -eq 0)
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
Write-Host "  Nsaabodee Smart - Starting" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green

if (-not (Test-DockerRunning)) {
    Write-Host "Docker Desktop isn't running. Please start it from the Start Menu" -ForegroundColor Yellow
    Write-Host "and wait for the whale icon to say 'running', then try again."
    Read-Host "Press Enter to close this window"
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

Write-Step "Starting Nsaabodee Smart..."
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Something went wrong. Run View-Logs.bat for more detail." -ForegroundColor Red
    Read-Host "Press Enter to close this window"
    exit 1
}

Write-Step "Waiting for the backend to be ready..."
if (-not (Wait-ForPort -portNumber 8000 -maxSeconds 120)) {
    Write-Host ""
    Write-Host "The backend didn't respond in time - it may still be starting. Check again shortly." -ForegroundColor Yellow
} else {
    Write-Host ""
}

Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "Nsaabodee Smart is running at http://localhost:3000" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close this window"
