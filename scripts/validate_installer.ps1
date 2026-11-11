<#
.SYNOPSIS
    Validates that all prerequisites and files needed for the Inno Setup installer are present.
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Get-Item $ScriptDir).Parent.FullName

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Privora Inno Setup Configuration Validation             " -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan

$RequiredFiles = @(
    "dist\Privora.exe",
    "dist\privora-engine\privora-engine.exe",
    "dist\privora-engine\_internal\out\index.html",
    "public\favicon.ico",
    "README_DESKTOP.md",
    "installer\privora_setup.iss"
)

$AllPresent = $true
foreach ($rf in $RequiredFiles) {
    $full = Join-Path $ProjectRoot $rf
    if (Test-Path $full) {
        Write-Host "[OK] Required asset present: $rf" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Missing required asset: $rf" -ForegroundColor Red
        $AllPresent = $false
    }
}

# Check Inno Setup Compiler
$IsccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$IsccFound = $false
foreach ($c in $IsccCandidates) {
    if (Test-Path $c) {
        Write-Host "[OK] Inno Setup 6 Compiler found: $c" -ForegroundColor Green
        $IsccFound = $true
        break
    }
}

if (-not $IsccFound) {
    Write-Host "[BLOCKED] Inno Setup 6 Compiler (ISCC.exe) is not installed." -ForegroundColor Yellow
    Write-Host "          Single external prerequisite required to compile binary installer:" -ForegroundColor Gray
    Write-Host "          - Download Inno Setup 6 from: https://jrsoftware.org/isdl.php" -ForegroundColor Cyan
    Write-Host "          - Or install via: winget install JRSoftware.InnoSetup" -ForegroundColor Cyan
}

if ($AllPresent) {
    Write-Host ""
    Write-Host "[SUCCESS] Inno Setup configuration and payload assets are 100% valid." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[ERROR] Payload validation failed. Run 'scripts\build_desktop.ps1' first." -ForegroundColor Red
    exit 1
}
