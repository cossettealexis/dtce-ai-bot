"""
Azure App Service startup script for DTCE AI Bot.
"""

import os
import sys
import subprocess
from pathlib import Path

def install_dependencies():
    """Install dependencies if not already installed"""
    print("📦 Checking Python dependencies...")
    try:
        import uvicorn
        print("✅ Dependencies already installed")
        return True
    except ImportError:
        print("⚠️ Installing dependencies from requirements.txt...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("✅ Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False

# Install dependencies first
if not install_dependencies():
    print("❌ Cannot start without dependencies")
    sys.exit(1)

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables for Azure App Service
os.environ.setdefault("ENVIRONMENT", "production")
os.environ.setdefault("API_HOST", "0.0.0.0")
os.environ.setdefault("API_PORT", "8000")

print("🚀 Starting DTCE AI Bot on Azure App Service (v2025-01-20-DEBUG-SYNTAX)...")

# Debug: Check teams_bot.py syntax before importing
try:
    import ast
    with open('dtce_ai_bot/bot/teams_bot.py', 'r') as f:
        source = f.read()
    
    # Compile check
    compile(source, 'dtce_ai_bot/bot/teams_bot.py', 'exec')
    print("✅ teams_bot.py syntax is valid")
    
    # AST parse check  
    ast.parse(source)
    print("✅ teams_bot.py AST parsing successful")
    
except Exception as e:
    print(f"❌ teams_bot.py syntax issue: {e}")
    import traceback
    traceback.print_exc()

# Import and create the app
from dtce_ai_bot.core.app import create_app

# Create the FastAPI application
app = create_app()

# For Azure App Service, the application should be available as 'app'
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🌐 Starting server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)