$ErrorActionPreference = "Stop"
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $ProjectRoot

$staging = Join-Path $ProjectRoot "temp_onprem_staging"
if (Test-Path $staging) {
    Remove-Item -Recurse -Force $staging
}
New-Item -ItemType Directory -Force -Path $staging | Out-Null

Write-Host "Copying deployment configuration..."
Copy-Item -Recurse "deploy" (Join-Path $staging "deploy")

Write-Host "Copying backend application..."
New-Item -ItemType Directory -Force -Path (Join-Path $staging "backend") | Out-Null
Copy-Item -Recurse "backend\app" (Join-Path $staging "backend\app")
Copy-Item "backend\requirements.txt" (Join-Path $staging "backend\requirements.txt")
Copy-Item "backend\desktop_server.py" (Join-Path $staging "backend\desktop_server.py")

Write-Host "Copying frontend application source..."
Copy-Item -Recurse "app" (Join-Path $staging "app")
Copy-Item -Recurse "components" (Join-Path $staging "components")
Copy-Item -Recurse "lib" (Join-Path $staging "lib")
Copy-Item -Recurse "public" (Join-Path $staging "public")
Copy-Item "package.json" (Join-Path $staging "package.json")
if (Test-Path "package-lock.json") { Copy-Item "package-lock.json" (Join-Path $staging "package-lock.json") }
if (Test-Path "pnpm-lock.yaml") { Copy-Item "pnpm-lock.yaml" (Join-Path $staging "pnpm-lock.yaml") }
Copy-Item "next.config.mjs" (Join-Path $staging "next.config.mjs")
Copy-Item "tsconfig.json" (Join-Path $staging "tsconfig.json")

Write-Host "Copying documentation suite..."
$docs = @(
    "README.md",
    "USER_GUIDE.md",
    "ADMIN_GUIDE.md",
    "INSTALLATION_GUIDE.md",
    "ON_PREMISE_DEPLOYMENT.md",
    "SECURITY_AND_PRIVACY.md",
    "TROUBLESHOOTING.md",
    "RELEASE_NOTES.md",
    "TEST_REPORT.md"
)
foreach ($doc in $docs) {
    if (Test-Path $doc) {
        Copy-Item $doc (Join-Path $staging $doc)
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $staging "scripts") | Out-Null
Copy-Item "scripts\backup_restore.py" (Join-Path $staging "scripts\backup_restore.py")

$outDir = Join-Path $ProjectRoot "release\on-premise"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$zipPath = Join-Path $outDir "privora-on-premise-1.1.0.zip"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}

Write-Host "Creating zip archive: $zipPath..."
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath

Remove-Item -Recurse -Force $staging

$hash = Get-FileHash $zipPath -Algorithm SHA256
$size = (Get-Item $zipPath).Length

Write-Host "Successfully packaged On-Premise Edition!"
Write-Host "Archive: $zipPath"
Write-Host "Size: $size bytes"
Write-Host "SHA256: $($hash.Hash)"
