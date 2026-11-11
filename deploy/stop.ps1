# ==============================================================================
# Privora On-Premise Enterprise Shutdown Script (Windows Server / PowerShell)
# ==============================================================================
[CmdletBinding()]
param ()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Privora On-Premise Enterprise — Stopping Services       " -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan

$dockerCmd = Get-Command "docker" -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host "[-] ERROR: Docker is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

docker compose down
Write-Host "[OK] All Privora enterprise services stopped cleanly." -ForegroundColor Green
Write-Host "     Persistent database and documents preserved in docker volumes." -ForegroundColor Gray
