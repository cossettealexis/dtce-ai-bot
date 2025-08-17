# DTCE AI Assistant

An intelligent AI assistant for DTCE engineering teams, providing comprehensive document analysis, project scoping, and engineering guidance with advanced SharePoint integration and Microsoft Teams bot capabilities.

## 🚀 Features

### Core Capabilities
- 🤖 **Microsoft Teams Bot Integration**: Seamless Teams app with validation compliance
- 📄 **Advanced Document Q&A**: AI-powered question answering from engineering documents
- 🏗️ **Project Scoping**: Analyze new projects and find similar past projects
- ⚠️ **Risk Analysis**: Identify potential issues based on past experience
- 🔍 **Similarity Matching**: Find relevant past projects for reference
- 📋 **Design Philosophy**: Generate design recommendations based on experience

### Document Management
- 📁 **SharePoint Integration**: Direct sync with Microsoft SharePoint/Suitefiles
- 🔄 **Real-time Sync**: Both standard and async document synchronization
- 💾 **Azure Blob Storage**: Secure document storage and retrieval
- 🔍 **Azure Form Recognizer**: Advanced text extraction from PDFs and images
- 📝 **PyPDF2 Fallback**: Robust document processing for large files
- ⚡ **Force Re-sync**: Complete folder re-processing capabilities

### Teams Integration
- ✅ **Teams App Store Compliant**: Schema v1.17 with full validation
- 🛡️ **Privacy & Terms**: Dedicated compliance endpoints
- 💬 **Enhanced Bot Commands**: Hi, Hello, Help, and comprehensive command support
- 🔐 **Secure Authentication**: Microsoft Graph API integration
- 📱 **Mobile Ready**: Optimized for Teams mobile and desktop

## 🏗️ Architecture

### Code Architecture Principles
Following **SOLID principles** throughout the codebase:
- **Single Responsibility**: Each service handles one specific concern
- **Open/Closed**: Extensible design without modifying existing code
- **Liskov Substitution**: Proper inheritance and interface implementation
- **Interface Segregation**: Focused, specific interfaces
- **Dependency Inversion**: Abstractions over concrete implementations

### Service Layer Design
```
dtce_ai_bot/
├── services/              # Business logic layer
│   ├── document_sync_service.py    # SharePoint sync orchestration
│   ├── ai_service.py              # AI/ML operations
│   └── chat_service.py            # Conversation management
├── integrations/          # External service integrations
│   ├── microsoft_graph.py         # SharePoint/Graph API
│   ├── azure_storage.py           # Blob storage operations
│   └── azure_form_recognizer.py   # Document text extraction
├── bot/                   # Teams bot implementation
│   ├── teams_bot.py              # Core bot logic
│   └── endpoints.py              # Bot API endpoints
├── api/                   # REST API layer
│   ├── documents.py              # Document management endpoints
│   └── chat.py                   # Chat/Q&A endpoints
└── core/                  # Application foundation
    ├── app.py                    # FastAPI application setup
    ├── dependencies.py           # Dependency injection
    └── middleware.py             # Request/response middleware
```

## 🚀 Quick Start

### Prerequisites
- **Python 3.9+** with pip and venv
- **Azure Subscription** with admin access
- **Microsoft 365 Tenant** with SharePoint access
- **Git** for version control
- **VS Code** (recommended) with Python extension

### 🔧 Complete Setup Guide

#### 1. Clone and Environment Setup
```bash
# Clone the repository
git clone https://github.com/cossettealexis/dtce-ai-bot.git
cd dtce-ai-bot

# Create and activate virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 2. Azure Services Setup

##### 2.1 Azure Storage Account
```bash
# Create resource group (if needed)
az group create --name dtce-ai-rg --location "East US"

# Create storage account
az storage account create \
  --name dtceaidocuments \
  --resource-group dtce-ai-rg \
  --location "East US" \
  --sku Standard_LRS

# Create container for documents
az storage container create \
  --name documents \
  --account-name dtceaidocuments
```

##### 2.2 Azure Form Recognizer
```bash
# Create Form Recognizer service
az cognitiveservices account create \
  --name dtce-form-recognizer \
  --resource-group dtce-ai-rg \
  --kind FormRecognizer \
  --sku S0 \
  --location "East US"
```

##### 2.3 Azure App Registration
```bash
# Create app registration for Microsoft Graph API
az ad app create \
  --display-name "DTCE AI Assistant" \
  --sign-in-audience AzureADMyOrg \
  --required-resource-accesses '[
    {
      "resourceAppId": "00000003-0000-0000-c000-000000000000",
      "resourceAccess": [
        {
          "id": "Sites.ReadWrite.All",
          "type": "Role"
        },
        {
          "id": "Files.ReadWrite.All", 
          "type": "Role"
        }
      ]
    }
  ]'
```

#### 3. Environment Configuration

##### 3.1 Create Environment File
```bash
# Copy the example environment file
cp .env.example .env
```

##### 3.2 Configure Environment Variables
Edit `.env` file with your Azure credentials:

```bash
# =============================================================================
# DTCE AI Assistant Configuration
# =============================================================================

# Application Settings
APP_NAME=DTCE AI Assistant
APP_VERSION=1.2.0
DEBUG=true
LOG_LEVEL=INFO

# Azure Storage Configuration
AZURE_STORAGE_ACCOUNT_NAME=dtceaidocuments
AZURE_STORAGE_ACCOUNT_KEY=your_storage_account_key_here
AZURE_STORAGE_CONTAINER=documents
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=dtceaidocuments;AccountKey=your_key;EndpointSuffix=core.windows.net

# Azure Form Recognizer
AZURE_FORM_RECOGNIZER_ENDPOINT=https://dtce-form-recognizer.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_KEY=your_form_recognizer_key_here

# Microsoft Graph API Configuration
AZURE_CLIENT_ID=your_app_client_id_here
AZURE_CLIENT_SECRET=your_app_client_secret_here
AZURE_TENANT_ID=your_tenant_id_here

# SharePoint Configuration  
SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/yoursite
SHAREPOINT_SITE_ID=your_site_id_here
SHAREPOINT_DRIVE_ID=your_drive_id_here

# Microsoft Teams Bot Configuration
MICROSOFT_APP_ID=your_bot_app_id_here
MICROSOFT_APP_PASSWORD=your_bot_app_password_here
BOT_ENDPOINT=https://your-bot-url.azurewebsites.net/api/teams

# Database Configuration (Optional)
DATABASE_URL=sqlite:///./dtce_ai.db

# AI/ML Configuration
OPENAI_API_KEY=your_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_KEY=your_azure_openai_key_here

# Security
SECRET_KEY=your_super_secret_key_here_minimum_32_characters
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
```

#### 4. Get Required Azure Values

##### 4.1 Storage Account Key
```bash
az storage account keys list \
  --account-name dtceaidocuments \
  --resource-group dtce-ai-rg \
  --query "[0].value" -o tsv
```

##### 4.2 Form Recognizer Key
```bash
az cognitiveservices account keys list \
  --name dtce-form-recognizer \
  --resource-group dtce-ai-rg \
  --query "key1" -o tsv
```

##### 4.3 App Registration Details
```bash
# Get client ID
az ad app list --display-name "DTCE AI Assistant" --query "[0].appId" -o tsv

# Get tenant ID  
az account show --query "tenantId" -o tsv
```

#### 5. SharePoint Configuration

##### 5.1 Find SharePoint Site ID
```python
# Run this Python script to get SharePoint details
python -c "
import requests
from dtce_ai_bot.integrations.microsoft_graph import MicrosoftGraphClient

# Initialize Graph client
graph = MicrosoftGraphClient()
sites = graph.get_sites()
print('Available SharePoint sites:')
for site in sites:
    print(f'  - {site[\"displayName\"]}: {site[\"id\"]}')
"
```

##### 5.2 Test SharePoint Connection
```bash
# Test SharePoint access
python -c "
from dtce_ai_bot.integrations.microsoft_graph import MicrosoftGraphClient
client = MicrosoftGraphClient()
drives = client.get_drives()
print(f'Found {len(drives)} drives in SharePoint')
"
```

#### 6. Local Development Server

##### 6.1 Run the Application
```bash
# Start the development server
python -m uvicorn dtce_ai_bot.core.app:app --reload --host 0.0.0.0 --port 8000

# Or use the provided script
./scripts/run_dev.sh
```

##### 6.2 Verify Installation
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test API documentation
open http://localhost:8000/docs

# Test document sync
curl -X POST "http://localhost:8000/documents/sync-suitefiles?force=true"
```

#### 7. Teams Bot Setup (Optional)

##### 7.1 Register Bot in Azure
```bash
# Create Bot Framework registration
az bot create \
  --resource-group dtce-ai-rg \
  --name dtce-ai-bot \
  --kind webapp \
  --version v4 \
  --lang python \
  --verbose \
  --appid your_app_id_here \
  --password your_app_password_here \
  --endpoint https://your-bot-url.azurewebsites.net/api/teams
```

##### 7.2 Configure Teams App
```bash
# Use the pre-built Teams package
cd teams-package
# Upload dtce-ai-bot-v1.2.0.zip to Teams Admin Center
```

### 🧪 Testing Setup

#### Run Tests
```bash
# Install test dependencies
pip install pytest pytest-cov pytest-asyncio

# Run all tests
pytest

# Run with coverage
pytest --cov=dtce_ai_bot --cov-report=html

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/test_teams_bot.py
```

### 🚀 Production Deployment

#### Azure App Service Deployment
```bash
# Create App Service plan
az appservice plan create \
  --name dtce-ai-plan \
  --resource-group dtce-ai-rg \
  --sku B1 \
  --is-linux

# Create Web App
az webapp create \
  --resource-group dtce-ai-rg \
  --plan dtce-ai-plan \
  --name dtce-ai-assistant \
  --runtime "PYTHON|3.9"

# Configure deployment from GitHub
az webapp deployment source config \
  --name dtce-ai-assistant \
  --resource-group dtce-ai-rg \
  --repo-url https://github.com/cossettealexis/dtce-ai-bot \
  --branch main \
  --manual-integration
```

### 🔍 Troubleshooting Setup

#### Common Issues

1. **Python Virtual Environment**
   ```bash
   # If activation fails, try:
   python -m venv --clear .venv
   source .venv/bin/activate
   pip install --upgrade pip setuptools wheel
   ```

2. **Azure Authentication**
   ```bash
   # Login to Azure CLI
   az login
   az account set --subscription "your-subscription-name"
   ```

3. **SharePoint Permissions**
   ```bash
   # Grant admin consent for app permissions
   az ad app permission admin-consent --id your_app_id_here
   ```

4. **Environment Variables**
   ```bash
   # Verify environment is loaded
   python -c "
   from dtce_ai_bot.config.settings import get_settings
   settings = get_settings()
   print(f'Storage Account: {settings.azure_storage_account_name}')
   print(f'Client ID: {settings.azure_client_id}')
   "
   ```

5. **Port Conflicts**
   ```bash
   # If port 8000 is in use
   python -m uvicorn dtce_ai_bot.core.app:app --reload --port 8001
   ```

### 📋 Setup Verification Checklist

- [ ] Python 3.9+ installed and virtual environment activated
- [ ] All dependencies installed via `pip install -r requirements.txt`
- [ ] Azure Storage Account created and accessible
- [ ] Azure Form Recognizer service configured
- [ ] App Registration created with correct permissions
- [ ] Environment variables configured in `.env`
- [ ] SharePoint site accessible and Site ID obtained
- [ ] Health endpoint returns 200: `curl http://localhost:8000/health`
- [ ] API documentation accessible: `http://localhost:8000/docs`
- [ ] Document sync test successful
- [ ] Tests pass: `pytest`
- [ ] Teams app package ready for deployment (optional)

## 📚 API Documentation

### Core Endpoints

#### Document Management
- **GET** `/docs` - Interactive API documentation
- **GET** `/health` - Health check endpoint
- **POST** `/documents/sync-suitefiles` - Standard document sync
- **POST** `/documents/sync-suitefiles-async` - Async document sync with force option
- **GET** `/documents/search` - Search synchronized documents
- **POST** `/documents/extract` - Extract text from specific document

#### Chat & Q&A
- **POST** `/chat` - Ask questions about documents
- **GET** `/chat/history` - Retrieve chat history
- **POST** `/projects/scope` - Project scoping analysis

#### Teams Bot
- **POST** `/api/teams/messages` - Teams bot message handler
- **GET** `/privacy` - Privacy policy (Teams compliance)
- **GET** `/terms` - Terms of use (Teams compliance)

### Advanced Sync Options

#### Force Re-sync
Process all documents regardless of modification dates:
```bash
# Force re-sync all documents
curl -X POST "http://localhost:8000/documents/sync-suitefiles-async?force=true"

# Force re-sync specific path
curl -X POST "http://localhost:8000/documents/sync-suitefiles-async?path=Clients/&force=true"
```

#### Path-based Sync
Sync specific SharePoint folders:
```bash
# Sync specific project
curl -X POST "http://localhost:8000/documents/sync-suitefiles?path=Projects/219"

# Sync engineering documents
curl -X POST "http://localhost:8000/documents/sync-suitefiles?path=Engineering/Marketing"
```

## 🏗️ Project Structure

```
dtce-ai-bot/
├── dtce_ai_bot/           # Main application package
│   ├── api/               # REST API endpoints
│   │   ├── documents.py   # Document sync and management
│   │   └── chat.py        # Chat and Q&A endpoints
│   ├── bot/               # Microsoft Teams bot
│   │   ├── teams_bot.py   # Core bot message handling
│   │   └── endpoints.py   # Bot API routes
│   ├── core/              # Application foundation
│   │   ├── app.py         # FastAPI application setup
│   │   ├── dependencies.py # Dependency injection
│   │   └── middleware.py  # Custom middleware
│   ├── services/          # Business logic layer
│   │   ├── document_sync_service.py # SharePoint sync orchestration
│   │   ├── ai_service.py  # AI/ML operations
│   │   └── chat_service.py # Conversation management
│   ├── integrations/      # External service integrations
│   │   ├── microsoft_graph.py # SharePoint/Graph API client
│   │   ├── azure_storage.py # Blob storage operations
│   │   └── azure_form_recognizer.py # Document processing
│   └── config/            # Configuration management
│       └── settings.py    # Environment configuration
├── teams/                 # Teams app development files
│   ├── manifest.json      # Teams app manifest
│   └── icons/             # App icons
├── teams-package/         # Deployable Teams app packages
│   ├── dtce-ai-bot-v1.2.0.zip # Latest Teams app package
│   └── manifest.json      # Production manifest
├── tests/                 # Comprehensive test suite
│   ├── unit/              # Unit tests following SOLID principles
│   ├── integration/       # Integration tests
│   └── test_teams_bot.py  # Teams bot validation tests
├── deployment/            # Deployment and infrastructure
│   ├── azure/             # Azure deployment templates
│   └── docs/              # Deployment documentation
└── docs/                  # Project documentation
    ├── api/               # API documentation
    ├── architecture/      # System architecture docs
    └── teams/             # Teams app documentation
```

## 🔧 Development Guidelines

### Code Quality Standards
- **Unit Testing**: Comprehensive test coverage for all components
- **SOLID Principles**: Maintained throughout the codebase architecture
- **Type Hints**: Full Python type annotations for better code clarity
- **Documentation**: Detailed docstrings and inline comments
- **Error Handling**: Robust exception handling and logging

### Testing Strategy
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests
pytest tests/test_teams_bot.py # Teams bot tests

# Run with coverage
pytest --cov=dtce_ai_bot
```

### Deployment
- **Azure App Service**: Automatic deployment via GitHub Actions
- **Teams App Store**: Compliant packages ready for validation
- **Environment Management**: Separate dev/staging/production configurations

## 📋 Teams App Deployment

### Current Status
- ✅ **Schema v1.17 Compliant**: Latest Teams manifest standard
- ✅ **Validation Ready**: All bot commands (Hi, Hello, Help) working
- ✅ **Privacy & Terms**: Compliance endpoints deployed
- ✅ **Production Ready**: Package `dtce-ai-bot-v1.2.0.zip` available

### Deployment Steps
1. Upload `teams-package/dtce-ai-bot-v1.2.0.zip` to Teams Admin Center
2. Configure bot permissions in Azure AD
3. Validate all endpoints are accessible
4. Submit for Teams app store approval

## 🚨 Troubleshooting

### Common Issues
- **SharePoint Access**: Ensure Graph API permissions are properly configured
- **Document Sync**: Use force re-sync for complete folder processing
- **Teams Bot**: Verify bot framework registration matches manifest
- **Azure Services**: Check all Azure service endpoints and keys

### Debug Mode
Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
python -m uvicorn dtce_ai_bot.core.app:app --reload
```

## 🤝 Contributing

1. Follow SOLID principles in all new code
2. Write comprehensive unit tests for new features
3. Update documentation for API changes
4. Ensure Teams app compliance for bot modifications

## 📞 Support

For issues or questions, refer to:
- `/docs/api/` - Detailed API documentation
- `/tests/` - Test examples and patterns
- `/deployment/docs/` - Deployment guides
