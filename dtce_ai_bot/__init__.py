"""
DTCE AI Bot - Internal AI Assistant for Engineering Teams

A Microsoft Teams bot that helps engineers find information from project files
using Azure Cognitive Search and OpenAI.
"""

__version__ = "1.0.0"
__author__ = "DTCE Engineering Team"
__email__ = "engineering@dtce.com"

from .core.app import create_app
from .bot.teams_bot import DTCETeamsBot

__all__ = ["create_app", "DTCETeamsBot"]
