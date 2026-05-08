#!/bin/bash
# API Restart Script

# Kill existing API process
pkill -f "uvicorn.*8001" 2>/dev/null || true

# Wait for process to die
sleep 2

# Start API in background
cd /home/ai/ai-visual-lab/dataset-prep/02-duplicate
nohup ./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8001 > /tmp/duplicate-api.log 2>&1 &

# Wait a bit and check if started
sleep 2

# Verify API is running
if pgrep -f "uvicorn.*8001" > /dev/null; then
    echo "API_RESTARTED"
    exit 0
else
    echo "API_FAILED"
    exit 1
fi
