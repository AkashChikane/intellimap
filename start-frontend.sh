#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install
fi
export PORT=3000
exec npm start
