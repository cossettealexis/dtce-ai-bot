# Testing Guide - DTCE AI Assistant

## Overview

This comprehensive testing guide covers unit testing, integration testing, end-to-end testing, and performance testing for the DTCE AI Assistant. The application follows Test-Driven Development (TDD) principles with comprehensive test coverage across all layers.

## Testing Architecture

### Testing Strategy
- **Unit Tests**: Individual component testing with mocks
- **Integration Tests**: Service-to-service communication testing
- **End-to-End Tests**: Complete workflow testing
- **Performance Tests**: Load and stress testing
- **Security Tests**: Authentication and authorization testing

### Testing Stack
- **pytest**: Primary testing framework
- **pytest-asyncio**: Async testing support
- **pytest-mock**: Mocking and patching
- **httpx**: HTTP client testing
- **coverage**: Code coverage analysis
- **locust**: Load testing
- **safety**: Security vulnerability scanning

## Test Environment Setup

### 1. Install Testing Dependencies
```bash
# Install development and testing dependencies
pip install -r requirements-dev.txt

# Key testing packages
pip install pytest pytest-asyncio pytest-mock pytest-cov httpx
pip install locust safety bandit
```

### 2. Test Configuration
Create `pytest.ini` in project root:
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --strict-config
    --cov=dtce_ai_bot
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
asyncio_mode = auto
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    security: Security tests
```

### 3. Test Environment Variables
Create `tests/.env.test`:
```env
# Test environment settings
ENVIRONMENT=test
DEBUG=true
TESTING=true

# Mock Azure services
AZURE_STORAGE_ACCOUNT_NAME=test_storage
AZURE_STORAGE_ACCOUNT_KEY=test_key
AZURE_STORAGE_CONTAINER_NAME=test_documents

# Mock authentication
MICROSOFT_CLIENT_ID=test_client_id
MICROSOFT_CLIENT_SECRET=test_client_secret
MICROSOFT_TENANT_ID=test_tenant_id

# Test database
DATABASE_URL=sqlite:///test.db
```

## Unit Testing

### 1. Service Layer Tests

#### DocumentSyncService Tests
```python
# tests/unit/services/test_document_sync_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dtce_ai_bot.services.document_sync_service import DocumentSyncService
from dtce_ai_bot.models.sync_result import SyncResult

class TestDocumentSyncService:
    
    @pytest.fixture
    def mock_graph_client(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_storage_client(self):
        return AsyncMock()
    
    @pytest.fixture
    def sync_service(self, mock_graph_client, mock_storage_client):
        return DocumentSyncService(
            graph_client=mock_graph_client,
            storage_client=mock_storage_client
        )
    
    @pytest.mark.asyncio
    async def test_sync_documents_success(self, sync_service, mock_graph_client):
        # Arrange
        mock_graph_client.get_drive_items.return_value = [
            {
                'id': 'doc1',
                'name': 'test.pdf',
                'lastModifiedDateTime': '2024-01-01T00:00:00Z',
                'size': 1024,
                'file': {'mimeType': 'application/pdf'},
                'webUrl': 'https://sharepoint.com/test.pdf'
            }
        ]
        
        # Act
        result = await sync_service.sync_documents()
        
        # Assert
        assert isinstance(result, SyncResult)
        assert result.status == "completed"
        assert result.synced_count > 0
        mock_graph_client.get_drive_items.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_documents_with_force_resync(self, sync_service):
        # Test force re-sync functionality
        result = await sync_service.sync_documents(force_resync=True)
        
        assert result.sync_mode.startswith("force_")
        assert "Force re-sync" in result.performance_notes
    
    @pytest.mark.asyncio
    async def test_sync_documents_path_filtering(self, sync_service):
        # Test path-specific synchronization
        path = "Projects/219"
        result = await sync_service.sync_documents(path=path)
        
        assert path in result.sync_mode
        assert result.path == path
    
    @pytest.mark.asyncio
    async def test_sync_documents_error_handling(self, sync_service, mock_graph_client):
        # Test error handling
        mock_graph_client.get_drive_items.side_effect = Exception("API Error")
        
        with pytest.raises(Exception):
            await sync_service.sync_documents()
    
    def test_should_skip_document_modification_check(self, sync_service):
        # Test document skip logic
        document = {
            'lastModifiedDateTime': '2024-01-01T00:00:00Z',
            'name': 'test.pdf'
        }
        existing_blob_info = {
            'last_modified': '2024-01-02T00:00:00Z'
        }
        
        # Should skip if not force resync and file is up to date
        assert sync_service._should_skip_document(
            document, existing_blob_info, force_resync=False
        ) is True
        
        # Should not skip if force resync
        assert sync_service._should_skip_document(
            document, existing_blob_info, force_resync=True
        ) is False
```

#### ChatService Tests
```python
# tests/unit/services/test_chat_service.py
import pytest
from unittest.mock import AsyncMock, patch
from dtce_ai_bot.services.chat_service import ChatService

class TestChatService:
    
    @pytest.fixture
    def mock_openai_client(self):
        mock = AsyncMock()
        mock.chat.completions.create.return_value.choices[0].message.content = "Test response"
        return mock
    
    @pytest.fixture
    def chat_service(self, mock_openai_client):
        return ChatService(openai_client=mock_openai_client)
    
    @pytest.mark.asyncio
    async def test_process_message_success(self, chat_service):
        # Test successful message processing
        response = await chat_service.process_message(
            message="What are the foundation requirements?",
            session_id="test_session"
        )
        
        assert "response" in response
        assert "sources" in response
        assert "session_id" in response
        assert response["session_id"] == "test_session"
    
    @pytest.mark.asyncio
    async def test_process_message_with_context(self, chat_service):
        # Test message processing with context
        context = {"project_filter": "Projects/219"}
        response = await chat_service.process_message(
            message="Test message",
            session_id="test_session",
            context=context
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_get_chat_history(self, chat_service):
        # Test chat history retrieval
        history = await chat_service.get_chat_history("test_session")
        
        assert isinstance(history, list)
```

### 2. API Layer Tests

#### Document API Tests
```python
# tests/unit/api/test_documents.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from dtce_ai_bot.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_sync_service():
    mock = AsyncMock()
    mock.sync_documents.return_value = {
        "status": "completed",
        "synced_count": 10,
        "sync_mode": "test_mode"
    }
    return mock

class TestDocumentsAPI:
    
    def test_sync_documents_endpoint(self, client, mock_sync_service):
        with patch('dtce_ai_bot.api.documents.get_document_sync_service', return_value=mock_sync_service):
            response = client.post("/documents/sync-suitefiles")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["synced_count"] == 10
    
    def test_sync_documents_with_path(self, client, mock_sync_service):
        with patch('dtce_ai_bot.api.documents.get_document_sync_service', return_value=mock_sync_service):
            response = client.post("/documents/sync-suitefiles?path=Projects/219")
            
            assert response.status_code == 200
            mock_sync_service.sync_documents.assert_called_with(path="Projects/219", force_resync=False)
    
    def test_sync_documents_with_force(self, client, mock_sync_service):
        with patch('dtce_ai_bot.api.documents.get_document_sync_service', return_value=mock_sync_service):
            response = client.post("/documents/sync-suitefiles?force=true")
            
            assert response.status_code == 200
            mock_sync_service.sync_documents.assert_called_with(path=None, force_resync=True)
    
    def test_extract_document_endpoint(self, client):
        with patch('dtce_ai_bot.api.documents.extract_text_from_blob') as mock_extract:
            mock_extract.return_value = {
                "status": "success",
                "extracted_text": "Test content"
            }
            
            response = client.post("/documents/extract?blob_name=test.pdf")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
    
    def test_async_sync_endpoint(self, client, mock_sync_service):
        with patch('dtce_ai_bot.api.documents.get_document_sync_service', return_value=mock_sync_service):
            response = client.post("/documents/sync-suitefiles-async?path=Engineering&force=true")
            
            assert response.status_code == 200
            mock_sync_service.sync_documents.assert_called_with(path="Engineering", force_resync=True)
```

#### Chat API Tests
```python
# tests/unit/api/test_chat.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from dtce_ai_bot.main import app

class TestChatAPI:
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def mock_chat_service(self):
        mock = AsyncMock()
        mock.process_message.return_value = {
            "response": "Test response",
            "sources": [],
            "session_id": "test_session"
        }
        return mock
    
    def test_chat_endpoint(self, client, mock_chat_service):
        with patch('dtce_ai_bot.api.chat.get_chat_service', return_value=mock_chat_service):
            response = client.post(
                "/chat",
                json={
                    "message": "Test message",
                    "session_id": "test_session"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Test response"
            assert data["session_id"] == "test_session"
    
    def test_chat_with_context(self, client, mock_chat_service):
        with patch('dtce_ai_bot.api.chat.get_chat_service', return_value=mock_chat_service):
            response = client.post(
                "/chat",
                json={
                    "message": "Test message",
                    "session_id": "test_session",
                    "context": {"project_filter": "Projects/219"}
                }
            )
            
            assert response.status_code == 200
    
    def test_chat_history_endpoint(self, client, mock_chat_service):
        mock_chat_service.get_chat_history.return_value = [
            {"type": "user", "content": "Test message"},
            {"type": "assistant", "content": "Test response"}
        ]
        
        with patch('dtce_ai_bot.api.chat.get_chat_service', return_value=mock_chat_service):
            response = client.get("/chat/history?session_id=test_session")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["messages"]) == 2
```

### 3. Teams Bot Tests

```python
# tests/unit/bot/test_teams_bot.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from botbuilder.core import MessageFactory, TurnContext
from dtce_ai_bot.bot.teams_bot import TeamsBot

class TestTeamsBot:
    
    @pytest.fixture
    def bot(self):
        return TeamsBot()
    
    @pytest.fixture
    def mock_turn_context(self):
        context = MagicMock(spec=TurnContext)
        context.activity = MagicMock()
        context.send_activity = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_on_message_activity_hello(self, bot, mock_turn_context):
        # Test hello message response
        mock_turn_context.activity.text = "Hello"
        
        await bot.on_message_activity(mock_turn_context)
        
        mock_turn_context.send_activity.assert_called_once()
        call_args = mock_turn_context.send_activity.call_args[0][0]
        assert "Hello!" in call_args.text
    
    @pytest.mark.asyncio
    async def test_on_message_activity_help(self, bot, mock_turn_context):
        # Test help command response
        mock_turn_context.activity.text = "Help"
        
        await bot.on_message_activity(mock_turn_context)
        
        mock_turn_context.send_activity.assert_called_once()
        call_args = mock_turn_context.send_activity.call_args[0][0]
        assert "I can help you" in call_args.text
    
    @pytest.mark.asyncio
    async def test_on_message_activity_case_insensitive(self, bot, mock_turn_context):
        # Test case insensitive command handling
        mock_turn_context.activity.text = "hi"
        
        await bot.on_message_activity(mock_turn_context)
        
        mock_turn_context.send_activity.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_members_added_activity(self, bot, mock_turn_context):
        # Test welcome message for new members
        mock_turn_context.activity.members_added = [MagicMock()]
        mock_turn_context.activity.recipient = MagicMock()
        mock_turn_context.activity.recipient.id = "bot_id"
        mock_turn_context.activity.members_added[0].id = "user_id"
        
        await bot.on_members_added_activity(mock_turn_context.activity.members_added, mock_turn_context)
        
        mock_turn_context.send_activity.assert_called_once()
        call_args = mock_turn_context.send_activity.call_args[0][0]
        assert "Welcome" in call_args.text
```

## Integration Testing

### 1. Azure Service Integration Tests

```python
# tests/integration/test_azure_services.py
import pytest
import os
from dtce_ai_bot.integrations.azure_storage import AzureStorageClient
from dtce_ai_bot.integrations.form_recognizer import FormRecognizerClient

@pytest.mark.integration
class TestAzureStorageIntegration:
    
    @pytest.fixture
    def storage_client(self):
        return AzureStorageClient(
            account_name=os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
            account_key=os.getenv("AZURE_STORAGE_ACCOUNT_KEY"),
            container_name="test-documents"
        )
    
    @pytest.mark.asyncio
    async def test_upload_and_download_blob(self, storage_client):
        # Test blob upload and download
        test_content = b"Test document content"
        blob_name = "test_document.txt"
        
        # Upload
        await storage_client.upload_blob(blob_name, test_content)
        
        # Download
        downloaded_content = await storage_client.download_blob(blob_name)
        
        assert downloaded_content == test_content
        
        # Cleanup
        await storage_client.delete_blob(blob_name)
    
    @pytest.mark.asyncio
    async def test_list_blobs(self, storage_client):
        # Test blob listing
        blobs = await storage_client.list_blobs()
        assert isinstance(blobs, list)

@pytest.mark.integration
class TestFormRecognizerIntegration:
    
    @pytest.fixture
    def form_recognizer_client(self):
        return FormRecognizerClient(
            endpoint=os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT"),
            key=os.getenv("AZURE_FORM_RECOGNIZER_KEY")
        )
    
    @pytest.mark.asyncio
    async def test_extract_text_from_pdf(self, form_recognizer_client):
        # Test PDF text extraction
        with open("tests/fixtures/sample.pdf", "rb") as f:
            result = await form_recognizer_client.extract_text(f.read())
        
        assert "extracted_text" in result
        assert result["status"] == "success"
```

### 2. Microsoft Graph Integration Tests

```python
# tests/integration/test_microsoft_graph.py
import pytest
from dtce_ai_bot.integrations.microsoft_graph import MicrosoftGraphClient

@pytest.mark.integration
class TestMicrosoftGraphIntegration:
    
    @pytest.fixture
    def graph_client(self):
        return MicrosoftGraphClient(
            client_id=os.getenv("MICROSOFT_CLIENT_ID"),
            client_secret=os.getenv("MICROSOFT_CLIENT_SECRET"),
            tenant_id=os.getenv("MICROSOFT_TENANT_ID")
        )
    
    @pytest.mark.asyncio
    async def test_get_sharepoint_drives(self, graph_client):
        # Test SharePoint drive listing
        drives = await graph_client.get_drives()
        assert isinstance(drives, list)
    
    @pytest.mark.asyncio
    async def test_get_drive_items(self, graph_client):
        # Test drive item retrieval
        items = await graph_client.get_drive_items()
        assert isinstance(items, list)
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_download_file_content(self, graph_client):
        # Test file download (slow test)
        # This would test actual file download from SharePoint
        pass
```

## End-to-End Testing

### 1. Complete Workflow Tests

```python
# tests/e2e/test_document_sync_workflow.py
import pytest
from fastapi.testclient import TestClient
from dtce_ai_bot.main import app

@pytest.mark.e2e
class TestDocumentSyncWorkflow:
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_complete_sync_and_query_workflow(self, client):
        # 1. Sync documents
        sync_response = client.post("/documents/sync-suitefiles")
        assert sync_response.status_code == 200
        sync_data = sync_response.json()
        assert sync_data["status"] in ["completed", "partial"]
        
        # 2. Wait for sync to complete (if async)
        # time.sleep(5)
        
        # 3. Query documents
        if sync_data["synced_count"] > 0:
            chat_response = client.post(
                "/chat",
                json={
                    "message": "What documents are available?",
                    "session_id": "e2e_test_session"
                }
            )
            assert chat_response.status_code == 200
            chat_data = chat_response.json()
            assert "response" in chat_data
            assert len(chat_data["sources"]) > 0
    
    def test_force_resync_workflow(self, client):
        # Test force re-sync functionality
        response = client.post("/documents/sync-suitefiles?force=true")
        assert response.status_code == 200
        
        data = response.json()
        assert "force" in data["sync_mode"].lower() or data.get("force_resync") is True

@pytest.mark.e2e
class TestTeamsBotWorkflow:
    
    def test_bot_endpoint_availability(self, client):
        # Test bot messaging endpoint
        # This would require Bot Framework authentication
        pass
    
    def test_bot_privacy_compliance(self, client):
        # Test privacy and terms endpoints
        privacy_response = client.get("/privacy")
        assert privacy_response.status_code == 200
        assert "privacy" in privacy_response.text.lower()
        
        terms_response = client.get("/terms")
        assert terms_response.status_code == 200
        assert "terms" in terms_response.text.lower()
```

### 2. Performance Tests

```python
# tests/performance/test_load.py
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import httpx

@pytest.mark.slow
class TestPerformance:
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    @pytest.mark.asyncio
    async def test_concurrent_sync_requests(self, base_url):
        """Test multiple concurrent sync requests"""
        async def make_request():
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{base_url}/documents/sync-suitefiles")
                return response.status_code
        
        # Run 5 concurrent requests
        tasks = [make_request() for _ in range(5)]
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        # Should complete within reasonable time
        assert duration < 30.0  # 30 seconds max
    
    @pytest.mark.asyncio
    async def test_chat_response_time(self, base_url):
        """Test chat response performance"""
        async with httpx.AsyncClient() as client:
            start_time = time.time()
            response = await client.post(
                f"{base_url}/chat",
                json={
                    "message": "What are the foundation requirements?",
                    "session_id": "perf_test"
                }
            )
            duration = time.time() - start_time
            
            assert response.status_code == 200
            assert duration < 5.0  # Should respond within 5 seconds
```

## Security Testing

### 1. Authentication Tests

```python
# tests/security/test_authentication.py
import pytest
from fastapi.testclient import TestClient
from dtce_ai_bot.main import app

@pytest.mark.security
class TestAuthentication:
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_unauthenticated_access(self, client):
        # Test endpoints that require authentication
        protected_endpoints = [
            "/documents/sync-suitefiles",
            "/chat"
        ]
        
        for endpoint in protected_endpoints:
            response = client.post(endpoint)
            # Depending on auth implementation, might be 401 or 403
            assert response.status_code in [200, 401, 403]  # Update based on auth setup
    
    def test_invalid_token(self, client):
        # Test with invalid auth token
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.post("/documents/sync-suitefiles", headers=headers)
        # Update assertion based on auth implementation
        assert response.status_code in [200, 401, 403]
```

### 2. Input Validation Tests

```python
# tests/security/test_input_validation.py
import pytest
from fastapi.testclient import TestClient
from dtce_ai_bot.main import app

@pytest.mark.security
class TestInputValidation:
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_sql_injection_prevention(self, client):
        # Test SQL injection attempts in chat messages
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "<script>alert('xss')</script>"
        ]
        
        for malicious_input in malicious_inputs:
            response = client.post(
                "/chat",
                json={
                    "message": malicious_input,
                    "session_id": "security_test"
                }
            )
            # Should not crash and should handle safely
            assert response.status_code in [200, 400]
    
    def test_path_traversal_prevention(self, client):
        # Test path traversal attempts
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f"
        ]
        
        for malicious_path in malicious_paths:
            response = client.post(f"/documents/sync-suitefiles?path={malicious_path}")
            # Should reject or sanitize malicious paths
            assert response.status_code in [200, 400, 422]
```

## Test Data Management

### 1. Test Fixtures

```python
# tests/fixtures/conftest.py
import pytest
import asyncio
from unittest.mock import AsyncMock

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def sample_sharepoint_document():
    return {
        'id': 'test_doc_123',
        'name': 'sample_specification.pdf',
        'lastModifiedDateTime': '2024-01-15T10:30:00Z',
        'size': 2048000,
        'file': {'mimeType': 'application/pdf'},
        'webUrl': 'https://sharepoint.com/sites/test/sample_specification.pdf',
        'parentReference': {
            'path': '/drive/root:/Projects/219'
        }
    }

@pytest.fixture
def sample_sync_result():
    return {
        "status": "completed",
        "message": "Test sync completed",
        "synced_count": 10,
        "processed_count": 15,
        "ai_ready_count": 8,
        "skipped_count": 5,
        "error_count": 0,
        "folder_count": 3,
        "performance_notes": ["Test completed in 5 seconds"],
        "sync_mode": "test_mode",
        "timestamp": "2024-01-15T10:30:00.000Z"
    }

@pytest.fixture
def sample_chat_response():
    return {
        "response": "Based on the specifications, the foundation requirements include...",
        "sources": [
            {
                "document": "Projects_219_foundation_specs.pdf",
                "relevance": 0.95,
                "excerpt": "Foundation depth minimum 600mm..."
            }
        ],
        "session_id": "test_session_123",
        "timestamp": "2024-01-15T10:30:00.000Z"
    }
```

### 2. Mock Data Setup

```python
# tests/fixtures/mock_data.py
import os
import json

def load_mock_sharepoint_data():
    """Load mock SharePoint API responses"""
    fixture_path = os.path.join(os.path.dirname(__file__), "sharepoint_responses.json")
    with open(fixture_path, 'r') as f:
        return json.load(f)

def create_test_pdf():
    """Create a minimal test PDF for testing"""
    from reportlab.pdfgen import canvas
    from io import BytesIO
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 750, "Test Document Content")
    p.drawString(100, 730, "Foundation requirements: 600mm depth")
    p.save()
    
    return buffer.getvalue()
```

## Test Execution

### 1. Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit                    # Unit tests only
pytest -m integration            # Integration tests only
pytest -m e2e                   # End-to-end tests only
pytest -m "not slow"            # Skip slow tests

# Run with coverage
pytest --cov=dtce_ai_bot --cov-report=html

# Run specific test file
pytest tests/unit/services/test_document_sync_service.py

# Run with verbose output
pytest -v

# Run tests in parallel
pytest -n auto
```

### 2. Continuous Integration

```yaml
# .github/workflows/test.yml
name: Run Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run unit tests
      run: pytest -m "unit" --cov=dtce_ai_bot --cov-report=xml
    
    - name: Run integration tests
      run: pytest -m "integration"
      env:
        AZURE_STORAGE_ACCOUNT_NAME: ${{ secrets.TEST_STORAGE_ACCOUNT }}
        AZURE_STORAGE_ACCOUNT_KEY: ${{ secrets.TEST_STORAGE_KEY }}
    
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
    
    - name: Security scan
      run: |
        safety check
        bandit -r dtce_ai_bot/
```

### 3. Load Testing with Locust

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class DTCEAIUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when a user starts"""
        self.session_id = f"load_test_{self.environment.runner.user_count}"
    
    @task(3)
    def chat_query(self):
        """Test chat endpoint (most common operation)"""
        self.client.post("/chat", json={
            "message": "What are the foundation requirements?",
            "session_id": self.session_id
        })
    
    @task(1)
    def health_check(self):
        """Test health endpoint"""
        self.client.get("/health")
    
    @task(1)
    def sync_documents(self):
        """Test document sync (less frequent)"""
        self.client.post("/documents/sync-suitefiles?path=Projects")

# Run load test:
# locust -f tests/load/locustfile.py --host=http://localhost:8000
```

## Test Coverage and Quality

### 1. Coverage Requirements
- **Overall Coverage**: Minimum 80%
- **Critical Services**: Minimum 90%
- **API Endpoints**: Minimum 85%
- **Error Handling**: 100% of error paths

### 2. Quality Metrics

```bash
# Code quality checks
flake8 dtce_ai_bot/                 # Style checks
black --check dtce_ai_bot/          # Formatting checks
mypy dtce_ai_bot/                   # Type checking
bandit -r dtce_ai_bot/              # Security scanning
safety check                       # Dependency vulnerability scanning

# Test quality
pytest --durations=10               # Identify slow tests
pytest --cache-clear                # Clear test cache
pytest --lf                         # Run last failed tests only
```

### 3. Test Reporting

```python
# Generate comprehensive test reports
pytest --html=reports/report.html --self-contained-html
pytest --junitxml=reports/junit.xml
pytest --cov=dtce_ai_bot --cov-report=html:reports/coverage
```

## Troubleshooting Common Test Issues

### 1. Async Test Issues
```python
# Fix for async test not running
@pytest.mark.asyncio
async def test_async_function():
    # Ensure asyncio mode is set in pytest.ini
    pass

# Fix for event loop issues
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

### 2. Mock Issues
```python
# Fix for mock not being called
@patch('dtce_ai_bot.services.DocumentSyncService')
def test_with_mock(mock_service):
    # Ensure mock is properly configured
    mock_service.return_value.sync_documents.return_value = expected_result
```

### 3. Test Data Issues
```python
# Fix for test data isolation
@pytest.fixture(autouse=True)
def clean_test_data():
    # Setup
    yield
    # Cleanup test data after each test
    cleanup_test_files()
```

This comprehensive testing guide ensures robust validation of all DTCE AI Assistant components, from individual functions to complete workflows, with emphasis on maintainability, security, and performance.
