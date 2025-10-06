"""
Bot API endpoints for Teams integration.
Version 1.0.2 - Fixed duplicate paths
"""

from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    UserState,
    MemoryStorage,
    TurnContext,
)
from botbuilder.schema import Activity
from fastapi import APIRouter, Request, HTTPException
from openai import AsyncAzureOpenAI
import structlog

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient

from ..config.settings import get_settings
from ..services.azure_rag_service_v2 import AzureRAGService
from ..services.document_qa import DocumentQAService
from .teams_bot import DTCETeamsBot

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.get("/")
async def teams_root():
    """Teams bot router root endpoint."""
    return {"message": "Teams bot router is working", "endpoints": ["/messages", "/test-bot"]}

@router.get("/config-status")
async def check_bot_config():
    """Check if the bot is properly configured."""
    settings = get_settings()
    
    config_status = {
        "microsoft_app_id_configured": bool(settings.microsoft_app_id),
        "microsoft_app_password_configured": bool(settings.microsoft_app_password),
        "microsoft_app_tenant_id_configured": bool(settings.microsoft_app_tenant_id),
        "bot_ready": bool(settings.microsoft_app_id and settings.microsoft_app_password),
        "messaging_endpoint": "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/api/teams/messages",
        "app_id_preview": settings.microsoft_app_id[:8] + "..." if settings.microsoft_app_id else "NOT_SET"
    }
    
    return config_status

# Initialize clients from settings
settings = get_settings()

# Use async clients for bot endpoints
search_client_async = SearchClient(
    endpoint=settings.azure_search_service_endpoint,
    index_name=settings.azure_search_index_name,
    credential=AzureKeyCredential(settings.azure_search_api_key)
)

openai_client_async = AsyncAzureOpenAI(
    azure_endpoint=settings.azure_openai_endpoint,
    api_key=settings.azure_openai_api_key,
    api_version="2024-05-01-preview"
)

# Initialize the new RAG service
rag_service = AzureRAGService(
    search_client=search_client_async,
    openai_client=openai_client_async,
    model_name=settings.azure_openai_deployment_name,
    intent_model_name=settings.azure_openai_deployment_name  # Use the main model for intent
)

# This is a legacy service, we will phase it out
# For now, it can be used as a fallback or for specific simple QA
# It must be initialized per-request, so we don't create it here.

# Initialize bot components
# Create adapter for Teams with proper authentication
BOT_SETTINGS = BotFrameworkAdapterSettings(
    app_id=settings.microsoft_app_id,
    app_password=settings.microsoft_app_password,
)

# Create adapter with proper Bot Framework authentication
ADAPTER = BotFrameworkAdapter(BOT_SETTINGS)

# Set up error handler for authentication issues
async def on_error(context: TurnContext, error: Exception):
    logger.error(f"Bot error occurred: {error}")
    logger.error(f"Error type: {type(error).__name__}")
    logger.error(f"Error details: {str(error)}")
    # Send a simple error message to user
    try:
        await context.send_activity("Sorry, I encountered an error while processing your message. Please try again.")
    except Exception as send_error:
        logger.error(f"Failed to send error message: {send_error}")

ADAPTER.on_turn_error = on_error

# Create storage and state
MEMORY_STORAGE = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY_STORAGE)
USER_STATE = UserState(MEMORY_STORAGE)

# Initialize bot instance
BOT = DTCETeamsBot(
    conversation_state=CONVERSATION_STATE, 
    user_state=USER_STATE, 
    search_client=search_client_async,
    rag_service=rag_service
)


@router.post("/messages")
async def messages_endpoint(request: Request):
    """Teams bot messaging endpoint."""
    
    if not BOT:
        raise HTTPException(status_code=503, detail="Teams bot not available")

    try:
        body = await request.json()
        activity = Activity().deserialize(body)
        auth_header = request.headers.get("Authorization", "")
        
        async def call_bot(turn_context: TurnContext):
            await BOT.on_turn(turn_context)

        await ADAPTER.process_activity(activity, auth_header, call_bot)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing Teams message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.options("/messages")
async def messages_options_endpoint(request: Request):
    """Handle OPTIONS requests for CORS preflight."""
    return {"message": "CORS preflight handled"}

@router.get("/messages")
async def messages_get_endpoint(request: Request):
    """Handle GET requests to messages endpoint - for debugging."""
    logger.info("Received GET request to /messages endpoint")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Query params: {dict(request.query_params)}")
    return {"message": "Messages endpoint is available", "method": "GET", "supported_methods": ["POST"]}

@router.post("/messages")
async def messages_endpoint(request: Request):
    """Teams bot messaging endpoint."""
    
    try:
        logger.info("Received Teams message request")
        
        # Check if bot is available
        if not BOT:
            logger.error("Bot is not initialized.")
            raise HTTPException(status_code=503, detail="Teams bot is not available.")
        
        # Check content type
        content_type = request.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            logger.error(f"Invalid content type: {content_type}")
            raise HTTPException(status_code=400, detail="Invalid content type")
        
        # Get request body
        try:
            body = await request.json()
            logger.info("Request body received", body_type=type(body).__name__)
        except Exception as e:
            logger.error(f"Failed to parse JSON body: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        
        # Create activity
        try:
            activity = Activity().deserialize(body)
            logger.info("Activity created", activity_type=activity.type)
        except Exception as e:
            logger.error(f"Failed to deserialize activity: {e}")
            raise HTTPException(status_code=400, detail="Invalid activity format")
        
        # Get auth header
        auth_header = request.headers.get("Authorization", "")
        logger.info("Processing activity", has_auth=bool(auth_header))
        
        # Define bot callback
        async def call_bot(turn_context: TurnContext):
            try:
                await BOT.on_turn(turn_context)
                logger.info("Bot processing completed successfully")
            except Exception as e:
                logger.error(f"Bot processing failed: {e}")
                raise
        
        # Process activity with adapter
        try:
            await ADAPTER.process_activity(activity, auth_header, call_bot)
            logger.info("Activity processed successfully")
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Adapter processing failed: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            # Return 200 but log the error - Teams expects 200 for most errors
            return {"status": "error", "message": str(e)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in messages endpoint: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        # Return 200 to prevent 502 errors in Teams
        return {"status": "error", "message": "Internal server error"}


@router.options("/messages")
async def messages_options_endpoint(request: Request):
    """Handle OPTIONS requests for CORS preflight."""
    return {"message": "CORS preflight handled"}

@router.get("/messages")
async def messages_get_endpoint(request: Request):
    """Handle GET requests to messages endpoint - for debugging."""
    logger.info("Received GET request to /messages endpoint")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Query params: {dict(request.query_params)}")
    return {"message": "Messages endpoint is available", "method": "GET", "supported_methods": ["POST"]}

@router.post("/messages")
async def messages_endpoint(request: Request):
    """Teams bot messaging endpoint."""
    
    try:
        logger.info("Received Teams message request")
        
        # Check if bot is available
        if not BOT:
            logger.error("Bot is not initialized.")
            raise HTTPException(status_code=503, detail="Teams bot is not available.")
        
        # Check content type
        content_type = request.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            logger.error(f"Invalid content type: {content_type}")
            raise HTTPException(status_code=400, detail="Invalid content type")
        
        # Get request body
        try:
            body = await request.json()
            logger.info("Request body received", body_type=type(body).__name__)
        except Exception as e:
            logger.error(f"Failed to parse JSON body: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        
        # Create activity
        try:
            activity = Activity().deserialize(body)
            logger.info("Activity created", activity_type=activity.type)
        except Exception as e:
            logger.error(f"Failed to deserialize activity: {e}")
            raise HTTPException(status_code=400, detail="Invalid activity format")
        
        # Get auth header
        auth_header = request.headers.get("Authorization", "")
        logger.info("Processing activity", has_auth=bool(auth_header))
        
        # Define bot callback
        async def call_bot(turn_context: TurnContext):
            try:
                await BOT.on_turn(turn_context)
                logger.info("Bot processing completed successfully")
            except Exception as e:
                logger.error(f"Bot processing failed: {e}")
                raise
        
        # Process activity with adapter
        try:
            await ADAPTER.process_activity(activity, auth_header, call_bot)
            logger.info("Activity processed successfully")
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Adapter processing failed: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            # Return 200 but log the error - Teams expects 200 for most errors
            return {"status": "error", "message": str(e)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in messages endpoint: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        # Return 200 to prevent 502 errors in Teams
        return {"status": "error", "message": "Internal server error"}


@router.post("/simple-test")
async def simple_test_endpoint(request: Request):
    """Simple test endpoint that bypasses Bot Framework completely."""
    
    try:
        body = await request.json()
        message_text = body.get("text", "Hello")
        
        logger.info(f"Simple test received: {message_text}")
        
        # Test if QA service works
        if BOT and BOT.qa_service:
            try:
                result = await BOT.qa_service.answer_question(message_text)
                return {
                    "status": "success",
                    "input": message_text,
                    "response": result.get('answer', 'No answer generated'),
                    "confidence": result.get('confidence', 'unknown'),
                    "bot_initialized": True,
                    "qa_service_available": True
                }
            except Exception as e:
                return {
                    "status": "qa_error",
                    "input": message_text,
                    "error": str(e),
                    "bot_initialized": True,
                    "qa_service_available": False
                }
        else:
            return {
                "status": "bot_not_available",
                "input": message_text,
                "bot_initialized": BOT is not None,
                "qa_service_available": False
            }
            
    except Exception as e:
        logger.error(f"Simple test error: {e}")
        return {
            "status": "endpoint_error",
            "error": str(e)
        }


@router.post("/test-bot")
async def test_bot_endpoint(request: Request):
    """Test bot endpoint that bypasses authentication."""
    
    if not BOT:
        raise HTTPException(status_code=503, detail="Teams bot not available")
    
    try:
        body = await request.json()
        message_text = body.get("text", "Hello")
        
        # Create a mock turn context for testing
        from botbuilder.core import MessageFactory
        from unittest.mock import AsyncMock, MagicMock
        
        # Mock turn context
        mock_context = MagicMock()
        mock_context.activity = MagicMock()
        mock_context.activity.text = message_text
        mock_context.activity.type = "message"
        mock_context.activity.from_property = MagicMock()
        mock_context.activity.from_property.id = "test-user"
        mock_context.activity.from_property.name = "Test User"
        mock_context.send_activity = AsyncMock()
        
        # Call bot directly
        await BOT.on_message_activity(mock_context)
        
        # Get the response
        if mock_context.send_activity.called:
            call_args = mock_context.send_activity.call_args[0][0]
            response_text = call_args.text if hasattr(call_args, 'text') else str(call_args)
            return {"status": "ok", "response": response_text}
        else:
            return {"status": "ok", "response": "No response generated"}
        
    except Exception as e:
        logger.error("Error in test bot endpoint", error=str(e))
        return {"status": "error", "error": str(e)}
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