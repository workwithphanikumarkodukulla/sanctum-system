#!/usr/bin/env bash
# Sanctum Unified Runner
# Starts both Python Backend (5050) and Next.js Frontend (3000)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================="
echo "  SANCTUM SOVEREIGN RUNTIME"
echo "  Backend:  http://127.0.0.1:5050"
echo "  Frontend: http://127.0.0.1:3000"
echo "================================================="

cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $(jobs -p) 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 1. Start Python Backend
echo "[1/2] Starting Python Flask backend on port 5050..."
cd "$ROOT_DIR"
if [ -f "./venv/bin/python" ]; then
    ./venv/bin/python app.py &
elif [ -f "./sanctum-backend/venv/bin/python" ]; then
    ./sanctum-backend/venv/bin/python app.py &
else
    python3 app.py &
fi
BACKEND_PID=$!

# 2. Start Next.js Frontend
echo "[2/2] Starting Next.js frontend on port 3000..."
cd "$ROOT_DIR/sanctum-studio"
npm run dev &
FRONTEND_PID=$!

echo "Both services running. Press Ctrl+C to stop."
wait
