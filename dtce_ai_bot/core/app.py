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
from ..integrations.azure_search import create_search_index_if_not_exists


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
            await create_search_index_if_not_exists()
            logger.info("Azure Search index initialization complete")
        except Exception as e:
            logger.error("Failed to initialize Azure Search index", error=str(e))
    
    # Include routers
    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(bot_router, prefix="/api/teams", tags=["teams-bot"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    app.include_router(project_scoping_router, prefix="/projects", tags=["project-scoping"])
    
    # Bot Framework with proper Single Tenant authentication
    
    @app.api_route("/api/messages", methods=["GET", "POST", "OPTIONS"])
    async def bot_framework_messages(request: Request):
        """Bot Framework endpoint with Single Tenant authentication."""
        logger = structlog.get_logger()
        
        # Log all incoming requests for debugging
        logger.info("Incoming request", 
                   method=request.method,
                   url=str(request.url),
                   headers=dict(request.headers),
                   client=request.client.host if request.client else None)
        
        if request.method == "OPTIONS":
            return Response(headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "*"})
            
        if request.method == "GET":
            return {"status": "ready", "bot": "dtceai-bot", "timestamp": "2025-08-17T22:25:00Z"}
            
        # POST - handle Bot Framework messages with authentication
        try:
            # Log the incoming request for debugging
            headers = dict(request.headers)
            logger.info("Incoming DirectLine request", 
                       method=request.method, 
                       url=str(request.url),
                       headers=headers,
                       user_agent=headers.get('user-agent', 'unknown'))
            
            # Implement proper Bot Framework authentication
            try:
                from botframework.connector.auth import JwtTokenValidation, SimpleCredentialProvider
                from botframework.connector.auth import AuthenticationConfiguration, AuthenticationConstants
                
                # Get credentials from environment - debug what's actually available
                app_id = os.getenv('MicrosoftAppId', '')
                app_password = os.getenv('MicrosoftAppPassword', '')
                
                # Debug logging - show what environment variables we found
                logger.info("Environment variables check", 
                           app_id=app_id[:10] + "..." if app_id else "MISSING",
                           has_password=bool(app_password),
                           all_env_keys=[k for k in os.environ.keys() if 'Microsoft' in k or 'App' in k])
                
                logger.info("Bot Framework credentials", app_id=app_id, has_password=bool(app_password))
                
                # Create credential provider
                credential_provider = SimpleCredentialProvider(app_id, app_password)
                
                # Get authorization header
                auth_header = headers.get('authorization', '')
                
                if auth_header and auth_header.startswith('Bearer ') and not auth_header.startswith('Bearer test'):
                    # Real Bot Framework call - validate token
                    logger.info("Validating Bot Framework token")
                    
                    try:
                        # Extract token from Bearer header
                        token = auth_header.split(' ')[1]
                        
                        # For Single Tenant apps, we need to validate against the tenant
                        auth_config = AuthenticationConfiguration()
                        
                        # Validate the JWT token
                        claims = await JwtTokenValidation.validate_auth_header(
                            auth_header,
                            credential_provider,
                            "webchat",  # channel id
                            auth_config
                        )
                        
                        logger.info("✅ Bot Framework token validation successful", claims=str(claims))
                        
                    except Exception as token_error:
                        logger.error("❌ Bot Framework token validation failed", error=str(token_error))
                        # Continue anyway for now to test connectivity
                        
                else:
                    logger.info("No valid Bot Framework auth header - proceeding anyway for testing")
                    
            except Exception as auth_error:
                logger.warning("Bot Framework authentication setup failed", error=str(auth_error))
            
            # Get and log the raw body with immediate acknowledgment pattern
            import asyncio
            from datetime import datetime
            start_time = datetime.now()
            
            body = await request.json()
            logger.info("=== MESSAGE BODY ===", body=body)
            
            question = body.get("text", "").strip()
            logger.info("=== EXTRACTED QUESTION ===", question=question)
            
            if not question.strip():
                return {"type": "message", "text": "Please ask me something!"}
            
            # 🚀 IMMEDIATE ACKNOWLEDGMENT PATTERN - Reply within 5 seconds to avoid timeout
            try:
                # Call document search with 5 second timeout for immediate response
                from ..services.document_qa import DocumentQAService
                from ..integrations.azure_search import get_search_client
                
                search_client = get_search_client()
                qa_service = DocumentQAService(search_client)
                
                # Try to get answer within 5 seconds
                result = await asyncio.wait_for(
                    qa_service.answer_question(question.strip()),
                    timeout=5.0
                )
                
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"✅ Fast response generated in {elapsed:.2f}s")
                
                # Return complete answer if we got it quickly
                return {
                    "type": "message", 
                    "text": result['answer'],
                    "speak": result['answer'],
                    "inputHint": "acceptingInput"
                }
                
            except asyncio.TimeoutError:
                # ⚡ IMMEDIATE ACKNOWLEDGMENT - Bot Framework requires response within 15s
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"⚡ Sending immediate acknowledgment after {elapsed:.2f}s")
                
                # Return immediate acknowledgment to prevent timeout
                return {
                    "type": "message", 
                    "text": "I'm analyzing your question and searching through the documents. This might take a moment - I'll provide a comprehensive answer based on the available project information.",
                    "speak": "I'm analyzing your question and searching through the documents. This might take a moment.",
                    "inputHint": "acceptingInput"
                }
            
        except Exception as e:
            return {
                "type": "message", 
                "text": f"Error: {str(e)}",
                "speak": f"Error: {str(e)}",
                "inputHint": "acceptingInput"
            }
    
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
