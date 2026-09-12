#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

echo "==> 后端 API :8000"
mkdir -p "$ROOT/backend/data"
cd "$ROOT/backend"
python3 -m app.seed
if ! curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
  sleep 2
fi

echo "==> 用户端 H5（小程序形态）:5173"
cd "$ROOT/web"
[ -d node_modules ] || npm install
npm run dev &

echo "==> 运营后台 :5174"
cd "$ROOT/admin"
[ -d node_modules ] || npm install
npm run dev &

wait
