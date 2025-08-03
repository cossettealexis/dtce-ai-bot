#!/bin/bash

# DTCE AI Assistant Startup Script

echo "🚀 Starting DTCE AI Assistant..."
echo "================================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "⚙️  Please edit .env file with your credentials before running the application."
    exit 1
fi

echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Then visit: http://localhost:8000/static/index.html"
echo ""
echo "API Documentation: http://localhost:8000/docs"
