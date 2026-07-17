$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildVenv = Join-Path $ProjectRoot ".build-venv"
$Python = Join-Path $BuildVenv "Scripts\python.exe"
$PyInstaller = Join-Path $BuildVenv "Scripts\pyinstaller.exe"
$DistPath = Join-Path $ProjectRoot "dist\windows"
$WorkPath = Join-Path $ProjectRoot "build\pyinstaller-windows"
$SpecPath = Join-Path $ProjectRoot "build"

Set-Location $ProjectRoot

if (-not (Test-Path $Python)) {
    py -3 -m venv $BuildVenv
}

& $Python -m pip install --upgrade pip setuptools wheel
& $Python -m pip install -e ".[windows,usb]" pyinstaller

& $PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name VitaGamepadDashboard `
    --hidden-import vitapad.backends.windows `
    --hidden-import vitapad.backends.debug `
    --hidden-import usb.backend.libusb1 `
    --collect-all vgamepad `
    --collect-all libusb_package `
    --paths $ProjectRoot `
    --distpath $DistPath `
    --workpath $WorkPath `
    --specpath $SpecPath `
    (Join-Path $ProjectRoot "vitapad\gui.py")

$Output = Join-Path $DistPath "VitaGamepadDashboard.exe"
if (-not (Test-Path $Output)) {
    throw "Build finished without producing $Output"
}

Write-Host ""
Write-Host "Windows package created:" -ForegroundColor Green
Write-Host $Output
