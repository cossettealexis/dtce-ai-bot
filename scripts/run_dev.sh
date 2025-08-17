#!/bin/bash
# =============================================================================
# DTCE AI Assistant - Development Server Runner
# =============================================================================
# This script runs the development server with proper environment setup

set -e

echo "🚀 Starting DTCE AI Assistant Development Server..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Run './scripts/setup_dev.sh' first"
    exit 1
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Environment file (.env) not found"
    echo "Copy .env.example to .env and configure your Azure credentials"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Check for port availability
PORT=${1:-8000}
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Port $PORT is already in use"
    echo "Trying alternative ports..."
    for alt_port in 8001 8002 8003 8004; do
        if ! lsof -Pi :$alt_port -sTCP:LISTEN -t >/dev/null ; then
            PORT=$alt_port
            break
        fi
    done
    echo "Using port $PORT"
fi

echo "🌐 Starting server on http://localhost:$PORT"
echo "📚 API docs will be available at http://localhost:$PORT/docs"
echo "❤️  Health check at http://localhost:$PORT/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the development server
python -m uvicorn dtce_ai_bot.core.app:app \
    --reload \
    --host 0.0.0.0 \
    --port $PORT \
    --log-level info
