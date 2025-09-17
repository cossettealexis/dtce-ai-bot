# DTCE AI Bot - Fresh Start

A clean implementation of DTCE AI Assistant with Microsoft Teams integration.

## Features
- Microsoft Teams Bot Framework integration
- Azure OpenAI for intelligent responses
- FastAPI backend
- Clean, maintainable architecture

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:
```bash
cp .env.example .env
# Edit .env with your Azure credentials
```

3. Run the application:
```bash
python -m dtce_ai_bot
```

## Azure Deployment

The app is configured for automatic deployment to Azure App Service.

## Architecture

```
dtce_ai_bot/
├── main.py          # FastAPI application entry point
├── config/          # Configuration management
├── api/             # API endpoints
├── bot/             # Teams bot handlers
└── services/        # Business logic services
```
