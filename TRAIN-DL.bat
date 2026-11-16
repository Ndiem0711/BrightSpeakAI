@echo off
cd /d "%~dp0"
echo === BRIGHTSPEAK V9 EXPERIMENTAL CNN KEYWORD TRAIN ===
echo WARNING: This is a keyword classifier, NOT a child pronunciation assessment model.
if not exist ".venv\Scripts\python.exe" (echo Run START-BRIGHTSPEAK.bat first. & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -r requirements-dl.txt
if errorlevel 1 (pause & exit /b 1)
if not exist "ml\data\mini_speech_commands" (
  ".venv\Scripts\python.exe" ml\train_keyword_spotter.py --download --max-per-class 800
  if errorlevel 1 (pause & exit /b 1)
)
".venv\Scripts\python.exe" ml\train_cnn_keyword_spotter.py --epochs 5 --max-per-class 250
if errorlevel 1 (pause & exit /b 1)
echo CNN metrics: ml\models\cnn_metrics.json
pause
