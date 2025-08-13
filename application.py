"""
Simple app.py for Azure App Service - fallback startup file
"""
import os
import sys
import subprocess
from pathlib import Path

# Install dependencies if needed
try:
    import uvicorn
except ImportError:
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    import uvicorn

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment
os.environ.setdefault("ENVIRONMENT", "production")

# Import the app
from dtce_ai_bot.core.app import create_app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
