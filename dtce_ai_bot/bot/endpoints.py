"""
Bot API endpoints for Teams messaging.
"""

from fastapi import APIRouter, Request, HTTPException
from botbuilder.core import TurnContext, MemoryStorage, ConversationState, UserState, BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity
import json
import structlog

from ..config.settings import get_settings
from .teams_bot import DTCETeamsBot
from ..integrations.azure_search import get_search_client
from ..services.document_qa import DocumentQAService

logger = structlog.get_logger(__name__)
router = APIRouter()

# Initialize bot components
settings = get_settings()

# Create adapter for Teams
BOT_SETTINGS = BotFrameworkAdapterSettings(
    app_id=settings.microsoft_app_id or "",
    app_password=settings.microsoft_app_password or ""
)

ADAPTER = BotFrameworkAdapter(BOT_SETTINGS)

# Create storage and state
MEMORY_STORAGE = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY_STORAGE)
USER_STATE = UserState(MEMORY_STORAGE)

# Initialize with actual service clients
try:
    search_client = get_search_client()
    qa_service = DocumentQAService(search_client)
    BOT = DTCETeamsBot(CONVERSATION_STATE, USER_STATE, search_client, qa_service)
    logger.info("Teams bot initialized successfully")
except Exception as e:
    logger.error("Failed to initialize Teams bot", error=str(e))
    BOT = None


@router.post("/messages")
async def messages_endpoint(request: Request):
    """Teams bot messaging endpoint."""
    
    if not BOT:
        raise HTTPException(status_code=503, detail="Teams bot not available")
    
    try:
        if "application/json" in request.headers.get("Content-Type", ""):
            body = await request.json()
        else:
            raise HTTPException(status_code=400, detail="Invalid content type")
        
        activity = Activity().deserialize(body)
        auth_header = request.headers.get("Authorization", "")
        
        async def call_bot(turn_context: TurnContext):
            await BOT.on_message_activity(turn_context)
        
        await ADAPTER.process_activity(activity, auth_header, call_bot)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error("Error processing Teams message", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@router.get("/teams/manifest")
async def get_teams_manifest():
    """Get the Teams app manifest for installation."""
    
    app_id = settings.microsoft_app_id or "YOUR_APP_ID"
    
    manifest = {
        "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.14/MicrosoftTeams.schema.json",
        "manifestVersion": "1.14",
        "version": "1.0.0",
        "id": app_id,
        "packageName": "com.dtce.ai.assistant",
        "developer": {
            "name": "DTCE",
            "websiteUrl": "https://dtce.com",
            "privacyUrl": "https://dtce.com/privacy",
            "termsOfUseUrl": "https://dtce.com/terms"
        },
        "icons": {
            "color": "icon-color.png",
            "outline": "icon-outline.png"
        },
        "name": {
            "short": "DTCE AI Assistant",
            "full": "DTCE Engineering Document AI Assistant"
        },
        "description": {
            "short": "AI-powered search for DTCE engineering documents",
            "full": "Search and find information from DTCE engineering project files using natural language queries. Get instant answers about projects, reports, calculations, and more."
        },
        "accentColor": "#667eea",
        "bots": [
            {
                "botId": app_id,
                "scopes": ["personal", "team", "groupchat"],
                "supportsFiles": False,
                "isNotificationOnly": False,
                "commandLists": [
                    {
                        "scopes": ["personal", "team", "groupchat"],
                        "commands": [
                            {
                                "title": "help",
                                "description": "Show available commands and examples"
                            },
                            {
                                "title": "search [query]",
                                "description": "Search engineering documents"
                            },
                            {
                                "title": "ask [question]",
                                "description": "Ask questions about documents"
                            },
                            {
                                "title": "projects",
                                "description": "List available projects"
                            },
                            {
                                "title": "health",
                                "description": "Check system status"
                            }
                        ]
                    }
                ]
            }
        ],
        "permissions": ["identity", "messageTeamMembers"],
        "validDomains": []
    }
    
