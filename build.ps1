param(
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path "VERSION")) {
    throw "File VERSION non trovato nella root del progetto."
}

$version = (Get-Content -Path "VERSION" -Raw).Trim()
if (-not $version) {
    throw "Il file VERSION e vuoto."
}

$appName = "APP-Timesheet"
$exeName = "$appName-v$version"

if (-not $NoClean) {
    if (Test-Path "dist") {
        Remove-Item "dist" -Recurse -Force
    }
    if (Test-Path "build") {
        Remove-Item "build" -Recurse -Force
    }
    if (Test-Path "$appName.spec") {
        Remove-Item "$appName.spec" -Force
    }
}

python -m PyInstaller --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller non trovato: installazione in corso..."
    python -m pip install pyinstaller
}

$pyInstallerArgs = @(
    "--noconfirm"
    "--clean"
    "--windowed"
    "--onedir"
    "--name", $exeName
    "--add-data", "VERSION;."
    "main.py"
)

python -m PyInstaller @pyInstallerArgs

Write-Host ""
Write-Host "Build completata."
Write-Host "Eseguibile: dist\$exeName\$exeName.exe"
