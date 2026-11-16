@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START-BRIGHTSPEAK.ps1"
if errorlevel 1 (
  echo.
  echo LOI KHI CHAY. KIEM TRA THONG BAO PHIA TREN.
  pause
)
