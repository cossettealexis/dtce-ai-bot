#!/bin/bash

# DTCE AI Bot - MVP Testing Startup Script
# This script starts the FastAPI server and opens the testing page

echo "🚀 Starting DTCE AI Bot MVP Testing Environment..."

# Check if Python environment is activated
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
else
    echo "⚠️  No virtual environment detected. Consider activating one."
fi

# Start the FastAPI server in the background
echo "🔧 Starting FastAPI server..."
python -m uvicorn dtce_ai_bot.core.app:app --host 0.0.0.0 --port 8000 --reload &
SERVER_PID=$!

echo "📡 Server started with PID: $SERVER_PID"
echo "🌐 API will be available at: http://localhost:8000"
echo "📖 API Documentation: http://localhost:8000/docs"

# Wait a moment for server to start
echo "⏳ Waiting for server to start..."
sleep 3

# Check if server is running
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Server is running successfully!"
    
    # Open the testing page
    echo "🧪 Opening MVP Testing Page..."
    if command -v open &> /dev/null; then
        # macOS
        open http://localhost:8000/static/test.html
    elif command -v xdg-open &> /dev/null; then
        # Linux
        xdg-open http://localhost:8000/static/test.html
    elif command -v start &> /dev/null; then
        # Windows
        start http://localhost:8000/static/test.html
    else
        echo "🌐 Please open http://localhost:8000/static/test.html in your browser"
    fi
    
    echo ""
    echo "🎉 DTCE AI Bot MVP Testing Environment Ready!"
    echo ""
    echo "Available endpoints:"
    echo "  • Testing Page: http://localhost:8000/static/test.html"
    echo "  • API Health: http://localhost:8000/health"
    echo "  • API Docs: http://localhost:8000/docs"
    echo "  • Document API: http://localhost:8000/documents"
    echo ""
    echo "Press Ctrl+C to stop the server"
    
    # Wait for user to stop
    wait $SERVER_PID
    
else
    echo "❌ Failed to start server"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi
