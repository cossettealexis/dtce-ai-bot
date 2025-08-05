"""
Core FastAPI application factory.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from ..config.settings import get_settings
from ..services.health import router as health_router
from ..bot.endpoints import router as bot_router
from ..services.documents import router as documents_router
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
        version="1.0.0",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url="/redoc" if settings.environment == "development" else None
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
    app.include_router(bot_router, prefix="/api", tags=["bot"])
    app.include_router(documents_router, prefix="/documents", tags=["documents"])
    
    return app
    
    return app


# Create app instance for uvicorn
app = create_app()
