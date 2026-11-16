@echo off
cd /d "%~dp0"
echo ==== BRIGHTSPEAK AI V9 DIAGNOSTICS ====
if exist ".venv\Scripts\python.exe" (
  echo [Preflight] kiem tra source Python va import
  ".venv\Scripts\python.exe" scripts\preflight.py
  echo [Port] kiem tra cong local
  ".venv\Scripts\python.exe" scripts\select_local_port.py
  ".venv\Scripts\python.exe" -m pytest tests -q
) else (echo Chua co .venv. Hay chay START-BRIGHTSPEAK.bat.)
if exist "logs\server-error.log" type "logs\server-error.log"
if exist ".brightspeak.port" (echo Port cua V9: & type ".brightspeak.port")
pause
