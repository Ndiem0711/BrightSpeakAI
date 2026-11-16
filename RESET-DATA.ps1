$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
& ".\STOP-BRIGHTSPEAK.ps1"
Remove-Item ".\runtime\brightspeak.db" -Force -ErrorAction SilentlyContinue
Write-Host "Demo database reset. Run START-BRIGHTSPEAK.bat again." -ForegroundColor Green
