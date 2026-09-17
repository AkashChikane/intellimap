#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

if [ ! -d backend/.venv ]; then
  "$PY" -m venv backend/.venv
fi

# shellcheck disable=SC1091
source backend/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

if [ ! -f data/IntelliMap_Architecture_Landscape.xlsx ]; then
  python backend/generate_sample.py
fi

mkdir -p backend/storage
echo "IntelliMap API → http://127.0.0.1:8000"
echo "In another terminal run ./start-frontend.sh"
cd backend
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
