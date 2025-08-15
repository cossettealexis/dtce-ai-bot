"""
Main FastAPI application entry point for DTCE AI Bot.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from datetime import datetime

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.api.documents import router as documents_router
from dtce_ai_bot.bot.endpoints import router as bot_router

# Configure structured logging
logger = structlog.get_logger(__name__)
settings = get_settings()

# Initialize FastAPI application
app = FastAPI(
    title="DTCE AI Bot",
    description="AI-powered document processing and chat bot for engineering projects",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents_router, prefix="/documents", tags=["Documents"])
app.include_router(bot_router, prefix="/api/bot", tags=["Bot"])

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return JSONResponse({
        "message": "DTCE AI Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "teams_bot": "/api/bot",
            "documents": "/documents",
            "project_scoping": "/projects"
        }
    })

@app.get("/health")
async def health_check():
    """Health check endpoint with real-time timestamp."""
    return JSONResponse({
        "status": "healthy",
        "service": "dtce-ai-bot",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
