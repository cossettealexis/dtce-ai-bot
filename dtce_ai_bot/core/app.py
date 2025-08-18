"""
Core FastAPI application factory.
"""

import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import structlog
import httpx
import json

from ..config.settings import get_settings
from ..api.health import router as health_router
from ..bot.endpoints import router as bot_router
from ..api.documents import router as documents_router
from ..api.project_scoping import router as project_scoping_router


def configure_logging():
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    # Configure logging
    configure_logging()
    
    # Create FastAPI app
    app = FastAPI(
        title="DTCE AI Assistant",
        description="Internal AI assistant for DTCE engineering teams",
        version="1.1.0",
        docs_url="/docs",  # Always enable docs for internal tool
        redoc_url="/redoc"  # Always enable redoc for internal tool
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize Azure Search Index on startup
    @app.on_event("startup")
    async def startup_event():
        """Initialize Azure services on startup."""
        logger = structlog.get_logger()
        try:
            logger.info("Initializing Azure Search index...")
            from ..integrations.azure.search_client import AzureSearchClient
            search_client = AzureSearchClient()
            await search_client.create_or_update_index()
            logger.info("Azure Search index initialization complete")
        except Exception as e:
            logger.error("Failed to initialize Azure Search index", error=str(e))
    
    # Include routers
    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(bot_router, prefix="/api/teams", tags=["teams-bot"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(project_scoping_router, prefix="/projects", tags=["project-scoping"])
    
    # Track Bot Framework calls - simple counter without exposing keys
    bot_calls = {"count": 0, "last_call": None}
    
    @app.get("/debug/bot-calls")
    async def get_bot_calls():
        """Check if Bot Framework is calling our endpoint."""
        return {
            "total_calls": bot_calls["count"],
            "last_call_time": bot_calls["last_call"],
            "status": "Bot Framework is calling our endpoint" if bot_calls["count"] > 0 else "No Bot Framework calls detected"
        }
    
    # Bot Framework with proper Single Tenant authentication
    
    # Bot Framework Setup
    from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, ActivityHandler, TurnContext, MessageFactory
    from botbuilder.schema import Activity
    
    # Set up Bot Framework adapter with proper settings
    bot_logger = structlog.get_logger()
    bot_logger.info("🔧 Bot Framework Config", 
                app_id=settings.effective_app_id, 
                tenant_id=settings.effective_app_tenant_id,
                has_password=bool(settings.effective_app_password))
    
    adapter_settings = BotFrameworkAdapterSettings(
        app_id=settings.effective_app_id,
        app_password=settings.effective_app_password,
        channel_auth_tenant=settings.effective_app_tenant_id  # Required for Single Tenant
    )
    adapter = BotFrameworkAdapter(adapter_settings)
    
    class DTCEBot(ActivityHandler):
        def is_greeting_or_help(self, text: str) -> bool:
            """Check if the message is a greeting or help request."""
            greetings = ["hi", "hello", "hey", "help", "what can you do", "how are you", "good morning", "good afternoon"]
            return text.lower().strip() in greetings or len(text.strip()) < 4
        
        async def on_message_activity(self, turn_context: TurnContext):
            logger = structlog.get_logger()
            user_message = turn_context.activity.text
            logger.info("🔥 BOT RECEIVED MESSAGE", text=user_message)
            
            # Check if it's a greeting or help request
            if self.is_greeting_or_help(user_message):
                greeting_response = (
                    "Hi there! 👋\n\n"
                    "I'm your DTCE document assistant. I can help you find engineering documents, reports, and project files.\n\n"
                    "Just ask me in plain English about what you're looking for:\n"
                    "• \"Find structural calculations\"\n"
                    "• \"Show me bridge drawings\"\n"
                    "• \"What reports do we have for the Auckland project?\"\n\n"
                    "What can I help you find today?"
                )
                await turn_context.send_activity(MessageFactory.text(greeting_response))
                return
            
            try:
                # Import the AI services
                from ..integrations.azure.search_client import AzureSearchClient
                from ..integrations.azure.openai_client import AzureOpenAIClient
                from ..models.legacy_models import SearchQuery
                
                # Initialize AI clients
                search_client = AzureSearchClient()
                openai_client = AzureOpenAIClient()
                
                # Create search query from user message
                search_query = SearchQuery(
                    query=user_message,
                    max_results=5,
                    include_content=True
                )
                
                # Search for relevant documents
                search_response = await search_client.search_documents(search_query)
                
                if search_response.results:
                    # Use AI to answer based on found documents
                    context_documents = []
                    for result in search_response.results[:3]:  # Top 3 results
                        doc = result.document
                        context_documents.append({
                            "file_name": doc.file_name,
                            "content": doc.content_preview or doc.extracted_text or "",
                            "project_id": doc.project_id,
                            "document_type": doc.document_type.value,
                            "score": result.score
                        })
                    
                    # Generate AI response
                    ai_response = await openai_client.answer_engineering_question(
                        user_message, 
                        context_documents
                    )
                    
                    response_text = f"🔍 **DTCE AI Assistant**\n\n{ai_response}\n\n📄 **Sources**: {len(context_documents)} relevant documents found"
                    
                else:
                    # No documents found, provide general response
                    response_text = f"🔍 **DTCE AI Assistant**\n\nI couldn't find specific documents related to your query '{user_message}'. Could you try rephrasing your question or provide more specific terms? I can help you search for:\n\n• Project reports and specifications\n• Calculations and drawings\n• Technical standards and codes\n• Past project examples"
                
                await turn_context.send_activity(MessageFactory.text(response_text))
                
            except Exception as e:
                logger.error("Error processing AI request", error=str(e))
                error_response = "🚨 I'm experiencing technical difficulties. Please try again in a moment, or contact IT support if the issue persists."
                await turn_context.send_activity(MessageFactory.text(error_response))
    
    bot = DTCEBot()

    @app.api_route("/api/messages", methods=["GET", "POST", "OPTIONS"])
    async def bot_framework_messages(request: Request):
        """Bot Framework endpoint using proper adapter.process_activity."""
        logger = structlog.get_logger()
        
        if request.method == "OPTIONS":
            return Response(headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "*"})
            
        if request.method == "GET":
            return {"status": "ready", "bot": "dtceai-bot", "timestamp": "2025-08-17T22:25:00Z"}
            
        # POST - handle Bot Framework messages using proper adapter
        try:
            # Track Bot Framework calls
            from datetime import datetime
            bot_calls["count"] += 1
            bot_calls["last_call"] = datetime.now().isoformat()
            
            logger.info("🔥 API/MESSAGES HIT!", call_number=bot_calls["count"])
            
            # Get the request body as JSON and auth header
            body_json = await request.json()
            auth_header = request.headers.get("authorization", "")
            
            logger.info("Incoming activity", body=body_json)
            
            # Create activity from JSON
            activity = Activity().deserialize(body_json)
            
            # Bot handler function
            async def bot_handler(turn_context: TurnContext):
                await bot.on_turn(turn_context)
            
            # Use Bot Framework adapter with positional arguments
            await adapter.process_activity(
                activity,
                auth_header,
                bot_handler
            )
            
            # Return 200 OK for Bot Framework
            return Response(status_code=200)
                
        except Exception as e:
            logger.error("Error processing bot message", error=str(e))
            return Response(status_code=500)
    
    # Add root route
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "DTCE AI Assistant API",
            "version": "1.1.0",
            "docs": "/docs",
            "health": "/health",
            "endpoints": {
                "teams_bot": "/api/teams",
                "documents": "/documents",
                "sync_suitefiles": "/documents/sync-suitefiles",
                "sync_async_start": "/documents/sync-async/start",
                "sync_async_status": "/documents/sync-async/status/{job_id}",
                "sync_async_jobs": "/documents/sync-async/jobs",
                "sync_async_cancel": "/documents/sync-async/cancel/{job_id}",
                "list_documents": "/documents/list",
                "test_connection": "/documents/test-connection",
                "project_scoping": "/projects"
            }
        }
    
    # Add Teams app compliance endpoints
    @app.get("/privacy")
    async def privacy_policy():
        """Privacy policy for Teams app compliance."""
        return {
            "title": "DTCE AI Assistant - Privacy Policy",
            "effective_date": "2025-08-17",
            "company": "Don Thomson Consulting Engineers Ltd",
            "description": "This AI assistant processes internal engineering documents and project files for DTCE staff members.",
            "data_handling": {
                "collection": "We collect queries and document interactions to provide AI-powered search and assistance",
                "storage": "Data is stored securely in Azure cloud services within New Zealand",
                "usage": "Information is used solely for providing engineering document search and AI assistance to DTCE staff",
                "sharing": "Data is not shared with third parties outside of Microsoft Azure services required for operation"
            },
            "contact": "For privacy questions, contact DTCE IT department",
            "updates": "This policy may be updated to reflect changes in our practices"
        }
    
    @app.get("/terms")
    async def terms_of_use():
        """Terms of use for Teams app compliance."""
        return {
            "title": "DTCE AI Assistant - Terms of Use",
            "effective_date": "2025-08-17",
            "company": "Don Thomson Consulting Engineers Ltd",
            "terms": {
                "usage": "This AI assistant is for internal DTCE staff use only for engineering document search and assistance",
                "restrictions": "Users must not share confidential project information outside authorized DTCE personnel",
                "accuracy": "AI responses should be verified for critical engineering decisions",
                "availability": "Service availability is provided on a best-effort basis",
                "compliance": "Users must comply with DTCE information security policies"
            },
            "contact": "For questions about these terms, contact DTCE management",
            "modifications": "DTCE reserves the right to modify these terms with notice to users"
        }
    
    # Mount static files for testing page
    static_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")
    
    return app


# Create app instance for uvicorn
app = create_app()
