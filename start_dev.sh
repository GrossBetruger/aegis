#!/bin/bash

# Start local development server for the frontend

PORT=${1:-8000}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "Starting development server..."
echo "Serving frontend at: http://localhost:$PORT"
echo "Press Ctrl+C to stop"
echo ""

cd "$FRONTEND_DIR" && python3 -m http.server "$PORT"
