"""
Azure App Service startup file for DTCE AI Bot
Updated to force container restart
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Azure App Service expects the app to run on port from environment variable
    port = int(os.environ.get("PORT", 8000))
    
    # Use string-based import which is more reliable in Azure
    import uvicorn
    print(f"Starting DTCE AI Bot on port {port}")
    uvicorn.run("dtce_ai_bot.main:app", host="0.0.0.0", port=port)
