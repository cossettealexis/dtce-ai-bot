# DTCE AI Assistant - Project Information

## 📋 Project Overview

**DTCE AI Assistant** is an intelligent AI assistant for DTCE engineering teams, providing comprehensive document analysis, project scoping, and engineering guidance with advanced SharePoint integration and Microsoft Teams bot capabilities.

## 🔗 Repository Information

### Primary Repository
- **Azure Repository**: `https://dtceai-backend-cyashrb8hnc2ayhp.scm.newzealandnorth-01.azurewebsites.net:443/dtceai-backend.git`
- **Branch**: `main`
- **Deployment**: Automatic deployment to Azure App Service

### Clone Instructions
```bash
# Clone the repository
git clone https://dtceai-backend-cyashrb8hnc2ayhp.scm.newzealandnorth-01.azurewebsites.net:443/dtceai-backend.git
cd dtceai-backend

# Setup development environment
./scripts/setup_dev.sh

# Run development server
./scripts/run_dev.sh
```

## 🚀 Deployment Information

### Production Environment
- **Azure App Service**: `dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net`
- **Azure Resource Group**: `dtce-ai-rg`
- **Azure Region**: `New Zealand North`

### Teams Application
- **Package Version**: `v1.2.0`
- **Manifest Schema**: `v1.17`
- **Package Location**: `teams-package/dtce-ai-bot-v1.2.0.zip`

### API Endpoints (Production)
- **Base URL**: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net`
- **API Documentation**: `/docs`
- **Health Check**: `/health`
- **Privacy Policy**: `/privacy`
- **Terms of Use**: `/terms`

### Key Features Deployed
- ✅ **Document Sync**: Both standard and async with force re-sync capability
- ✅ **Teams Bot**: Full validation compliance with Hi/Hello/Help commands
- ✅ **SharePoint Integration**: Complete folder structure processing
- ✅ **Azure Form Recognizer**: Advanced document text extraction
- ✅ **Privacy & Terms**: Compliance endpoints for Teams app store

## 📁 Project Structure

```
dtceai-backend/
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
│   ├── services/          # Business logic layer (SOLID principles)
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
├── teams-package/         # Deployable Teams app packages
│   └── dtce-ai-bot-v1.2.0.zip # Current production package
├── tests/                 # Comprehensive test suite
│   ├── unit/              # Unit tests following SOLID principles
│   ├── integration/       # Integration tests
│   └── test_teams_bot.py  # Teams bot validation tests
├── scripts/               # Setup and automation scripts
│   ├── setup_dev.sh       # Development environment setup
│   ├── run_dev.sh         # Development server runner
│   └── setup_azure.sh     # Azure resource creation
├── docs/                  # Comprehensive documentation
│   ├── DEVELOPMENT.md     # Development guidelines
│   ├── deployment/        # Deployment procedures
│   ├── api/               # API documentation
│   └── architecture/      # System architecture
└── deployment/            # Infrastructure and deployment configs
```

## 🔧 Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Python 3.11**: Latest stable Python version
- **Pydantic**: Data validation and settings management
- **SQLAlchemy**: Database ORM (when needed)

### Azure Services
- **Azure App Service**: Application hosting
- **Azure Blob Storage**: Document storage
- **Azure Form Recognizer**: Document text extraction
- **Azure AD**: Authentication and authorization
- **Microsoft Graph API**: SharePoint integration

### Microsoft Integrations
- **Microsoft Teams**: Bot platform
- **SharePoint**: Document management
- **Office 365**: Document processing

### Development & Testing
- **pytest**: Testing framework
- **Black**: Code formatting
- **isort**: Import sorting
- **mypy**: Type checking
- **flake8**: Code linting

## 📋 Architecture Principles

### SOLID Principles Implementation
- **Single Responsibility**: Each service handles one specific concern
- **Open/Closed**: Extensible design without modifying existing code
- **Liskov Substitution**: Proper inheritance and interface implementation
- **Interface Segregation**: Focused, specific interfaces
- **Dependency Inversion**: Abstractions over concrete implementations

### Design Patterns
- **Dependency Injection**: Clean separation of concerns
- **Service Layer**: Business logic isolation
- **Repository Pattern**: Data access abstraction
- **Factory Pattern**: Object creation management

## 🚀 Recent Updates (v1.2.0)

### Force Re-sync Implementation
- Added `force` parameter to both sync endpoints
- Enables complete re-processing of documents regardless of modification dates
- Improved handling of nested folder structures

### Teams App Compliance
- Updated to Teams manifest schema v1.17
- Enhanced bot command handling (Hi, Hello, Help)
- Added privacy and terms compliance endpoints
- Full validation ready for Teams app store

### Documentation Enhancement
- Comprehensive setup instructions with Azure CLI commands
- Automated setup scripts for development environment
- Architecture documentation following SOLID principles
- Deployment procedures and troubleshooting guides

## 🤝 Development Workflow

### Getting Started
1. Clone repository from Azure DevOps
2. Run automated setup script: `./scripts/setup_dev.sh`
3. Configure Azure resources: `./scripts/setup_azure.sh`
4. Update `.env` file with Azure credentials
5. Start development server: `./scripts/run_dev.sh`

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dtce_ai_bot

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
```

### Deployment
- **Automatic**: Push to main branch triggers Azure App Service deployment
- **Manual**: Use Azure CLI or Azure Portal
- **Teams Package**: Upload `teams-package/dtce-ai-bot-v1.2.0.zip` to Teams Admin Center

## 📞 Support & Documentation

### Documentation Resources
- **README.md**: Complete setup and usage guide
- **docs/DEVELOPMENT.md**: Development guidelines and architecture
- **docs/deployment/**: Production deployment procedures
- **docs/api/**: API endpoint documentation

### Key Commands
```bash
# Development setup
./scripts/setup_dev.sh

# Run development server
./scripts/run_dev.sh

# Azure resource setup
./scripts/setup_azure.sh

# Run tests
pytest

# Format code
black dtce_ai_bot/ && isort dtce_ai_bot/
```

---

**Last Updated**: August 17, 2025  
**Version**: 1.2.0  
**Repository**: https://dtceai-backend-cyashrb8hnc2ayhp.scm.newzealandnorth-01.azurewebsites.net:443/dtceai-backend.git
