@echo off
setlocal
cd /d "%~dp0frontend"
if not exist node_modules (
  npm install
)
set PORT=3000
npm start
