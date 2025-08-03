"""
Main entry point for the DTCE AI Bot.
"""

import uvicorn
from .config.settings import get_settings


def main():
    """Start the DTCE AI Bot server."""
    settings = get_settings()
    
    uvicorn.run(
        "dtce_ai_bot.core.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False  # Disable reload to avoid import string issue
    )


if __name__ == "__main__":
    main()
