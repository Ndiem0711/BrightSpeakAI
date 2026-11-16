@echo off
cd /d "%~dp0"
echo TRAIN ML - Google mini Speech Commands CC BY 4.0
echo Tai dataset ~180MB va huan luyen RandomForest. Khong phai mo hinh cham phat am.
if not exist ".venv\Scripts\python.exe" (echo Chay START-BRIGHTSPEAK.bat truoc! & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -r requirements-train.txt
if errorlevel 1 (pause & exit /b 1)
".venv\Scripts\python.exe" ml\train_keyword_spotter.py --download
if errorlevel 1 (pause & exit /b 1)
".venv\Scripts\python.exe" ml\prepare_audio_manifest.py
if errorlevel 1 (pause & exit /b 1)
echo Train complete; check ml\models\keyword_spotter_metrics.json
pause
