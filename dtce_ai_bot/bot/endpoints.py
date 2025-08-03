"""
Bot API endpoints for Teams messaging.
"""

from fastapi import APIRouter, Request, HTTPException
from botbuilder.core import TurnContext, MemoryStorage, ConversationState, UserState, BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity
import json

from ..config.settings import get_settings
from .teams_bot import DTCETeamsBot

router = APIRouter()

# Initialize bot components
settings = get_settings()

# Create adapter for Teams
from botbuilder.core.bot_framework_adapter import BotFrameworkAdapter, BotFrameworkAdapterSettings

BOT_SETTINGS = BotFrameworkAdapterSettings(
    app_id=settings.microsoft_app_id,
    app_password=settings.microsoft_app_password
)

ADAPTER = BotFrameworkAdapter(BOT_SETTINGS)

# Create storage and state
MEMORY_STORAGE = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY_STORAGE)
USER_STATE = UserState(MEMORY_STORAGE)

# TODO: Initialize with actual service clients
BOT = DTCETeamsBot(CONVERSATION_STATE, USER_STATE, None, None)


@router.post("/messages")
async def messages_endpoint(request: Request):
    """Teams bot messaging endpoint."""
    
    if "application/json" in request.headers.get("Content-Type", ""):
        body = await request.json()
    else:
        raise HTTPException(status_code=400, detail="Invalid content type")
    
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")
    
    try:
        response = await ADAPTER.process_activity(activity, auth_header, BOT.on_message_activity)
        if response:
            return response.body
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bot processing error: {str(e)}")
