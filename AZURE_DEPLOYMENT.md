# Azure App Service Deployment Guide for DTCE AI Bot

This guide will help you deploy the DTCE AI Bot to Azure App Service.

## Prerequisites

1. **Azure Subscription** with access to:
   - Azure App Service
   - Azure Storage Account
   - Azure Cognitive Search
   - Azure OpenAI Service
   - Microsoft Entra ID (Azure AD)

2. **Local Development Tools**:
   - Azure CLI installed and logged in
   - Git (for deployment)
   - VS Code with Azure Extensions (optional but recommended)

## Step 1: Using Your Existing Azure Resources

✅ **You already have the following resources set up:**

- **App Service Plan**: `ASP-AIChatBot-97aa` (New Zealand North)
- **App Service**: `dtceai-backend` (New Zealand North)
- **Azure Storage**: `dtceaistorage`
- **Azure Cognitive Search**: `dtceai-search` (Central US)
- **Azure OpenAI**: `dtceai-gpt` (East US)
- **Document Intelligence**: `dtceai-formrecognizer` (East US)

Since your resources are already created, we'll skip to configuring your existing App Service for deployment.

## Step 2: Configure Environment Variables for Your Resources

First, get your resource group name:
```bash
# Find your resource group (likely something like 'dtceai-rg' or similar)
az group list --query "[?contains(name, 'dtce') || contains(name, 'ai')].name" -o table
```

Set these in your existing Azure App Service Configuration using your actual resource group name:

```bash
# Replace 'your-resource-group' with your actual resource group name
RESOURCE_GROUP="your-resource-group"

# Set application settings for your existing resources
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name dtceai-backend \
  --settings \
    ENVIRONMENT=production \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    AZURE_STORAGE_ACCOUNT_NAME=dtceaistorage \
    AZURE_STORAGE_ACCOUNT_KEY="$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name dtceaistorage --query '[0].value' -o tsv)" \
    AZURE_STORAGE_CONTAINER=documents \
    AZURE_SEARCH_SERVICE_NAME=dtceai-search \
    AZURE_SEARCH_API_KEY="$(az search admin-key show --resource-group $RESOURCE_GROUP --service-name dtceai-search --query 'primaryKey' -o tsv)" \
    AZURE_OPENAI_ENDPOINT="$(az cognitiveservices account show --name dtceai-gpt --resource-group $RESOURCE_GROUP --query 'properties.endpoint' -o tsv)" \
    AZURE_OPENAI_API_KEY="$(az cognitiveservices account keys list --name dtceai-gpt --resource-group $RESOURCE_GROUP --query 'key1' -o tsv)" \
    AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4 \
    AZURE_FORM_RECOGNIZER_ENDPOINT="$(az cognitiveservices account show --name dtceai-formrecognizer --resource-group $RESOURCE_GROUP --query 'properties.endpoint' -o tsv)" \
    AZURE_FORM_RECOGNIZER_API_KEY="$(az cognitiveservices account keys list --name dtceai-formrecognizer --resource-group $RESOURCE_GROUP --query 'key1' -o tsv)" \
    MICROSOFT_TENANT_ID=your_tenant_id \
    MICROSOFT_CLIENT_ID=your_client_id \
    MICROSOFT_CLIENT_SECRET=your_client_secret
```

**Important**: 
1. Replace `your-resource-group` with your actual resource group name
2. Replace the Microsoft/SharePoint credentials with your actual values
3. Verify that your OpenAI deployment name matches (might be different from 'gpt-4')

## Step 3: Deploy the Application

### Option A: Deploy from Local Git

1. **Initialize local git repository** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. **Configure Azure deployment to your existing App Service**:
   ```bash
   az webapp deployment source config-local-git \
     --name dtceai-backend \
     --resource-group $RESOURCE_GROUP
   ```

3. **Add Azure as git remote**:
   ```bash
   # Get the deployment URL for your existing app service
   DEPLOY_URL=$(az webapp deployment list-publishing-credentials --name dtceai-backend --resource-group $RESOURCE_GROUP --query 'scmUri' -o tsv)
   git remote add azure $DEPLOY_URL
   ```

4. **Deploy**:
   ```bash
   git push azure main
   ```

### Option B: Deploy from GitHub

1. **Push your code to GitHub** (if not already done)

2. **Configure GitHub deployment to your existing App Service**:
   ```bash
   az webapp deployment source config \
     --name dtceai-backend \
     --resource-group $RESOURCE_GROUP \
     --repo-url https://github.com/yourusername/dtce-ai-bot \
     --branch main \
     --manual-integration
   ```

### Option C: Deploy using VS Code

1. Install the Azure App Service extension for VS Code
2. Sign in to your Azure account
3. Right-click on your project folder
4. Select "Deploy to Web App..."
5. Choose your subscription and web app

## Step 4: Configure Startup Command

Set the startup command in your existing Azure App Service:

```bash
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name dtceai-backend \
  --startup-file "python startup.py"
```

## Step 5: Configure SharePoint/Microsoft Graph

1. **Register Application in Azure AD**:
   - Go to Azure Portal → Azure Active Directory → App registrations
   - Create new registration
   - Add API permissions for Microsoft Graph and SharePoint
   - Generate client secret

2. **Update environment variables** with the correct Microsoft credentials

## Step 6: Set Up Custom Domain (Optional)

```bash
# Map custom domain
az webapp config hostname add \
  --webapp-name dtce-ai-bot \
  --resource-group dtce-ai-bot-rg \
  --hostname yourdomain.com

# Configure SSL
az webapp config ssl bind \
  --certificate-thumbprint your_cert_thumbprint \
  --ssl-type SNI \
  --name dtce-ai-bot \
  --resource-group dtce-ai-bot-rg
```

## Step 7: Monitor and Scale

### Enable Application Insights
```bash
az monitor app-insights component create \
  --app dtce-ai-bot-insights \
  --location "East US" \
  --resource-group dtce-ai-bot-rg

# Link to web app
az webapp config appsettings set \
  --resource-group dtce-ai-bot-rg \
  --name dtce-ai-bot \
  --settings APPLICATIONINSIGHTS_CONNECTION_STRING="$(az monitor app-insights component show --app dtce-ai-bot-insights --resource-group dtce-ai-bot-rg --query 'connectionString' -o tsv)"
```

### Configure Auto-scaling
```bash
az monitor autoscale create \
  --resource-group dtce-ai-bot-rg \
  --resource dtce-ai-bot-plan \
  --resource-type Microsoft.Web/serverfarms \
  --name dtce-ai-bot-autoscale \
  --min-count 1 \
  --max-count 3 \
  --count 1
```

## Step 8: Verify Deployment

1. **Check the application**:
   ```bash
   az webapp browse --name dtceai-backend --resource-group $RESOURCE_GROUP
   ```

2. **Test endpoints**:
   - Health check: `https://dtceai-backend.azurewebsites.net/health`
   - API docs: `https://dtceai-backend.azurewebsites.net/docs` (if enabled)
   - Document sync: `https://dtceai-backend.azurewebsites.net/documents/sync-suitefiles`

3. **Check logs**:
   ```bash
   az webapp log tail --name dtceai-backend --resource-group $RESOURCE_GROUP
   ```

## Troubleshooting

### Common Issues:

1. **Import errors**: Make sure all dependencies are in `requirements.txt`
2. **Environment variables**: Verify all required environment variables are set
3. **Authentication**: Check Microsoft Graph API permissions
4. **Storage**: Verify Azure Storage account configuration
5. **Startup**: Check the startup command and Python version

### Debug Commands:
```bash
# Check app settings
az webapp config appsettings list --name dtceai-backend --resource-group $RESOURCE_GROUP

# View logs
az webapp log download --name dtceai-backend --resource-group $RESOURCE_GROUP

# Restart app
az webapp restart --name dtceai-backend --resource-group $RESOURCE_GROUP
```

## Security Considerations

1. **Use Key Vault** for sensitive credentials:
   ```bash
   az keyvault create --name dtce-ai-bot-kv --resource-group dtce-ai-bot-rg
   ```

2. **Enable managed identity** for the web app:
   ```bash
   az webapp identity assign --name dtce-ai-bot --resource-group dtce-ai-bot-rg
   ```

3. **Configure IP restrictions** if needed:
   ```bash
   az webapp config access-restriction add \
     --resource-group dtce-ai-bot-rg \
     --name dtce-ai-bot \
     --rule-name "Office IP" \
     --action Allow \
     --ip-address "YOUR.OFFICE.IP.ADDRESS/32" \
     --priority 100
   ```

## Cost Optimization

1. **Use B1 or S1 pricing tier** for production
2. **Enable auto-scaling** to handle traffic spikes
3. **Use Azure Storage cool tier** for infrequently accessed documents
4. **Monitor costs** with Azure Cost Management

## Backup and Disaster Recovery

1. **Set up backup**:
   ```bash
   az webapp config backup create \
     --resource-group dtce-ai-bot-rg \
     --webapp-name dtce-ai-bot \
     --backup-name initial-backup \
     --storage-account-url "https://dtceaibotstore.blob.core.windows.net/backups"
   ```

2. **Configure slot deployment** for zero-downtime updates:
   ```bash
   az webapp deployment slot create \
     --name dtce-ai-bot \
     --resource-group dtce-ai-bot-rg \
     --slot staging
   ```

Your DTCE AI Bot should now be successfully deployed to Azure App Service!
