@echo off
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Install Node.js 24 to run the browser preview.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:1440 in your browser.
node scripts/preview.mjs
pause
