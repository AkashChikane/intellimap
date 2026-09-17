@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

if not exist backend\.venv (
  %PY% -m venv backend\.venv
)

call backend\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

if not exist data\IntelliMap_Architecture_Landscape.xlsx (
  python backend\generate_sample.py
)

if not exist backend\storage mkdir backend\storage
echo IntelliMap API - http://127.0.0.1:8000
echo In another terminal run start-frontend.bat
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
