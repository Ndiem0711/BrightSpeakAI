@echo off
setlocal
cd /d "%~dp0"
title BrightSpeakAI
 echo BrightSpeakAI - Render Free demo setup
 echo.
 echo 1. Create your own NEW GitHub repository for BrightSpeakAI.
 echo 2. Push only source, no .env, GEMINI_KEY.txt or student data.
 echo 3. Open Render - New - Blueprint and select that GitHub repo.
 echo 4. Set GEMINI_API_KEY, RESEND_API_KEY, MAIL_FROM, PUBLIC_BASE_URL,
 echo    BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD in Render.
 echo 5. Confirm resources use plan Free before applying.
 echo 6. After deploy, check /api/v1/system/health for version 13.0.0.
 echo.
 echo NOTE: Live can have wake-up delays; free DB expires after 30 days.
 echo Cloud demo is not for real child profiles or recordings.
 echo.
start "" "https://dashboard.render.com/"
start "" "%~dp0HUONG_DAN_V13.txt"
pause
