# API Documentation - DTCE AI Assistant

## Overview

The DTCE AI Assistant provides a comprehensive REST API for document management, AI-powered Q&A, and Microsoft Teams integration. All endpoints follow RESTful conventions and return JSON responses.

## Base URL

- **Local Development**: `http://localhost:8000`
- **Production**: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net`

## Authentication

Most endpoints require Azure AD authentication or Teams app authentication. Development endpoints may be configured to allow anonymous access.

```bash
# Example with Bearer token
curl -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     <endpoint>
```

## Document Management API

### Sync SharePoint Documents

#### Standard Sync
Synchronize documents from SharePoint to Azure Blob Storage.

```http
POST /documents/sync-suitefiles
```

**Query Parameters:**
- `path` (optional): Specific SharePoint path to sync
- `force` (optional): Force re-sync all files even if up-to-date (default: false)

**Examples:**
```bash
# Sync all documents
curl -X POST "http://localhost:8000/documents/sync-suitefiles"

# Sync specific project
curl -X POST "http://localhost:8000/documents/sync-suitefiles?path=Projects/219"

# Force re-sync specific path
curl -X POST "http://localhost:8000/documents/sync-suitefiles?path=Clients/&force=true"
```

**Response:**
```json
{
  "status": "completed",
  "message": "Sync completed! 150 documents ready for AI queries.",
  "synced_count": 150,
  "processed_count": 200,
  "ai_ready_count": 150,
  "skipped_count": 50,
  "error_count": 0,
  "folder_count": 25,
  "performance_notes": ["Sync completed in 45 seconds"],
  "sync_mode": "path_Projects_219",
  "path": "Projects/219",
  "timestamp": "2025-08-17T13:30:00.000Z"
}
```

#### Async Sync
Real asynchronous document synchronization with better timeout handling.

```http
POST /documents/sync-suitefiles-async
```

**Query Parameters:**
- `path` (optional): Specific SharePoint path to sync
- `force` (optional): Force re-sync all files even if up-to-date (default: false)

**Examples:**
```bash
# Async sync all documents
curl -X POST "http://localhost:8000/documents/sync-suitefiles-async"

# Async sync with force re-sync
curl -X POST "http://localhost:8000/documents/sync-suitefiles-async?force=true"

# Async sync specific engineering folder
curl -X POST "http://localhost:8000/documents/sync-suitefiles-async?path=Engineering/Marketing"
```

**Response:**
```json
{
  "status": "completed",
  "message": "ASYNC Sync completed! 150 documents ready for AI queries.",
  "synced_count": 150,
  "processed_count": 200,
  "ai_ready_count": 150,
  "skipped_count": 50,
  "error_count": 0,
  "folder_count": 25,
  "performance_notes": ["Real-time processing completed"],
  "sync_mode": "async_path_Engineering_Marketing",
  "path": "Engineering/Marketing",
  "timestamp": "2025-08-17T13:30:00.000Z"
}
```

### Extract Text from Document

Extract text content from a specific document using Azure Form Recognizer.

```http
POST /documents/extract
```

**Query Parameters:**
- `blob_name` (required): Name of the blob to extract text from

**Example:**
```bash
curl -X POST "http://localhost:8000/documents/extract?blob_name=Projects_219_specifications.pdf"
```

**Response:**
```json
{
  "status": "success",
  "extracted_text": "Document content here...",
  "metadata": {
    "page_count": 15,
    "extraction_method": "azure_form_recognizer",
    "file_size_mb": 2.5,
    "processing_time_seconds": 8.3
  },
  "document_info": {
    "blob_name": "Projects_219_specifications.pdf",
    "last_modified": "2025-08-17T10:15:00.000Z",
    "content_type": "application/pdf"
  }
}
```

### Search Documents

Search through synchronized documents based on content or metadata.

```http
GET /documents/search
```

**Query Parameters:**
- `q` (required): Search query
- `limit` (optional): Maximum number of results (default: 10)
- `path` (optional): Restrict search to specific path

**Example:**
```bash
curl "http://localhost:8000/documents/search?q=foundation+design&limit=5&path=Projects"
```

**Response:**
```json
{
  "results": [
    {
      "document_id": "Projects_219_foundation_specs.pdf",
      "title": "Foundation Design Specifications",
      "path": "Projects/219/Engineering",
      "relevance_score": 0.95,
      "excerpt": "Foundation design specifications for residential construction...",
      "last_modified": "2025-08-15T14:30:00.000Z",
      "file_size_mb": 1.2
    }
  ],
  "total_results": 12,
  "search_time_ms": 145,
  "query": "foundation design"
}
```

## Chat & Q&A API

### Ask Questions about Documents

Submit questions to get AI-powered answers based on synchronized documents.

```http
POST /chat
```

**Request Body:**
```json
{
  "message": "What are the foundation requirements for Project 219?",
  "session_id": "user123_session456",
  "context": {
    "project_filter": "Projects/219",
    "document_types": ["specifications", "drawings"]
  }
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "What are the foundation requirements for Project 219?",
       "session_id": "user123_session456"
     }'
```

**Response:**
```json
{
  "response": "Based on the project specifications, Project 219 requires concrete footings with a minimum depth of 600mm below ground level. The foundation must be designed for medium density soil conditions...",
  "sources": [
    {
      "document": "Projects_219_foundation_specs.pdf",
      "relevance": 0.92,
      "excerpt": "Foundation depth minimum 600mm..."
    }
  ],
  "session_id": "user123_session456",
  "timestamp": "2025-08-17T13:45:00.000Z",
  "processing_time_ms": 1250
}
```

### Get Chat History

Retrieve conversation history for a specific session.

```http
GET /chat/history
```

**Query Parameters:**
- `session_id` (required): Session identifier
- `limit` (optional): Maximum number of messages (default: 50)

**Example:**
```bash
curl "http://localhost:8000/chat/history?session_id=user123_session456&limit=10"
```

**Response:**
```json
{
  "messages": [
    {
      "id": "msg_001",
      "type": "user",
      "content": "What are the foundation requirements for Project 219?",
      "timestamp": "2025-08-17T13:45:00.000Z"
    },
    {
      "id": "msg_002",
      "type": "assistant",
      "content": "Based on the project specifications...",
      "sources": [...],
      "timestamp": "2025-08-17T13:45:02.000Z"
    }
  ],
  "session_id": "user123_session456",
  "total_messages": 8
}
```

## Project Analysis API

### Project Scoping Analysis

Analyze a new project description and find similar past projects.

```http
POST /projects/scope
```

**Request Body:**
```json
{
  "project_description": "Residential development with 15 units, 3 stories, concrete construction",
  "location": "Wellington, New Zealand",
  "budget_range": "$2M-$5M",
  "timeline": "18 months"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/projects/scope" \
     -H "Content-Type: application/json" \
     -d '{
       "project_description": "Residential development with 15 units",
       "location": "Wellington, New Zealand"
     }'
```

**Response:**
```json
{
  "analysis": {
    "project_complexity": "medium",
    "estimated_duration": "16-20 months",
    "key_considerations": [
      "Building consent requirements",
      "Seismic design considerations",
      "Stormwater management"
    ]
  },
  "similar_projects": [
    {
      "project_id": "Projects/218",
      "name": "Marine Parade Apartments",
      "similarity_score": 0.87,
      "location": "Wellington",
      "units": 12,
      "completion_date": "2024-03-15"
    }
  ],
  "risks": [
    {
      "category": "regulatory",
      "description": "Building consent delays common for multi-unit developments",
      "mitigation": "Early engagement with council, pre-application meetings"
    }
  ],
  "recommendations": [
    "Review Project 218 specifications for similar design patterns",
    "Consider early geotechnical investigation",
    "Plan for 6-month consent process"
  ]
}
```

## Teams Bot API

### Process Teams Messages

Handle incoming messages from Microsoft Teams bot.

```http
POST /api/teams/messages
```

**Request Body:** (Bot Framework Activity)
```json
{
  "type": "message",
  "text": "Hello, can you help me find project specifications?",
  "from": {
    "id": "user_id",
    "name": "John Doe"
  },
  "conversation": {
    "id": "conversation_id"
  }
}
```

**Response:** (Bot Framework Activity)
```json
{
  "type": "message",
  "text": "Hello! I can help you find project specifications. You can ask me questions like:\n- 'Find specifications for Project 219'\n- 'What are the foundation requirements?'\n- 'Show me similar projects'\n\nWhat would you like to know?",
  "attachments": []
}
```

## System API

### Health Check

Check the health status of the application and its dependencies.

```http
GET /health
```

**Example:**
```bash
curl "http://localhost:8000/health"
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-08-17T13:50:00.000Z",
  "version": "1.2.0",
  "services": {
    "azure_storage": "healthy",
    "azure_form_recognizer": "healthy",
    "microsoft_graph": "healthy",
    "database": "healthy"
  },
  "performance": {
    "response_time_ms": 45,
    "active_connections": 12,
    "memory_usage_mb": 245
  }
}
```

### Privacy Policy

Teams app compliance endpoint.

```http
GET /privacy
```

**Response:** HTML page with privacy policy

### Terms of Use

Teams app compliance endpoint.

```http
GET /terms
```

**Response:** HTML page with terms of use

## Error Handling

All API endpoints follow consistent error response formats:

### HTTP Status Codes
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource not found)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

### Error Response Format
```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "The specified document could not be found",
    "details": {
      "blob_name": "nonexistent_file.pdf",
      "path": "Projects/999"
    }
  },
  "timestamp": "2025-08-17T13:55:00.000Z",
  "request_id": "req_abc123def456"
}
```

## Rate Limiting

API endpoints are subject to rate limiting to ensure fair usage:

- **Document Sync**: 10 requests per minute per user
- **Chat API**: 60 requests per minute per user
- **Search API**: 100 requests per minute per user
- **Teams Bot**: No rate limiting (handled by Bot Framework)

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1692273600
```

## SDK and Integration Examples

### Python SDK Example
```python
import httpx
import asyncio

class DTCEClient:
    def __init__(self, base_url: str, auth_token: str = None):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"
    
    async def sync_documents(self, path: str = None, force: bool = False):
        params = {}
        if path:
            params["path"] = path
        if force:
            params["force"] = "true"
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/documents/sync-suitefiles-async",
                headers=self.headers,
                params=params
            )
            return response.json()
    
    async def ask_question(self, message: str, session_id: str):
        data = {
            "message": message,
            "session_id": session_id
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat",
                headers=self.headers,
                json=data
            )
            return response.json()

# Usage
async def main():
    client = DTCEClient("http://localhost:8000")
    
    # Sync documents
    sync_result = await client.sync_documents(path="Projects/219", force=True)
    print(f"Synced {sync_result['synced_count']} documents")
    
    # Ask a question
    answer = await client.ask_question(
        "What are the foundation requirements?",
        "user123_session"
    )
    print(f"Answer: {answer['response']}")

asyncio.run(main())
```

### JavaScript/Node.js Example
```javascript
class DTCEClient {
    constructor(baseUrl, authToken = null) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Content-Type': 'application/json'
        };
        if (authToken) {
            this.headers['Authorization'] = `Bearer ${authToken}`;
        }
    }
    
    async syncDocuments(path = null, force = false) {
        const params = new URLSearchParams();
        if (path) params.append('path', path);
        if (force) params.append('force', 'true');
        
        const response = await fetch(
            `${this.baseUrl}/documents/sync-suitefiles-async?${params}`,
            {
                method: 'POST',
                headers: this.headers
            }
        );
        return response.json();
    }
    
    async askQuestion(message, sessionId) {
        const response = await fetch(`${this.baseUrl}/chat`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        return response.json();
    }
}

// Usage
const client = new DTCEClient('http://localhost:8000');

// Sync documents
client.syncDocuments('Projects/219', true)
    .then(result => console.log(`Synced ${result.synced_count} documents`));

// Ask a question
client.askQuestion('What are the foundation requirements?', 'user123_session')
    .then(answer => console.log(`Answer: ${answer.response}`));
```

## Interactive API Documentation

For interactive API documentation with request/response examples, visit:
- **Local**: http://localhost:8000/docs
- **Production**: https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/docs

The interactive documentation provides:
- Real-time API testing
- Request/response schemas
- Authentication setup
- Example requests for all endpoints
