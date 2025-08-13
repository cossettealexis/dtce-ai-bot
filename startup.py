"""
Azure App Service startup script for DTCE AI Bot.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables for Azure App Service
os.environ.setdefault("ENVIRONMENT", "production")
os.environ.setdefault("API_HOST", "0.0.0.0")
os.environ.setdefault("API_PORT", "8000")

# Import and create the app
from dtce_ai_bot.core.app import create_app

# Create the FastAPI application
app = create_app()

# For Azure App Service, the application should be available as 'app'
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
