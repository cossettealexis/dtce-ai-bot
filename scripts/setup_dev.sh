#!/bin/bash
# =============================================================================
# DTCE AI Assistant - Development Setup Script
# =============================================================================
# This script sets up the local development environment

set -e  # Exit on any error

echo "🚀 Setting up DTCE AI Assistant Development Environment..."

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1-2)
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.9+ required. Found: $python_version"
    echo "Please install Python 3.9 or higher"
    exit 1
fi
echo "✅ Python $python_version detected"

# Create virtual environment
echo "🔧 Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "📦 Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
else
    echo "❌ requirements.txt not found"
    exit 1
fi

# Setup environment file
echo "⚙️  Setting up environment file..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Environment file created from .env.example"
        echo "⚠️  Please edit .env with your actual Azure credentials"
    else
        echo "❌ .env.example not found"
        exit 1
    fi
else
    echo "ℹ️  Environment file already exists"
fi

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p logs
echo "✅ Logs directory created"

# Create basic folder structure
echo "📂 Ensuring folder structure..."
mkdir -p tests/unit tests/integration docs/api docs/architecture

# Install development dependencies
echo "🧪 Installing development dependencies..."
pip install pytest pytest-cov pytest-asyncio black flake8 mypy

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your Azure credentials"
echo "2. Run 'source .venv/bin/activate' to activate the environment"
echo "3. Run 'python -m uvicorn dtce_ai_bot.core.app:app --reload' to start the server"
echo "4. Visit http://localhost:8000/docs to see the API documentation"
echo ""
echo "For detailed setup instructions, see README.md"
