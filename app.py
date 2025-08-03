"""
DTCE AI Bot - Application Entry Point

A Microsoft Teams bot that helps engineers find information from project files.
"""

import uvicorn
from dtce_ai_bot.core.app import create_app
from dtce_ai_bot.config.settings import get_settings


def main():
    """Main application entry point."""
    settings = get_settings()
    app = create_app()
    
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload and settings.environment == "development",
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
