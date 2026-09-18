@echo off
setlocal
cd /d "%~dp0"

echo IntelliMap screenshot capture
echo Requires: start.bat (API :8000) and start-frontend.bat (UI :3000) already running.
echo.

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js is not on PATH. Install Node LTS from https://nodejs.org/ then open a new Command Prompt.
  exit /b 1
)

cd scripts
if not exist node_modules (
  echo Installing Playwright in scripts\ ...
  call npm install
)
echo Installing Chromium for Playwright if needed...
call npx playwright install chromium
cd ..

set BASE_URL=http://localhost:3000
node scripts\capture-screenshots.mjs
if errorlevel 1 (
  echo Capture failed. Confirm the UI is at http://localhost:3000 and the API pill says ready.
  exit /b 1
)

echo.
echo PNGs are in docs\screenshots\
echo Markdown to paste into README.md: docs\screenshots\README-SNIPPET.md
echo This script does not edit README.md.
endlocal
