# Simple Deployment Guide - Deploy Your Code to Azure

## 🎯 Your Azure Resources
- **Resource Group**: `AIChatBot`
- **App Service**: `dtceai-backend`
- **App URL**: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net`

## 🚀 Easy Deployment Steps

### Step 1: Create Your Environment Variables

Create a `.env` file with your Azure resource details:

```env
# Azure Resources (from your existing setup)
AZURE_STORAGE_ACCOUNT_NAME=dtceaistorage
AZURE_SEARCH_SERVICE_NAME=dtceai-search
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# You need to get these values from Azure Portal:
AZURE_STORAGE_ACCOUNT_KEY=your_storage_key_here
AZURE_SEARCH_API_KEY=your_search_key_here
AZURE_OPENAI_ENDPOINT=https://dtceai-gpt.openai.azure.com/
AZURE_OPENAI_API_KEY=your_openai_key_here
AZURE_FORM_RECOGNIZER_ENDPOINT=https://dtceai-formrecognizer.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_API_KEY=your_form_recognizer_key_here

# Microsoft Graph/SharePoint (if needed)
MICROSOFT_TENANT_ID=your_tenant_id
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret

# Application Settings
ENVIRONMENT=production
API_HOST=0.0.0.0
API_PORT=8000
AZURE_STORAGE_CONTAINER=documents
```

### Step 2: Get Your Azure Keys

#### Option A: Use Azure Portal (Easiest)
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to each resource and copy the keys:

**Storage Account Key:**
- Go to `dtceaistorage` → Access keys → Copy key1

**Search Service Key:**
- Go to `dtceai-search` → Keys → Copy Primary admin key

**OpenAI Key:**
- Go to `dtceai-gpt` → Keys and Endpoint → Copy KEY 1

**Form Recognizer Key:**
- Go to `dtceai-formrecognizer` → Keys and Endpoint → Copy KEY 1

#### Option B: Use Azure CLI (if you have it installed)
```bash
# Storage key
az storage account keys list --resource-group AIChatBot --account-name dtceaistorage --query '[0].value' -o tsv

# Search key
az search admin-key show --resource-group AIChatBot --service-name dtceai-search --query 'primaryKey' -o tsv

# OpenAI key
az cognitiveservices account keys list --name dtceai-gpt --resource-group AIChatBot --query 'key1' -o tsv

# Form Recognizer key
az cognitiveservices account keys list --name dtceai-formrecognizer --resource-group AIChatBot --query 'key1' -o tsv
```

### Step 3: Deploy Using VS Code (Recommended)

1. **Install VS Code Extension:**
   - Install "Azure App Service" extension in VS Code

2. **Sign in to Azure:**
   - Open VS Code
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
   - Type "Azure: Sign In"
   - Sign in with your Azure account

3. **Deploy Your Code:**
   - Right-click on your project folder in VS Code
   - Select "Deploy to Web App..."
   - Choose your subscription
   - Select `dtceai-backend` from the list
   - Confirm deployment

4. **Set Environment Variables:**
   - After deployment, go to Azure Portal
   - Navigate to `dtceai-backend` → Configuration → Application settings
   - Add all the environment variables from your `.env` file

### Step 4: Alternative - ZIP Deployment

If VS Code doesn't work, you can use ZIP deployment:

1. **Create a ZIP file:**
   - Zip your entire project folder
   - Make sure `requirements.txt`, `startup.py`, and all your Python files are included

2. **Deploy via Azure Portal:**
   - Go to Azure Portal → `dtceai-backend`
   - Go to Advanced Tools → Go to Kudu
   - Go to Tools → ZIP Push Deploy
   - Drag and drop your ZIP file

### Step 5: Configure Startup

In Azure Portal:
1. Go to `dtceai-backend` → Configuration → General settings
2. Set Startup Command to: `python startup.py`
3. Save the configuration

### Step 6: Test Your Deployment

Visit these URLs to test:
- **Main App**: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net`
- **Health Check**: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/health`
- **API Docs**: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/docs`

## 🔧 Quick Troubleshooting

**If deployment fails:**
1. Check the logs in Azure Portal → `dtceai-backend` → Monitoring → Log stream
2. Make sure all environment variables are set
3. Verify `startup.py` exists in your project
4. Check that `requirements.txt` has all dependencies

**Common issues:**
- Missing environment variables
- Wrong Python version (should be 3.10 or 3.11)
- Missing dependencies in `requirements.txt`

## 📱 Quick Commands

**Restart your app:**
- Go to Azure Portal → `dtceai-backend` → Overview → Restart

**View logs:**
- Go to Azure Portal → `dtceai-backend` → Monitoring → Log stream

**Update environment variables:**
- Go to Azure Portal → `dtceai-backend` → Configuration → Application settings

That's it! Your enhanced DTCE AI Bot should now be running on Azure! 🎉
