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
    
    # Check if we should use reload mode
    use_reload = settings.api_reload and settings.environment == "development"
    
    if use_reload:
        # Use import string for reload mode
        uvicorn.run(
            "dtce_ai_bot.core.app:create_app",
            factory=True,
            host=settings.api_host,
            port=settings.api_port,
            reload=True,
            log_level=settings.log_level.lower()
        )
    else:
        # Use app object for production
        app = create_app()
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port,
            reload=False,
            log_level=settings.log_level.lower()
        )


if __name__ == "__main__":
    main()
