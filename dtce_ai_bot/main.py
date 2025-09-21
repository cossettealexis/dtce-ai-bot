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
        
        # Extract message text from Teams bot framework payload
        message_text = None
        if body.get("type") == "message" and "text" in body:
            message_text = body["text"].strip()
        elif "activity" in body and body["activity"].get("type") == "message":
            message_text = body["activity"].get("text", "").strip()
        elif "text" in body:
            message_text = body["text"].strip()
        
        if not message_text:
            logger.warning("No message text found in request", body=body)
            return JSONResponse({
                "type": "message",
                "text": "I didn't receive any message text. Please try again."
            })
        
        logger.info("Processing message", message=message_text)
        
        # Use the comprehensive RAG system
        try:
            from azure.search.documents import SearchClient
            from azure.identity import DefaultAzureCredential
            from openai import AsyncAzureOpenAI
            from .services.rag_handler import RAGHandler
            
            # Initialize Azure Search client
            search_endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
            search_index = os.environ.get("AZURE_SEARCH_INDEX", "dtce-documents")
            
            if not search_endpoint:
                logger.error("Missing AZURE_SEARCH_ENDPOINT environment variable")
                return JSONResponse({
                    "type": "message",
                    "text": "Configuration error: Missing search endpoint. Please contact support."
                })
            
            # Use managed identity for Azure Search
            credential = DefaultAzureCredential()
            search_client = SearchClient(
                endpoint=search_endpoint,
                index_name=search_index,
                credential=credential
            )
            
            # Initialize OpenAI client  
            openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            openai_key = os.environ.get("AZURE_OPENAI_API_KEY")
            model_name = os.environ.get("AZURE_OPENAI_MODEL_NAME", "gpt-4")
            
            if not openai_endpoint or not openai_key:
                logger.error("Missing OpenAI configuration")
                return JSONResponse({
                    "type": "message", 
                    "text": "Configuration error: Missing AI configuration. Please contact support."
                })
            
            openai_client = AsyncAzureOpenAI(
                azure_endpoint=openai_endpoint,
                api_key=openai_key,
                api_version="2024-02-01"
            )
            
            # Initialize comprehensive RAG handler
            rag_handler = RAGHandler(search_client, openai_client, model_name)
            
            # Process the question using the comprehensive RAG system
            result = await rag_handler.process_comprehensive_rag(message_text)
            
            response_text = result.get("answer", "I couldn't process your question. Please try again.")
            
            logger.info("Comprehensive RAG response generated", 
                       response_length=len(response_text),
                       category=result.get("category", "unknown"),
                       confidence=result.get("confidence", "unknown"),
                       documents_searched=result.get("documents_searched", 0))
            
            # Return response in Teams bot format
            return JSONResponse({
                "type": "message",
                "text": response_text
            })
            
        except Exception as rag_error:
            logger.error("Comprehensive RAG system error", error=str(rag_error), error_type=type(rag_error).__name__)
            
            # Try fallback to simple response
            fallback_response = f"""I apologize, but I'm experiencing technical difficulties processing your question: "{message_text}"

This might be due to:
- Configuration issues with the search or AI services
- Network connectivity problems  
- Temporary service unavailability

Please try again in a few moments, or contact support if the issue persists.

Technical details: {str(rag_error)}"""
            
            return JSONResponse({
                "type": "message", 
                "text": fallback_response
            })
        
    except Exception as e:
        logger.error("Error processing bot message", error=str(e))
        return JSONResponse({
            "type": "message",
            "text": "I encountered an error processing your message. Please try again."
        }, status_code=500)

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
