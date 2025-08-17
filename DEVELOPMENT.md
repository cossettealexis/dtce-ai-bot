# DTCE AI Assistant - Development Guide

## Development Workflow

### Getting Started
1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd dtce-ai-bot
   ./scripts/setup_dev.sh
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Azure credentials
   ```

3. **Run Development Server**
   ```bash
   ./scripts/run_dev.sh
   ```

### Architecture Overview

#### Service Layer Architecture
The application follows SOLID principles with a clean service layer architecture:

```
├── app.py                 # Main Flask application entry point
├── src/
│   ├── services/          # Business logic layer
│   │   ├── document_service.py    # Document processing and storage
│   │   ├── sync_service.py        # SharePoint synchronization
│   │   └── bot_service.py         # Teams bot interactions
│   ├── utils/             # Utility functions
│   │   ├── azure_storage.py       # Azure Blob Storage operations
│   │   ├── form_recognizer.py     # Document OCR processing
│   │   └── sharepoint_client.py   # Microsoft Graph API client
│   └── models/            # Data models and schemas
└── static/                # Static web assets
```

#### Key Design Principles

1. **Single Responsibility Principle (SRP)**
   - Each service handles one specific domain
   - Document processing separated from synchronization
   - Bot logic isolated from business logic

2. **Dependency Inversion Principle (DIP)**
   - Services depend on abstractions, not implementations
   - Easy to mock for testing
   - Configurable through environment variables

3. **Open/Closed Principle (OCP)**
   - New document processors can be added without modifying existing code
   - Bot commands extensible through configuration

### API Endpoints

#### Document Management
- `POST /upload` - Upload documents to Azure Storage
- `GET /documents` - List stored documents
- `POST /process` - Process documents with Form Recognizer
- `DELETE /documents/<id>` - Remove documents

#### SharePoint Synchronization
- `POST /sync` - Sync SharePoint documents
- `POST /sync?force=true` - Force complete re-sync
- `GET /sync/status` - Get synchronization status

#### Teams Bot Integration
- `POST /api/messages` - Teams bot message endpoint
- `GET /privacy` - Privacy policy (Teams compliance)
- `GET /terms` - Terms of service (Teams compliance)

### Testing Strategy

#### Unit Tests
Each service should have comprehensive unit tests:

```python
# Example: test_document_service.py
import pytest
from unittest.mock import Mock, patch
from src.services.document_service import DocumentService

class TestDocumentService:
    def test_upload_document_success(self):
        # Test successful document upload
        pass
    
    def test_process_document_with_form_recognizer(self):
        # Test document processing
        pass
```

#### Integration Tests
Test service interactions:

```python
# Example: test_sync_integration.py
class TestSyncIntegration:
    def test_sharepoint_to_storage_sync(self):
        # Test complete sync workflow
        pass
```

### Debugging and Troubleshooting

#### Common Issues

1. **"No documents found to sync"**
   - Use force sync: `POST /sync?force=true`
   - Check SharePoint permissions
   - Verify folder structure

2. **Teams Bot Not Responding**
   - Check bot endpoint registration
   - Verify ngrok tunnel (development)
   - Validate manifest.json

3. **Form Recognizer Errors**
   - Check document format support
   - Verify Azure quota limits
   - Ensure proper authentication

#### Logging
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Deployment

#### Azure App Service
1. **Create App Service**
   ```bash
   az webapp create --resource-group dtce-ai-rg --plan dtce-plan --name dtce-ai-assistant --runtime "PYTHON|3.9"
   ```

2. **Configure Deployment**
   ```bash
   az webapp deployment source config --name dtce-ai-assistant --resource-group dtce-ai-rg --repo-url <github-url> --branch main
   ```

3. **Set Environment Variables**
   ```bash
   az webapp config appsettings set --name dtce-ai-assistant --resource-group dtce-ai-rg --settings @appsettings.json
   ```

#### Environment Variables
All required environment variables are documented in `.env.example`.

### Code Quality

#### Code Style
- Follow PEP 8 guidelines
- Use type hints where possible
- Document functions with docstrings

#### Pre-commit Hooks
```bash
pip install pre-commit
pre-commit install
```

#### Linting
```bash
flake8 src/
black src/
isort src/
```

### Contributing

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Write Tests**
   - Add unit tests for new functionality
   - Ensure existing tests pass

3. **Code Review**
   - Submit pull request
   - Address review feedback

4. **Deploy**
   - Merge to main branch
   - Automatic deployment via GitHub Actions

### Performance Optimization

#### Document Processing
- Use async processing for large documents
- Implement caching for processed results
- Batch operations where possible

#### Storage Optimization
- Use blob storage tiers appropriately
- Implement lifecycle policies
- Monitor storage costs

### Security Considerations

#### Authentication
- Use Azure AD for authentication
- Implement proper token validation
- Rotate keys regularly

#### Data Protection
- Encrypt data at rest and in transit
- Implement proper access controls
- Regular security audits

### Monitoring and Observability

#### Application Insights
```python
from applicationinsights import TelemetryClient
tc = TelemetryClient(instrumentation_key)
tc.track_event('DocumentProcessed', {'document_id': doc_id})
```

#### Health Checks
Implement health check endpoints:
```python
@app.route('/health')
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}
```

### Future Enhancements

#### Planned Features
- Advanced document search capabilities
- Machine learning-based document classification
- Real-time collaboration features
- Mobile application support

#### Technical Debt
- Migrate to async/await patterns
- Implement proper caching layer
- Add comprehensive error handling
- Improve test coverage

For more information, see the main [README.md](../README.md) file.
