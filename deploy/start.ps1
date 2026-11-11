# ==============================================================================
# Privora On-Premise Enterprise Startup Script (Windows Server / PowerShell)
# ==============================================================================
[CmdletBinding()]
param ()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Privora On-Premise Enterprise — Starting Services       " -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".env.server")) {
    if (Test-Path ".env.server.example") {
        Write-Host "[!] .env.server not found. Initializing from .env.server.example..." -ForegroundColor Yellow
        Copy-Item ".env.server.example" ".env.server"
        Write-Host "[*] Created .env.server. Please review secrets before production use." -ForegroundColor Gray
    } else {
        Write-Error "Missing .env.server configuration file."
        exit 1
    }
}

$dockerCmd = Get-Command "docker" -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host "[-] ERROR: Docker is not installed or not in PATH." -ForegroundColor Red
    Write-Host "    Install Docker Desktop for Windows or Docker Engine on Linux VM." -ForegroundColor DarkYellow
    exit 1
}

Write-Host "[1/3] Building enterprise application container..." -ForegroundColor Yellow
docker compose build privora-app

Write-Host "[2/3] Launching air-gapped stack (Ollama + App + Nginx)..." -ForegroundColor Yellow
docker compose up -d

Write-Host "[3/3] Checking container status..." -ForegroundColor Yellow
Start-Sleep -Seconds 3
docker compose ps

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Privora Enterprise is active!                           " -ForegroundColor Green
Write-Host "  Web Interface: http://localhost                         " -ForegroundColor Cyan
Write-Host "  Direct Backend: http://localhost:8000/api/health        " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
