# DTCE AI Assistant

An intelligent AI assistant for DTCE engineering teams, providing comprehensive document analysis, project scoping, and engineering guidance.

## Features

- 🤖 **Teams Bot Integration**: Microsoft Teams bot for easy access
- 📄 **Document Q&A**: Intelligent question answering from engineering documents
- 🏗️ **Project Scoping**: Analyze new projects and find similar past projects
- ⚠️ **Risk Analysis**: Identify potential issues based on past experience
- 🔍 **Similarity Matching**: Find relevant past projects for reference
- 📋 **Design Philosophy**: Generate design recommendations based on experience

## Quick Start

### Local Development

```bash
# Clone and setup
git clone <repository-url>
cd dtce-ai-bot

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your Azure credentials

# Run locally
python -m uvicorn dtce_ai_bot.core.app:app --reload --host 0.0.0.0 --port 8000
```

### API Endpoints

- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Document Q&A**: http://localhost:8000/documents
- **Project Scoping**: http://localhost:8000/projects
- **Teams Bot**: http://localhost:8000/api/teams

## Project Structure

```
dtce-ai-bot/
├── dtce_ai_bot/           # Main application package
│   ├── bot/               # Teams bot implementation
│   ├── core/              # Core application setup
│   ├── services/          # Business logic services
│   ├── integrations/      # External service integrations
│   └── config/            # Configuration management
├── tests/                 # Test files
├── docs/                  # Documentation
├── deployment/            # Deployment scripts and docs
└── static/                # Static files
```

## Development

See individual folders for specific documentation:
- `/tests/README.md` - Running tests
- `/deployment/docs/` - Deployment guides
- `/docs/examples/` - Usage examples
