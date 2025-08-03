from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import structlog
from datetime import datetime
from typing import List, Optional

# Teams Bot Framework imports
from botbuilder.core import TurnContext, MemoryStorage, ConversationState, UserState
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from botbuilder.schema import Activity
from aiohttp import web
from aiohttp.web import Request as AiohttpRequest, Response as AiohttpResponse

from config import settings
from src.models import (
    SearchQuery, SearchResponse, ProcessingStatus, 
    HealthCheck, DocumentMetadata
)
from src.sharepoint_client import SharePointClient
from src.azure_blob_client import AzureBlobClient
from src.azure_search_client import AzureSearchClient
from src.azure_openai_client import AzureOpenAIClient
from src.document_processor import DocumentProcessor
from src.teams_bot import DTCETeamsBot

# Configure structured logging
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

logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DTCE AI Assistant",
    description="AI-powered assistant for searching DTCE engineering project files",
    version=settings.app_version
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global clients (initialized on startup)
sharepoint_client: Optional[SharePointClient] = None
blob_client: Optional[AzureBlobClient] = None
search_client: Optional[AzureSearchClient] = None
openai_client: Optional[AzureOpenAIClient] = None
document_processor: Optional[DocumentProcessor] = None

# Teams Bot components
memory_storage: Optional[MemoryStorage] = None
conversation_state: Optional[ConversationState] = None
user_state: Optional[UserState] = None
teams_bot: Optional[DTCETeamsBot] = None
bot_adapter: Optional[CloudAdapter] = None

# Background task tracking
processing_tasks = {}


@app.on_event("startup")
async def startup_event():
    """Initialize clients and services on startup."""
    global sharepoint_client, blob_client, search_client, openai_client, document_processor
    global memory_storage, conversation_state, user_state, teams_bot, bot_adapter
    
    logger.info("Starting DTCE AI Assistant", version=settings.app_version)
    
    try:
        # Initialize core clients
        sharepoint_client = SharePointClient()
        blob_client = AzureBlobClient()
        search_client = AzureSearchClient()
        openai_client = AzureOpenAIClient()
        document_processor = DocumentProcessor()
        
        # Ensure Azure services are ready
        await blob_client.ensure_container_exists()
        await search_client.create_or_update_index()
        
        # Initialize Teams Bot components
        memory_storage = MemoryStorage()
        conversation_state = ConversationState(memory_storage)
        user_state = UserState(memory_storage)
        
        # Create Teams bot
        teams_bot = DTCETeamsBot(conversation_state, user_state, search_client, openai_client)
        
        # Create bot adapter
        bot_adapter = CloudAdapter(ConfigurationBotFrameworkAuthentication({
            "MicrosoftAppId": settings.microsoft_app_id,
            "MicrosoftAppPassword": settings.microsoft_app_password,
            "MicrosoftAppType": settings.microsoft_app_type,
            "MicrosoftAppTenantId": settings.microsoft_app_tenant_id
        }))
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise


def get_clients():
    """Dependency to get initialized clients."""
    return {
        'sharepoint': sharepoint_client,
        'blob': blob_client,
        'search': search_client,
        'openai': openai_client,
        'processor': document_processor
    }


@app.get("/", response_model=dict)
async def root():
    """Root endpoint with basic information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
        "type": "Microsoft Teams Bot"
    }


@app.post("/api/messages")
async def handle_teams_messages(request: Request):
    """Handle incoming messages from Microsoft Teams."""
    
    if not bot_adapter or not teams_bot:
        raise HTTPException(status_code=503, detail="Teams bot not initialized")
    
    try:
        # Get request body
        body = await request.body()
        
        # Create activity from request
        activity = Activity().deserialize(await request.json())
        
        # Process the activity
        auth_header = request.headers.get("Authorization", "")
        
        async def call_bot(turn_context: TurnContext):
            await teams_bot.on_message_activity(turn_context)
        
        await bot_adapter.process_activity(activity, auth_header, call_bot)
        
        return JSONResponse(content={"status": "ok"}, status_code=200)
        
    except Exception as e:
        logger.error("Error processing Teams message", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@app.get("/api/teams/manifest")
async def get_teams_manifest():
    """Get the Teams app manifest for installation."""
    
    manifest = {
        "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.14/MicrosoftTeams.schema.json",
        "manifestVersion": "1.14",
        "version": "1.0.0",
        "id": settings.microsoft_app_id,
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
        "accentColor": "#3498db",
        "bots": [
            {
                "botId": settings.microsoft_app_id,
                "scopes": ["personal", "team", "groupchat"],
                "commandLists": [
                    {
                        "scopes": ["personal", "team", "groupchat"],
                        "commands": [
                            {
                                "title": "Help",
                                "description": "Show available commands and examples"
                            },
                            {
                                "title": "Search documents",
                                "description": "Search for engineering documents"
                            },
                            {
                                "title": "List projects",
                                "description": "Show all available projects"
                            },
                            {
                                "title": "Health check",
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
    
    return manifest


@app.get("/health", response_model=HealthCheck)
async def health_check(clients = Depends(get_clients)):
    """Comprehensive health check endpoint."""
    
    services_status = {}
    overall_status = "healthy"
    
    # Check SharePoint connectivity
    try:
        await clients['sharepoint']._ensure_authenticated()
        services_status["sharepoint"] = "healthy"
    except Exception as e:
        services_status["sharepoint"] = f"unhealthy: {str(e)}"
        overall_status = "degraded"
    
    # Check Azure Blob Storage
    try:
        await clients['blob'].ensure_container_exists()
        services_status["blob_storage"] = "healthy"
    except Exception as e:
        services_status["blob_storage"] = f"unhealthy: {str(e)}"
        overall_status = "degraded"
    
    # Check Azure Search
    try:
        stats = await clients['search'].get_index_statistics()
        services_status["search"] = f"healthy (docs: {stats.get('document_count', 0)})"
    except Exception as e:
        services_status["search"] = f"unhealthy: {str(e)}"
        overall_status = "degraded"
    
    # Check Azure OpenAI
    try:
        # Simple test query
        test_response = await clients['openai'].client.chat.completions.create(
            model=clients['openai'].deployment_name,
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=1
        )
        services_status["openai"] = "healthy"
    except Exception as e:
        services_status["openai"] = f"unhealthy: {str(e)}"
        overall_status = "degraded"
    
    return HealthCheck(
        status=overall_status,
        services=services_status,
        version=settings.app_version
    )


@app.post("/api/search", response_model=SearchResponse)
async def search_documents(query: SearchQuery, clients = Depends(get_clients)):
    """Search for documents using natural language query."""
    
    logger.info("Search request received", query=query.query)
    
    try:
        # Perform search
        search_response = await clients['search'].search_documents(query)
        
        # Generate AI summary if results found
        if search_response.results and clients['openai']:
            ai_summary = await clients['openai'].generate_search_summary(search_response)
            search_response.ai_summary = ai_summary
        
        logger.info("Search completed", 
                   query=query.query, 
                   results=len(search_response.results))
        
        return search_response
        
    except Exception as e:
        logger.error("Search failed", query=query.query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/api/ingest/start")
async def start_document_ingestion(background_tasks: BackgroundTasks, clients = Depends(get_clients)):
    """Start the document ingestion process from SharePoint."""
    
    operation_id = f"ingest_{int(datetime.utcnow().timestamp())}"
    
    # Start background task
    background_tasks.add_task(
        run_document_ingestion,
        operation_id,
        clients
    )
    
    # Track the operation
    processing_tasks[operation_id] = ProcessingStatus(
        operation_id=operation_id,
        status="started",
        start_time=datetime.utcnow()
    )
    
    logger.info("Document ingestion started", operation_id=operation_id)
    
    return {
        "operation_id": operation_id,
        "status": "started",
        "message": "Document ingestion process has been started"
    }


@app.get("/api/ingest/status/{operation_id}", response_model=ProcessingStatus)
async def get_ingestion_status(operation_id: str):
    """Get the status of a document ingestion operation."""
    
    if operation_id not in processing_tasks:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    return processing_tasks[operation_id]


@app.get("/api/projects")
async def list_projects(clients = Depends(get_clients)):
    """List all available projects."""
    
    try:
        # Get project statistics from search index
        query = SearchQuery(query="*", max_results=1000)
        search_response = await clients['search'].search_documents(query)
        
        # Group by project ID
        projects = {}
        for result in search_response.results:
            project_id = result.document.project_id
            if project_id:
                if project_id not in projects:
                    projects[project_id] = {
                        "project_id": project_id,
                        "document_count": 0,
                        "latest_activity": None,
                        "document_types": set()
                    }
                
                projects[project_id]["document_count"] += 1
                projects[project_id]["document_types"].add(result.document.document_type.value)
                
                if result.document.modified_date:
                    if (not projects[project_id]["latest_activity"] or 
                        result.document.modified_date > projects[project_id]["latest_activity"]):
                        projects[project_id]["latest_activity"] = result.document.modified_date
        
        # Convert sets to lists for JSON serialization
        for project in projects.values():
            project["document_types"] = list(project["document_types"])
        
        return {"projects": list(projects.values())}
        
    except Exception as e:
        logger.error("Failed to list projects", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")


@app.get("/api/projects/{project_id}")
async def get_project_details(project_id: str, clients = Depends(get_clients)):
    """Get detailed information about a specific project."""
    
    try:
        # Search for all documents in this project
        query = SearchQuery(
            query="*",
            filters={"project_id": project_id},
            max_results=500
        )
        
        search_response = await clients['search'].search_documents(query)
        
        if not search_response.results:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Generate project summary using AI
        project_docs = [result.document.model_dump() for result in search_response.results]
        ai_summary = await clients['openai'].generate_project_summary(project_docs)
        
        # Organize documents by type
        documents_by_type = {}
        for result in search_response.results:
            doc_type = result.document.document_type.value
            if doc_type not in documents_by_type:
                documents_by_type[doc_type] = []
            documents_by_type[doc_type].append(result.document)
        
        return {
            "project_id": project_id,
            "total_documents": len(search_response.results),
            "ai_summary": ai_summary,
            "documents_by_type": documents_by_type,
            "documents": [result.document for result in search_response.results]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get project details", project_id=project_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get project details: {str(e)}")


@app.post("/api/ask")
async def ask_question(request: dict, clients = Depends(get_clients)):
    """Ask a specific question and get an AI-powered answer."""
    
    question = request.get("question", "")
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    try:
        # First, search for relevant documents
        search_query = SearchQuery(query=question, max_results=10)
        search_response = await clients['search'].search_documents(search_query)
        
        # Use AI to answer the question based on found documents
        context_docs = [result.document.model_dump() for result in search_response.results]
        answer = await clients['openai'].answer_engineering_question(question, context_docs)
        
        return {
            "question": question,
            "answer": answer,
            "relevant_documents": search_response.results[:5],  # Return top 5 relevant docs
            "total_documents_searched": len(search_response.results)
        }
        
    except Exception as e:
        logger.error("Failed to answer question", question=question, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {str(e)}")


async def run_document_ingestion(operation_id: str, clients: dict):
    """Background task to run document ingestion."""
    
    status = processing_tasks[operation_id]
    
    try:
        status.status = "scanning_sharepoint"
        logger.info("Starting SharePoint scan", operation_id=operation_id)
        
        # Scan SharePoint for documents
        documents = await clients['sharepoint'].scan_engineering_folders()
        status.total_files = len(documents)
        
        logger.info("SharePoint scan completed", 
                   operation_id=operation_id, 
                   total_files=len(documents))
        
        status.status = "processing_documents"
        
        # Process documents in batches
        batch_size = 10
        successful_uploads = 0
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            for document in batch:
                try:
                    # Download and process document content
                    if document.download_url:
                        content = await clients['sharepoint'].download_file_content(document.download_url)
                        if content:
                            # Process document to extract text
                            document = await clients['processor'].process_document(document, content)
                            
                            # Upload to blob storage
                            blob_url = await clients['blob'].upload_document_metadata(document)
                            if blob_url:
                                # Index in search
                                success = await clients['search'].index_document(document)
                                if success:
                                    successful_uploads += 1
                    
                    status.processed_files += 1
                    
                except Exception as e:
                    logger.error("Failed to process document", 
                               file_name=document.file_name, 
                               error=str(e))
                    status.failed_files += 1
        
        status.status = "completed"
        status.end_time = datetime.utcnow()
        
        logger.info("Document ingestion completed", 
                   operation_id=operation_id,
                   successful=successful_uploads,
                   failed=status.failed_files)
        
    except Exception as e:
        status.status = "failed"
        status.error_message = str(e)
        status.end_time = datetime.utcnow()
        
        logger.error("Document ingestion failed", 
                    operation_id=operation_id, 
                    error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload
    )
