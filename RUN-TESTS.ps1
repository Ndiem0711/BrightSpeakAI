$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Run START-BRIGHTSPEAK.bat once first to create the environment." -ForegroundColor Yellow
    exit 1
}
& ".\.venv\Scripts\python.exe" -m pytest -q
