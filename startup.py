"""
Azure App Service startup file for DTCE AI Bot
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main application
from dtce_ai_bot.main import app

if __name__ == "__main__":
    # Azure App Service expects the app to run on port from environment variable
    port = int(os.environ.get("PORT", 8000))
    
    # Run the FastAPI app using uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
