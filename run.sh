#!/bin/bash
set -e

# Pentagon Pizza Meter / StrikeRadar - Run Commands
# Usage:
#   ./cmd.sh update    - Run the backend data updater (updates npoint.io)
#   ./cmd.sh serve     - Serve the frontend locally
#   ./cmd.sh all       - Run update once, then serve frontend
#   ./cmd.sh watch     - Run update every 30 min + serve frontend

case "${1:-help}" in
    update)
        echo "🍕 Running Pentagon Pizza Meter data update..."
        uv run python pentagon_pizza.py
        echo "✅ Data updated to npoint.io"
        ;;
    
    serve)
        echo "🌐 Serving frontend at http://localhost:8000"
        echo "   Press Ctrl+C to stop"
        cd frontend && uv run python -m http.server 8000
        ;;
    
    all)
        echo "🍕 Running data update first..."
        uv run python pentagon_pizza.py
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
        
        # Trap to clean up on exit
        trap "kill $SERVER_PID 2>/dev/null; exit" INT TERM
        
        # Run update loop
        while true; do
            echo ""
            echo "🍕 [$(date '+%H:%M:%S')] Running data update..."
            uv run python pentagon_pizza.py
            echo "✅ [$(date '+%H:%M:%S')] Update complete. Next update in 30 minutes."
            sleep 1800
        done
        ;;
    
    help|*)
        echo "Pentagon Pizza Meter / StrikeRadar"
        echo ""
        echo "Usage: ./cmd.sh <command>"
        echo ""
        echo "Commands:"
        echo "  update  - Run the backend data updater (updates npoint.io)"
        echo "  serve   - Serve the frontend locally at http://localhost:8000"
        echo "  all     - Run update once, then serve frontend"
        echo "  watch   - Run update every 30 min + serve frontend"
        echo "  help    - Show this help message"
        echo ""
        echo "First time setup:"
        echo "  uv sync    - Install dependencies"
        ;;
esac
