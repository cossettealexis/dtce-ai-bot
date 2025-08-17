# Setup Instructions

Comprehensive setup guide for the DTCE AI Assistant.

## Prerequisites

Before setting up the DTCE AI Assistant, ensure you have:

- **Python 3.11+** installed
- **Azure subscription** with appropriate permissions
- **Microsoft 365/SharePoint** access for document integration
- **Git** for version control
- **Azure CLI** installed and configured

## Environment Setup

### Option A: Automated Setup (Recommended)

```bash
# Make setup script executable
chmod +x scripts/setup_dev.sh

# Run automated setup
./scripts/setup_dev.sh
```

### Option B: Manual Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

## Environment Variables Configuration

Edit the `.env` file with your Azure credentials:

### Required Configuration

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_openai_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Azure Storage Configuration  
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...

# Microsoft Graph API
AZURE_CLIENT_ID=your_client_id_here
AZURE_CLIENT_SECRET=your_client_secret_here
AZURE_TENANT_ID=your_tenant_id_here

# SharePoint Configuration
SHAREPOINT_SITE_ID=your_site_id_here
SHAREPOINT_DRIVE_ID=your_drive_id_here

# Azure Form Recognizer
AZURE_FORM_RECOGNIZER_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_KEY=your_form_recognizer_key_here
```

### Optional Configuration

```bash
# Development Settings
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=development

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Teams Bot Configuration (for Teams integration)
MICROSOFT_APP_ID=your_teams_app_id
MICROSOFT_APP_PASSWORD=your_teams_app_password
```

## Azure Resource Setup

### Option A: Automated Azure Setup

```bash
# Make Azure setup script executable
chmod +x scripts/setup_azure.sh

# Run Azure resource creation
./scripts/setup_azure.sh
```

### Option B: Manual Azure Setup

#### 1. Create Resource Group

```bash
az group create --name dtce-ai-rg --location "New Zealand North"
```

#### 2. Create Storage Account

```bash
az storage account create \
  --name dtceaistorage \
  --resource-group dtce-ai-rg \
  --location "New Zealand North" \
  --sku Standard_LRS
```

#### 3. Create OpenAI Service

```bash
az cognitiveservices account create \
  --name dtce-openai \
  --resource-group dtce-ai-rg \
  --kind OpenAI \
  --sku S0 \
  --location "East US"
```

#### 4. Create Form Recognizer Service

```bash
az cognitiveservices account create \
  --name dtce-form-recognizer \
  --resource-group dtce-ai-rg \
  --kind FormRecognizer \
  --sku S0 \
  --location "East US"
```

#### 5. Create App Registration

```bash
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

## Running the Application

### Option A: Using Run Script

```bash
# Make run script executable
chmod +x scripts/run_dev.sh

# Start development server
./scripts/run_dev.sh
```

### Option B: Manual Run

```bash
# Activate virtual environment
source .venv/bin/activate

# Start the server
python -m uvicorn dtce_ai_bot.core.app:app --reload --host 0.0.0.0 --port 8000
```

## Verification

Navigate to:
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Teams Bot**: http://localhost:8000/api/teams

## Teams Integration Setup

1. Upload the Teams app package (`teams-package/dtce-ai-bot-v1.2.0.zip`)
2. Configure bot endpoints in Azure Bot Service
3. Add app to your Teams workspace

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Kill process using port 8000
   lsof -ti:8000 | xargs kill -9
   ```

2. **Azure Authentication Issues**
   ```bash
   # Login to Azure CLI
   az login
   
   # Verify subscription
   az account show
   ```

3. **Environment Variable Issues**
   ```bash
   # Check if .env file exists
   ls -la .env
   
   # Verify environment variables are loaded
   python -c "from dtce_ai_bot.config.settings import get_settings; print(get_settings())"
   ```

4. **SharePoint Access Issues**
   - Verify app registration permissions
   - Check SharePoint site access
   - Confirm tenant admin consent

### Debug Mode

Set `DEBUG=true` in `.env` for detailed logging:

```bash
echo "DEBUG=true" >> .env
```

## Next Steps

After successful setup:
1. Review the [Development Guide](DEVELOPMENT.md)
2. Check the [API Reference](api/) for detailed endpoint documentation
3. Explore [Teams Integration](teams/) for Teams app configuration
