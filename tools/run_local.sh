#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT  # Cleanup on exit

echo "Starting backend..."
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID $BACKEND_PID"

# Wait for backend to be ready
sleep 2
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend failed to start. Check backend.log:"
    cat backend.log
    exit 1
fi

echo "Starting frontend..."
streamlit run frontend/streamlit_app/app.py --server.port 8501