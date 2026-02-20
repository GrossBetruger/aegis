#!/bin/bash
set -e

# Pentagon Pizza Meter / StrikeRadar - Run Commands
# Usage:
#   ./run.sh update    - Run the backend data updater (updates npoint.io)
#   ./run.sh serve     - Serve the frontend locally
#   ./run.sh all       - Run update once, then serve frontend
#   ./run.sh watch     - Run update every 30 min + serve frontend
#   ./run.sh kill      - Kill any running background server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server.pid"

case "${1:-help}" in
    update)
        echo "🍕 Running Pentagon Pizza Meter data update..."
        uv run python update_data.py
        echo "✅ Data updated to npoint.io"
        ;;
    
    serve)
        echo "🌐 Serving frontend at http://localhost:8000"
        echo "   Press Ctrl+C to stop"
        cd frontend && uv run python -m http.server 8000
        ;;
    
    all)
        echo "🍕 Running data update first..."
        uv run python update_data.py
        echo "✅ Data updated"
        echo ""
        echo "🌐 Serving frontend at http://localhost:8000"
        echo "   Press Ctrl+C to stop"
        cd frontend && uv run python -m http.server 8000
        ;;
    
    watch)
        echo "👀 Starting watch mode..."
        echo "   - Frontend: http://localhost:8000"
        echo "   - Data updates every 30 minutes"
        echo "   Press Ctrl+C to stop"
        
        # Start frontend server in background
        (cd frontend && uv run python -m http.server 8000) &
        SERVER_PID=$!
        
        # Save PID to file for kill command
        echo $SERVER_PID > "$PID_FILE"
        
        # Trap to clean up on exit
        cleanup() {
            kill $SERVER_PID 2>/dev/null
            rm -f "$PID_FILE"
            exit
        }
        trap cleanup INT TERM
        
        # Run update loop
        while true; do
            echo ""
            echo "🍕 [$(date '+%H:%M:%S')] Running data update..."
            uv run python update_data.py
            echo "✅ [$(date '+%H:%M:%S')] Update complete. Next update in 30 minutes."
            sleep 1800
        done
        ;;
    
    kill)
        lsof -ti:8000 | xargs kill 2>/dev/null && echo "✅ Server killed" || echo "No server running"
        rm -f "$PID_FILE"
        ;;
    
    help|*)
        echo "Pentagon Pizza Meter / StrikeRadar"
        echo ""
        echo "Usage: ./run.sh <command>"
        echo ""
        echo "Commands:"
        echo "  update  - Run the backend data updater (updates npoint.io)"
        echo "  serve   - Serve the frontend locally at http://localhost:8000"
        echo "  all     - Run update once, then serve frontend"
        echo "  watch   - Run update every 30 min + serve frontend"
        echo "  kill    - Kill any running background server on port 8000"
        echo "  help    - Show this help message"
        echo ""
        echo "First time setup:"
        echo "  uv sync    - Install dependencies"
        ;;
esac
