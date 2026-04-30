param(
    [string]$Python = "python",
    [string]$VenvDir = "venv",
    [switch]$Dev
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path $VenvDir)) {
    & $Python -m venv $VenvDir
}

$venvPython = Join-Path $VenvDir "Scripts/python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Python executable not found in venv: $venvPython"
}

& $venvPython -m pip install --upgrade pip

if ($Dev) {
    & $venvPython -m pip install "-e" ".[dev]"
}
else {
    & $venvPython -m pip install "-e" "."
}

# Playwright package is installed from dependencies, browsers are installed separately.
& $venvPython -m playwright install chromium

Write-Host "Bootstrap complete. Venv path: $VenvDir"
