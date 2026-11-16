@echo off
cd /d "%~dp0"
echo === BRIGHTSPEAK V9 DATASET ===
echo [1] Ban ke 125 cau hoc:
start "" "data\lesson_manifest.csv"
echo [2] Vi tri du lieu am thanh neu tai ve: ml\data\mini_speech_commands
echo [3] Ket qua train: ml\models\keyword_spotter_metrics.json
if exist "ml\DATASET_STATUS.json" type "ml\DATASET_STATUS.json"
pause
