"""
Bot API endpoints for Teams messaging.
Version 1.0.2 - Fixed duplicate paths
"""

from fastapi import APIRouter, Request, HTTPException
from botbuilder.core import TurnContext, MemoryStorage, ConversationState, UserState, BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity
import json
import structlog
import os

from ..config.settings import get_settings
from .teams_bot import DTCETeamsBot
from ..integrations.azure_search import get_search_client
from ..services.document_qa import DocumentQAService

logger = structlog.get_logger(__name__)
router = APIRouter()

# Initialize bot components
settings = get_settings()

# Create adapter for Teams with proper authentication
BOT_SETTINGS = BotFrameworkAdapterSettings(
    app_id=settings.microsoft_app_id or "",
    app_password=settings.microsoft_app_password or ""
)

ADAPTER = BotFrameworkAdapter(BOT_SETTINGS)

# Set up error handler for authentication issues
async def on_error(context: TurnContext, error: Exception):
    logger.error(f"Bot authentication error: {error}")
    # Don't send error message to user for auth errors
    if "authorization" not in str(error).lower():
        await context.send_activity("Sorry, an error occurred while processing your message.")

ADAPTER.on_turn_error = on_error

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


@router.get("/manifest")
async def get_teams_manifest():
    """Get the Teams app manifest for installation."""
    
    app_id = settings.microsoft_app_id or "YOUR_APP_ID"
    
    manifest = {
        "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.14/MicrosoftTeams.schema.json",
        "manifestVersion": "1.14",
        "version": "1.0.2",
        "id": app_id,
        "packageName": "com.dtce.ai.assistant",
        "developer": {
            "name": "DTCE",
            "websiteUrl": "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net",
            "privacyUrl": "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net",
            "termsOfUseUrl": "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
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
        "validDomains": [
            "donthomson.sharepoint.com",
            "*.azure.com",
            "*.openai.azure.com",
            "dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
        ],
        "webApplicationInfo": {
            "id": app_id,
            "resource": "https://graph.microsoft.com/"
        }
    }
    
    return manifest


@router.get("/manifest/download")
async def download_teams_manifest():
    """Download the Teams app manifest as a zip file."""
    import tempfile
    import zipfile
    import json
    from fastapi.responses import FileResponse
    import os
    
    try:
        # Get the manifest
        manifest = await get_teams_manifest()
        
        # Create a temporary zip file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
            with zipfile.ZipFile(temp_zip.name, 'w') as zip_file:
                # Add manifest.json
                zip_file.writestr('manifest.json', json.dumps(manifest, indent=2))
                
                # Add icons if they exist
                teams_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'teams')
                
                color_icon_path = os.path.join(teams_dir, 'icon-color.png')
                if os.path.exists(color_icon_path):
                    zip_file.write(color_icon_path, 'icon-color.png')
                
                outline_icon_path = os.path.join(teams_dir, 'icon-outline.png')
                if os.path.exists(outline_icon_path):
                    zip_file.write(outline_icon_path, 'icon-outline.png')
            
            return FileResponse(
                temp_zip.name,
                media_type='application/zip',
                filename='dtce-ai-assistant.zip',
                headers={"Content-Disposition": "attachment; filename=dtce-ai-assistant.zip"}
            )
            
    except Exception as e:
        logger.error("Error creating Teams app package", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error creating app package: {str(e)}")


@router.get("/setup")
async def get_teams_setup_instructions():
    """Get instructions for setting up the Teams bot."""
    
    instructions = {
        "title": "DTCE AI Assistant - Teams Bot Setup",
        "steps": [
            {
                "step": 1,
                "title": "Download the App Package",
                "description": "Download the Teams app package from /api/teams/manifest/download"
            },
            {
                "step": 2,
                "title": "Upload to Teams",
                "description": "In Microsoft Teams, go to Apps > Manage your apps > Upload an app > Upload a custom app"
            },
            {
                "step": 3,
                "title": "Install the App",
                "description": "Select the downloaded zip file and click 'Add' to install the DTCE AI Assistant"
            },
            {
                "step": 4,
                "title": "Start Using",
                "description": "Open a chat with the DTCE AI Assistant and start asking questions about your engineering documents!"
            }
        ],
        "features": [
            "🔍 Search engineering documents and project files",
            "❓ Ask questions about specific projects or topics",
            "📋 List available projects and documents",
            "🤖 AI-powered responses with document sources",
            "⚡ Real-time search through Suitefiles"
        ],
        "commands": [
            "/help - Show available commands",
            "/search [query] - Search documents",
            "/ask [question] - Ask questions",
            "/projects - List projects",
            "/health - Check system status"
        ],
        "app_id": settings.microsoft_app_id,
        "status": "ready" if settings.microsoft_app_id and settings.microsoft_app_password else "needs_configuration"
    }
    
    return instructions