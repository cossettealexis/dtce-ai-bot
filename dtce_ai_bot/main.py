"""
DTCE AI Bot - Clean Implementation
FastAPI + Teams Bot Integration
Updated: Force Azure redeploy with correct app variable
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import structlog
from datetime import datetime
import os

# Configure structured logging
structlog.configure(
    processors=[
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
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title="DTCE AI Bot",
    description="Clean implementation of DTCE AI Assistant",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return JSONResponse({
        "message": "DTCE AI Assistant - Clean Implementation",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs",
        "health": "/health"
    })

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    })

@app.api_route("/api/messages", methods=["GET", "POST", "OPTIONS"])
async def bot_messages(request: Request):
    """Bot Framework endpoint for Teams integration."""
    logger.info("Bot messages endpoint called", method=request.method)
    
    if request.method == "OPTIONS":
        return Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST",
                "Access-Control-Allow-Headers": "*"
            }
        )
    
    if request.method == "GET":
        return JSONResponse({
            "status": "ready",
            "bot": "dtce-ai-bot-v2",
            "timestamp": datetime.now().isoformat()
        })
    
    # POST - Handle bot messages
    try:
        body = await request.json()
        logger.info("Received bot message", body=body)
        
        # For now, just return success
        # TODO: Implement bot logic
        return Response(status_code=200)
        
    except Exception as e:
        logger.error("Error processing bot message", error=str(e))
        return Response(status_code=500)

def main():
    """Main entry point for the application."""
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info("Starting DTCE AI Bot", host=host, port=port)
    
    uvicorn.run(
        "dtce_ai_bot.main:app",
        host=host,
        port=port,
        reload=False,
        access_log=True
    )

if __name__ == "__main__":
    main()
