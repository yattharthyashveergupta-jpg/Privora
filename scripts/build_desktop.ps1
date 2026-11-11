<#
.SYNOPSIS
    Builds the Privora Windows Desktop release bundle and optional installer.
.DESCRIPTION
    1. Compiles Next.js into a static export ('out/').
    2. Builds the unified Python backend engine into 'dist/privora-engine/'.
    3. Builds the native launcher into 'dist/Privora.exe'.
    4. Compiles the Inno Setup installer if ISCC.exe is present on system.
#>

[CmdletBinding()]
param (
    [switch]$SkipFrontendBuild,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Get-Item $ScriptDir).Parent.FullName

Set-Location $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Privora Desktop Build Pipeline                          " -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host ""

# Step 1: Static Frontend Build
if ($SkipFrontendBuild) {
    Write-Host "[1/4] Skipping Next.js static export (using existing out/)..." -ForegroundColor DarkGray
} else {
    Write-Host "[1/4] Building Next.js static export..." -ForegroundColor Yellow
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Next.js static export build failed."
        exit $LASTEXITCODE
    }
    Write-Host "[OK] Static export generated successfully in 'out/'" -ForegroundColor Green
}

# Step 2: PyInstaller Engine Build
Write-Host ""
Write-Host "[2/4] Compiling Privora backend engine via PyInstaller..." -ForegroundColor Yellow
python -m PyInstaller --clean --noconfirm backend/privora_engine.spec
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller backend compilation failed."
    exit $LASTEXITCODE
}
Write-Host "[OK] Backend engine compiled to 'dist/privora-engine/'" -ForegroundColor Green

# Step 3: PyInstaller Launcher Build
Write-Host ""
Write-Host "[3/4] Compiling Privora native launcher executable..." -ForegroundColor Yellow
python -m PyInstaller --clean --noconfirm --onefile --noconsole --name Privora privora_launcher.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller launcher compilation failed."
    exit $LASTEXITCODE
}
Write-Host "[OK] Launcher compiled to 'dist/Privora.exe'" -ForegroundColor Green

# Step 4: Optional Inno Setup Compiler
Write-Host ""
Write-Host "[4/4] Checking Inno Setup 6 compiler..." -ForegroundColor Yellow
$IsccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$IsccPath = $null
foreach ($c in $IsccCandidates) {
    if (Test-Path $c) {
        $IsccPath = $c
        break
    }
}

if ($IsccPath -and (-not $SkipInstaller)) {
    Write-Host "[*] Compiling installer using $IsccPath..." -ForegroundColor Cyan
    & $IsccPath "installer\privora_setup.iss"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Installer created in 'dist-installer/'" -ForegroundColor Green
    } else {
        Write-Warning "Inno Setup compilation returned non-zero code: $LASTEXITCODE"
    }
} else {
    if (-not $IsccPath) {
        Write-Host "[i] Inno Setup compiler (ISCC.exe) not installed on this host." -ForegroundColor DarkYellow
        Write-Host "    The installer script 'installer\privora_setup.iss' is ready." -ForegroundColor Gray
        Write-Host "    Install Inno Setup 6 (https://jrsoftware.org/isdl.php) to compile Privora-Setup-1.1.0.exe." -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Privora Desktop Build Complete!                         " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Outputs:" -ForegroundColor White
Write-Host "  - Launcher:   $ProjectRoot\dist\Privora.exe" -ForegroundColor Gray
Write-Host "  - Engine Dir: $ProjectRoot\dist\privora-engine\" -ForegroundColor Gray
Write-Host "  - Static UI:  $ProjectRoot\dist\privora-engine\_internal\out\" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Green
