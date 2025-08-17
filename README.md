# DTCE AI Assistant

An intelligent AI assistant for DTCE engineering teams, providing comprehensive document analysis, project scoping, and engineering guidance with advanced SharePoint integration and Microsoft Teams bot capabilities.

## 🚀 Quick Start

### Prerequisites
- Python 3.9+ with pip and venv
- Azure Subscription with admin access
- Microsoft 365 Tenant with SharePoint access
- Git for version control

### Installation
```bash
# Clone and setup
git clone https://github.com/cossettealexis/dtce-ai-bot.git
cd dtce-ai-bot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Azure credentials

# Run development server
python -m uvicorn dtce_ai_bot.core.app:app --reload --host 0.0.0.0 --port 8000
```

## 📚 Documentation

All project documentation is organized in the `/docs` folder:

- **[Setup Guide](docs/SETUP.md)** - Comprehensive setup and configuration instructions
- **[Development Guide](docs/DEVELOPMENT.md)** - Development workflow and guidelines  
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment instructions
- **[API Documentation](docs/api/)** - Complete API reference and examples
- **[Teams Integration](docs/teams/)** - Microsoft Teams app documentation

## 🏗️ Core Features

### Document Management
- 📁 **SharePoint Integration** - Direct sync with Microsoft SharePoint/OneDrive
- 🔄 **Real-time Sync** - Standard and async document synchronization
- ⚡ **Force Re-sync** - Complete folder re-processing capabilities
- 💾 **Azure Storage** - Secure document storage and retrieval

### AI Capabilities
- 🤖 **Document Q&A** - AI-powered question answering from engineering documents
- 🏗️ **Project Scoping** - Analyze new projects and find similar past projects
- ⚠️ **Risk Analysis** - Identify potential issues based on past experience
- 🔍 **Similarity Matching** - Find relevant past projects for reference

### Teams Integration
- ✅ **Teams App Store Compliant** - Schema v1.17 with full validation
- 🛡️ **Privacy & Terms** - Dedicated compliance endpoints
- 💬 **Enhanced Bot Commands** - Comprehensive command support
- 🔐 **Secure Authentication** - Microsoft Graph API integration

## 🚀 Core Endpoints

### Health & Documentation
- `GET /` - Health check and API information
- `GET /docs` - Interactive API documentation (Swagger/OpenAPI)
- `GET /health` - System health monitoring

### Document Management
- `POST /documents/sync-suitefiles-async` - Asynchronous document synchronization
- `POST /documents/sync-suitefiles-async?force=true` - Force re-sync all documents
- `POST /documents/ask` - **Core AI endpoint** - handles ALL user queries (document Q&A, project scoping, general chat)

### Teams Bot Interface
- `POST /api/teams/messages` - Teams bot message handler (routes all user input to `/documents/ask`)
- `GET /privacy` - Privacy policy (Teams compliance)
- `GET /terms` - Terms of use (Teams compliance)

> **Note**: **ALL user interactions** in Teams (document questions, project analysis, general chat) go through the Teams bot, which internally calls `/documents/ask` for AI responses.

## 🏗️ Architecture

### Service Layer Design
```
dtce_ai_bot/
├── services/              # Business logic layer
├── integrations/          # External service integrations  
├── bot/                   # Teams bot implementation
├── api/                   # REST API layer
└── core/                  # Application foundation
```

Following **SOLID principles** throughout the codebase with proper separation of concerns, dependency injection, and extensible design patterns.

## 📋 Teams App Package

- **Current Version**: 1.2.0
- **Package Location**: `/teams-package/dtce-ai-bot-v1.2.0.zip`
- **Schema Compliance**: Teams manifest v1.17
- **Features**: Document sync, interactive chat, compliance endpoints

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dtce_ai_bot --cov-report=html

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
```

## 🚀 Deployment

- **Azure App Service**: Automatic deployment via GitHub Actions
- **Teams App Store**: Compliant packages ready for validation
- **Environment Management**: Separate dev/staging/production configurations

## 🔧 Force Re-sync Feature

The application includes a powerful force re-sync capability:

```bash
# Force re-sync all documents (bypasses modification date checks)
curl -X POST "https://your-app-url/documents/sync-suitefiles-async?force=true"
```

This feature is particularly useful for:
- Initial setup and configuration
- Troubleshooting "No documents found to sync" issues
- Complete knowledge base refresh
- After configuration changes

## 💬 User Experience

Users interact with the AI assistant entirely through the **Microsoft Teams bot chat interface**:

- **Document Questions**: Users ask questions in Teams chat, bot searches documents and provides answers
- **Project Scoping**: Users describe new projects, bot analyzes and finds similar past projects
- **Natural Language**: No need to learn API endpoints - just chat naturally with the bot

## 🚨 Troubleshooting

### Common Issues
- **SharePoint Access**: Ensure Graph API permissions are configured
- **Document Sync**: Use force re-sync for complete folder processing  
- **Teams Bot**: Verify bot framework registration matches manifest

### Debug Mode
```bash
export LOG_LEVEL=DEBUG
python -m uvicorn dtce_ai_bot.core.app:app --reload
```

## 📞 Support

For detailed information, see the comprehensive documentation in the `/docs` folder:
- [Setup Guide](docs/SETUP.md) for environment configuration
- [API Documentation](docs/api/) for endpoint details
- [Teams Documentation](docs/teams/) for Teams app deployment

---

**Version**: 1.2.0 | **License**: MIT | **Status**: Production Ready
