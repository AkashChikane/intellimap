@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Use the Python already on PATH. Do not create or activate a venv —
rem Windows Store stubs and half-created backend\.venv folders break pip.
set "PY="
set "PYARGS="

python -c "import sys" >nul 2>&1
if not errorlevel 1 (
  set "PY=python"
  goto :got_py
)

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
  set "PY=py"
  set "PYARGS=-3"
  goto :got_py
)

echo.
echo Python was not found on PATH.
echo Install Python 3.11 or 3.12 from https://www.python.org/downloads/windows/
echo Tick "Add python.exe to PATH", then open a NEW Command Prompt.
echo Do not use only the Microsoft Store Python stub.
exit /b 1

:got_py
echo Using:
%PY% %PYARGS% --version
%PY% %PYARGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo IntelliMap needs Python 3.11 or newer on PATH.
  exit /b 1
)

if exist backend\.venv (
  echo Note: ignoring backend\.venv — start.bat uses PATH Python.
  echo To remove the leftover folder:  rmdir /s /q backend\.venv
)

echo.
echo Installing backend packages into that Python ^(no venv^)...
%PY% %PYARGS% -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo pip is missing or broken. Try:  %PY% %PYARGS% -m ensurepip --upgrade
  echo Then re-run start.bat
  exit /b 1
)

rem Prefer wheels so pip does not try to compile Rust ^(watchfiles / pydantic-core^)
rem which shows up as "Encountered error while generating package metadata".
%PY% %PYARGS% -m pip install --prefer-binary --only-binary=:all: -r backend\requirements.txt
if errorlevel 1 (
  echo Wheel-only install failed, retrying with source allowed...
  %PY% %PYARGS% -m pip install --prefer-binary -r backend\requirements.txt
)
if errorlevel 1 (
  echo.
  echo pip install failed. If you saw "error while generating package metadata":
  echo   1. Install Python 3.11 or 3.12 from python.org ^(not Microsoft Store^)
  echo   2. Tick Add python.exe to PATH, open a NEW Command Prompt
  echo   3. rmdir /s /q backend\.venv
  echo   4. Run start.bat again
  echo Confirm with:  python --version
  exit /b 1
)

if not exist data\IntelliMap_Architecture_Landscape.xlsx (
  %PY% %PYARGS% backend\generate_sample.py
  if errorlevel 1 exit /b 1
)

if not exist backend\storage mkdir backend\storage
echo IntelliMap API - http://127.0.0.1:8000
echo In another terminal run start-frontend.bat
cd backend
%PY% %PYARGS% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
