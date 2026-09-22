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
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
    lsof -ti:5050 | xargs kill -9 2>/dev/null || true
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 0. Clean any orphaned processes on port 5050 and 3000
echo "Ensuring ports 5050 and 3000 are free..."
lsof -ti:5050 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
sleep 1

# 1. Start Python Backend
echo "[1/2] Starting Python Flask backend on port 5050..."
cd "$ROOT_DIR/sanctum-backend"
./venv/bin/python app.py &
BACKEND_PID=$!

# 2. Start Next.js Frontend
echo "[2/2] Starting Next.js frontend on port 3000..."
cd "$ROOT_DIR/sanctum-studio"
npm run dev &
FRONTEND_PID=$!

echo "Both services running. Press Ctrl+C to stop."
wait
