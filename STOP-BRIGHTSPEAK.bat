@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0STOP-BRIGHTSPEAK.ps1"
pause
