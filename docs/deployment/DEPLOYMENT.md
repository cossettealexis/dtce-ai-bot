# Deployment Guide - DTCE AI Assistant

## Overview

This guide covers deployment of the DTCE AI Assistant to Azure App Service using GitHub Actions CI/CD pipeline. The application follows a microservices architecture with FastAPI backend and integrated Teams bot functionality.

## Prerequisites

### Required Azure Resources
- **Azure App Service** (Linux, Python 3.11)
- **Azure Form Recognizer** (Document Intelligence)
- **Azure Blob Storage** (Document storage)
- **Azure AD App Registration** (Authentication)
- **Microsoft Graph API** (SharePoint access)

### Development Tools
- Python 3.11+
- Git and GitHub account
- Azure CLI
- VS Code (recommended)
- Teams Developer Portal access

## Azure Resource Setup

### 1. Create Resource Group
```bash
# Login to Azure
az login

# Create resource group
az group create \
  --name dtce-ai-rg \
  --location "New Zealand North"
```

### 2. Create Storage Account
```bash
# Create storage account
az storage account create \
  --name dtceaistorage \
  --resource-group dtce-ai-rg \
  --location "New Zealand North" \
  --sku Standard_LRS \
  --kind StorageV2

# Create blob container
az storage container create \
  --name documents \
  --account-name dtceaistorage \
  --public-access off
```

### 3. Create Form Recognizer Resource
```bash
# Create Form Recognizer (Document Intelligence)
az cognitiveservices account create \
  --name dtce-form-recognizer \
  --resource-group dtce-ai-rg \
  --kind FormRecognizer \
  --sku S0 \
  --location "New Zealand North"
```

### 4. Create App Service Plan
```bash
# Create App Service Plan (Linux)
az appservice plan create \
  --name dtce-ai-plan \
  --resource-group dtce-ai-rg \
  --sku B1 \
  --is-linux
```

### 5. Create App Service
```bash
# Create Web App
az webapp create \
  --name dtceai-backend \
  --resource-group dtce-ai-rg \
  --plan dtce-ai-plan \
  --runtime "PYTHON|3.11"

# Enable logging
az webapp log config \
  --name dtceai-backend \
  --resource-group dtce-ai-rg \
  --web-server-logging filesystem
```

## Azure AD App Registration

### 1. Create App Registration
1. Go to **Azure Portal** → **Azure Active Directory** → **App registrations**
2. Click **New registration**
3. Configure:
   - **Name**: `DTCE AI Assistant`
   - **Supported account types**: `Accounts in this organizational directory only`
   - **Redirect URI**: `Web` → `https://your-app-name.azurewebsites.net/auth/callback`

### 2. Configure API Permissions
Add the following Microsoft Graph permissions:
- `Files.Read.All` (Application)
- `Sites.Read.All` (Application)
- `User.Read` (Delegated)

### 3. Create Client Secret
1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Set expiration and save the **Value** (you'll need this)

### 4. Grant Admin Consent
1. Go to **API permissions**
2. Click **Grant admin consent for [Your Organization]**

## Environment Configuration

### 1. Local Development (.env)
Create `.env` file in project root:
```env
# Azure Storage
AZURE_STORAGE_ACCOUNT_NAME=dtceaistorage
AZURE_STORAGE_ACCOUNT_KEY=your_storage_key
AZURE_STORAGE_CONTAINER_NAME=documents

# Azure Form Recognizer
AZURE_FORM_RECOGNIZER_ENDPOINT=https://dtce-form-recognizer.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_KEY=your_form_recognizer_key

# Microsoft Graph
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret
MICROSOFT_TENANT_ID=your_tenant_id

# Teams Bot
MICROSOFT_APP_ID=your_bot_app_id
MICROSOFT_APP_PASSWORD=your_bot_password

# Application
ENVIRONMENT=production
DEBUG=false
API_BASE_URL=https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net

# OpenAI (if using)
OPENAI_API_KEY=your_openai_key
```

### 2. Azure App Service Settings
Configure these in Azure Portal → App Service → Configuration:

```bash
# Using Azure CLI
az webapp config appsettings set \
  --name dtceai-backend \
  --resource-group dtce-ai-rg \
  --settings \
    AZURE_STORAGE_ACCOUNT_NAME="dtceaistorage" \
    AZURE_STORAGE_ACCOUNT_KEY="your_storage_key" \
    AZURE_STORAGE_CONTAINER_NAME="documents" \
    AZURE_FORM_RECOGNIZER_ENDPOINT="https://dtce-form-recognizer.cognitiveservices.azure.com/" \
    AZURE_FORM_RECOGNIZER_KEY="your_form_recognizer_key" \
    MICROSOFT_CLIENT_ID="your_client_id" \
    MICROSOFT_CLIENT_SECRET="your_client_secret" \
    MICROSOFT_TENANT_ID="your_tenant_id" \
    MICROSOFT_APP_ID="your_bot_app_id" \
    MICROSOFT_APP_PASSWORD="your_bot_password" \
    ENVIRONMENT="production" \
    DEBUG="false" \
    API_BASE_URL="https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
```

## GitHub Actions CI/CD Pipeline

### 1. Repository Secrets
Add these secrets in GitHub → Settings → Secrets and variables → Actions:

- `AZURE_WEBAPP_PUBLISH_PROFILE`: Download from Azure Portal → App Service → Get publish profile
- `AZURE_CLIENT_ID`: Your app registration client ID
- `AZURE_CLIENT_SECRET`: Your app registration client secret
- `AZURE_TENANT_ID`: Your Azure AD tenant ID

### 2. Workflow Configuration
The `.github/workflows/main_dtceai-backend.yml` file:

```yaml
name: Build and deploy Python app to Azure Web App - dtceai-backend

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python version
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Create and start virtual environment
        run: |
          python -m venv venv
          source venv/bin/activate

      - name: Install dependencies
        run: |
          source venv/bin/activate
          pip install -r requirements.txt

      - name: Zip artifact for deployment
        run: zip release.zip ./* -r

      - name: Upload artifact for deployment jobs
        uses: actions/upload-artifact@v4
        with:
          name: python-app
          path: |
            release.zip
            !venv/

  deploy:
    runs-on: ubuntu-latest
    needs: build
    environment:
      name: 'Production'
      url: ${{ steps.deploy-to-webapp.outputs.webapp-url }}

    steps:
      - name: Download artifact from build job
        uses: actions/download-artifact@v4
        with:
          name: python-app

      - name: Unzip artifact for deployment
        run: unzip release.zip

      - name: 'Deploy to Azure Web App'
        uses: azure/webapps-deploy@v3
        id: deploy-to-webapp
        with:
          app-name: 'dtceai-backend'
          slot-name: 'Production'
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

### 3. Manual Deployment (Alternative)
```bash
# Install Azure CLI
pip install azure-cli

# Login and deploy
az login
az webapp up \
  --name dtceai-backend \
  --resource-group dtce-ai-rg \
  --location "New Zealand North" \
  --runtime "PYTHON:3.11"
```

## Teams App Deployment

### 1. Create Teams App Package
The Teams app package (`teams-package/dtce-ai-bot-v1.2.0.zip`) includes:
- `manifest.json` - App manifest with v1.17 schema
- `color.png` - 192x192 color icon
- `outline.png` - 32x32 outline icon

### 2. Upload to Teams Admin Center
1. Go to **Teams Admin Center** → **Teams apps** → **Manage apps**
2. Click **Upload new app** → **Upload**
3. Select `dtce-ai-bot-v1.2.0.zip`
4. Configure app permissions and policies

### 3. App Validation
Ensure compliance with Teams store policies:
- ✅ Valid manifest schema (v1.17)
- ✅ Privacy policy endpoint (`/privacy`)
- ✅ Terms of use endpoint (`/terms`)
- ✅ Bot responds to basic commands (`Hi`, `Hello`, `Help`)
- ✅ Proper icon specifications

## Database Setup (Optional)

### 1. Azure Cosmos DB
```bash
# Create Cosmos DB account
az cosmosdb create \
  --name dtce-cosmos \
  --resource-group dtce-ai-rg \
  --kind GlobalDocumentDB

# Create database
az cosmosdb sql database create \
  --account-name dtce-cosmos \
  --resource-group dtce-ai-rg \
  --name dtce-ai-db

# Create container
az cosmosdb sql container create \
  --account-name dtce-cosmos \
  --resource-group dtce-ai-rg \
  --database-name dtce-ai-db \
  --name chat-sessions \
  --partition-key-path "/session_id"
```

### 2. PostgreSQL (Alternative)
```bash
# Create PostgreSQL server
az postgres server create \
  --name dtce-postgres \
  --resource-group dtce-ai-rg \
  --location "New Zealand North" \
  --admin-user dtceadmin \
  --admin-password "YourSecurePassword123!" \
  --sku-name B_Gen5_1

# Create database
az postgres db create \
  --resource-group dtce-ai-rg \
  --server-name dtce-postgres \
  --name dtce_ai_db
```

## Monitoring and Logging

### 1. Application Insights
```bash
# Create Application Insights
az monitor app-insights component create \
  --app dtce-ai-insights \
  --location "New Zealand North" \
  --resource-group dtce-ai-rg \
  --application-type web

# Link to App Service
az webapp config appsettings set \
  --name dtceai-backend \
  --resource-group dtce-ai-rg \
  --settings APPINSIGHTS_INSTRUMENTATIONKEY="your_instrumentation_key"
```

### 2. Log Analytics
```bash
# Create Log Analytics Workspace
az monitor log-analytics workspace create \
  --workspace-name dtce-ai-logs \
  --resource-group dtce-ai-rg \
  --location "New Zealand North"
```

### 3. Monitoring Configuration
Add to your FastAPI application:
```python
# Add to main.py
from opencensus.ext.azure.log_exporter import AzureLogHandler
import logging

# Configure Azure logging
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(
    connection_string='InstrumentationKey=your_key'
))

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(f"Path: {request.url.path} | "
               f"Method: {request.method} | "
               f"Status: {response.status_code} | "
               f"Duration: {process_time:.3f}s")
    return response
```

## Security Configuration

### 1. CORS Settings
```python
# In main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://teams.microsoft.com",
        "https://your-frontend-domain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Azure Key Vault (Recommended)
```bash
# Create Key Vault
az keyvault create \
  --name dtce-ai-vault \
  --resource-group dtce-ai-rg \
  --location "New Zealand North"

# Add secrets
az keyvault secret set \
  --vault-name dtce-ai-vault \
  --name "microsoft-client-secret" \
  --value "your_client_secret"

# Grant App Service access
az webapp identity assign \
  --name dtceai-backend \
  --resource-group dtce-ai-rg

az keyvault set-policy \
  --name dtce-ai-vault \
  --object-id "app_service_principal_id" \
  --secret-permissions get list
```

### 3. Network Security
```bash
# Restrict App Service access (optional)
az webapp config access-restriction add \
  --name dtceai-backend \
  --resource-group dtce-ai-rg \
  --rule-name "teams-only" \
  --action Allow \
  --ip-address "13.107.42.14/32" \
  --priority 100
```

## Performance Optimization

### 1. App Service Configuration
```bash
# Scale up the App Service plan
az appservice plan update \
  --name dtce-ai-plan \
  --resource-group dtce-ai-rg \
  --sku S1

# Enable auto-scaling
az monitor autoscale create \
  --resource-group dtce-ai-rg \
  --resource dtce-ai-plan \
  --resource-type Microsoft.Web/serverfarms \
  --name dtce-autoscale \
  --min-count 1 \
  --max-count 3 \
  --count 1
```

### 2. CDN Configuration (Optional)
```bash
# Create CDN profile
az cdn profile create \
  --name dtce-cdn \
  --resource-group dtce-ai-rg \
  --sku Standard_Microsoft

# Create CDN endpoint
az cdn endpoint create \
  --name dtce-api \
  --profile-name dtce-cdn \
  --resource-group dtce-ai-rg \
  --origin dtceai-backend.azurewebsites.net
```

## Backup and Disaster Recovery

### 1. App Service Backup
```bash
# Configure backup
az webapp config backup update \
  --webapp-name dtceai-backend \
  --resource-group dtce-ai-rg \
  --storage-account-url "your_storage_url" \
  --frequency 7 \
  --retain-one-years-backup-count 1
```

### 2. Data Backup Strategy
- **Blob Storage**: Enable soft delete and versioning
- **Database**: Configure automated backups
- **Configuration**: Store in Azure Key Vault
- **Code**: GitHub repository with proper branching

## Health Checks and Monitoring

### 1. Application Health Endpoint
```python
# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.2.0",
        "services": {
            "azure_storage": await check_storage_health(),
            "azure_form_recognizer": await check_fr_health(),
            "microsoft_graph": await check_graph_health()
        }
    }
```

### 2. Azure Monitor Alerts
```bash
# Create availability test
az monitor app-insights web-test create \
  --resource-group dtce-ai-rg \
  --app-insights dtce-ai-insights \
  --web-test-name "health-check" \
  --web-test-kind ping \
  --locations "Australia East" "Southeast Asia" \
  --frequency 300 \
  --url "https://dtceai-backend.azurewebsites.net/health"
```

## Troubleshooting

### Common Issues

#### 1. Deployment Failures
```bash
# Check deployment logs
az webapp log tail \
  --name dtceai-backend \
  --resource-group dtce-ai-rg

# Check application logs
az webapp log show \
  --name dtceai-backend \
  --resource-group dtce-ai-rg
```

#### 2. Authentication Issues
- Verify Azure AD app registration permissions
- Check client secret expiration
- Ensure proper redirect URIs are configured
- Validate tenant ID and client ID

#### 3. Storage Access Issues
```bash
# Test storage connection
az storage blob list \
  --container-name documents \
  --account-name dtceaistorage \
  --account-key "your_key"
```

#### 4. Teams Bot Issues
- Verify bot endpoint URL in Bot Framework
- Check Teams manifest validation
- Ensure bot responds to basic commands
- Validate messaging endpoint security

### Performance Issues
- Monitor Application Insights metrics
- Check CPU and memory usage
- Review slow query logs
- Optimize document processing pipeline

### Log Analysis
```bash
# Stream logs in real-time
az webapp log tail \
  --name dtceai-backend \
  --resource-group dtce-ai-rg \
  --provider application

# Download logs
az webapp log download \
  --name dtceai-backend \
  --resource-group dtce-ai-rg \
  --log-file app_logs.zip
```

## Post-Deployment Checklist

- [ ] All Azure resources created and configured
- [ ] Environment variables set in App Service
- [ ] GitHub Actions pipeline working
- [ ] Teams app uploaded and validated
- [ ] Health check endpoint responding
- [ ] Document sync functionality tested
- [ ] Chat/Q&A functionality tested
- [ ] Monitoring and alerts configured
- [ ] Backup strategy implemented
- [ ] Security configurations applied
- [ ] Performance baseline established

## Maintenance

### Regular Tasks
1. **Weekly**: Review application logs and performance metrics
2. **Monthly**: Update dependencies and security patches
3. **Quarterly**: Review and rotate secrets/certificates
4. **Annually**: Review architecture and scalability needs

### Updates and Patches
```bash
# Update Python dependencies
pip install --upgrade -r requirements.txt

# Update Teams app package
# Upload new version to Teams Admin Center

# Deploy updates
git push origin main  # Triggers GitHub Actions
```

For additional support and advanced configurations, refer to the Azure documentation and Microsoft Teams development guides.
