<#
.SYNOPSIS
    Starts Privora -- Private Document Intelligence in native Windows desktop mode.
.DESCRIPTION
    Launches Privora using Microsoft Edge App Mode without requiring separate frontend
    development servers (Node.js/Next.js). Supervises the backend process and terminates
    cleanly when the window is closed.
#>

[CmdletBinding()]
param (
    [switch]$NoBrowser,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Privora -- Private Document Intelligence (Desktop Mode)  " -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python environment
$PythonCmd = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonCmd) {
    $PythonCmd = (Get-Command py -ErrorAction SilentlyContinue).Source
    if (-not $PythonCmd) {
        Write-Error "Python was not found in PATH. Please install Python 3.10+ or build the standalone executable."
        exit 1
    }
}

# Verify static build exists
$OutDir = Join-Path $ScriptDir "out"
if (-not (Test-Path (Join-Path $OutDir "index.html"))) {
    Write-Host "[!] Static export not found in '$OutDir'. Building frontend first..." -ForegroundColor Yellow
    Push-Location $ScriptDir
    try {
        npm run build
    } finally {
        Pop-Location
    }
}

# Check Edge browser
$EdgePaths = @(
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe"
)
$FoundEdge = $false
foreach ($p in $EdgePaths) {
    if (Test-Path $p) {
        $FoundEdge = $true
        Write-Host "[OK] Microsoft Edge detected: $p" -ForegroundColor Green
        break
    }
}
if (-not $FoundEdge) {
    Write-Host "[i] Microsoft Edge not found in standard paths; will fallback to default browser." -ForegroundColor DarkYellow
}

Write-Host "[*] Launching Privora supervisor..." -ForegroundColor Cyan
Write-Host "    Data Directory: $env:LOCALAPPDATA\Privora\data" -ForegroundColor Gray
Write-Host "    Logs:           $env:LOCALAPPDATA\Privora\logs\launcher.log" -ForegroundColor Gray
Write-Host ""

$LauncherScript = Join-Path $ScriptDir "privora_launcher.py"

# Execute launcher
& $PythonCmd $LauncherScript

Write-Host ""
Write-Host "[OK] Privora session closed cleanly." -ForegroundColor Green
