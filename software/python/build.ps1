# Build DKUScope Windows bundle (PyInstaller onedir)
#
# Usage (from repo root or this directory):
#   cd software/python
#   .\build.ps1
#
# Output: dist/DKUScope/DKUScope.exe + dependencies
#         dist/DKUScope.zip

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Installing build dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

Write-Host "==> Running PyInstaller..."
python -m PyInstaller DKUScope.spec --noconfirm --clean

$distDir = Join-Path $PSScriptRoot "dist\DKUScope"
$configDir = Join-Path $distDir "config"
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir | Out-Null
}
Copy-Item -Path "config\project_config.json" -Destination $configDir -Force

$zipPath = Join-Path $PSScriptRoot "dist\DKUScope.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path $distDir -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Build complete:"
Write-Host "  Folder: $distDir"
Write-Host "  Zip:    $zipPath"
Write-Host ""
Write-Host "Run: dist\DKUScope\DKUScope.exe"
