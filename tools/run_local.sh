#!/bin/bash

echo "Starting backend..."
# Run backend in background and log output
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &

BACKEND_PID=$!

echo "Backend started with PID $BACKEND_PID"

echo "Starting frontend..."
streamlit run frontend/streamlit_app/app.py --server.port 8501

echo "Shutting down backend..."
kill $BACKEND_PID
