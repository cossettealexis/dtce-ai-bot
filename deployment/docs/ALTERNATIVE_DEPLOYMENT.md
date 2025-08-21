# 🚀 Alternative Deployment Methods for Azure App Service

Since the VS Code "Deploy to Web App" option isn't showing, here are other easy ways to deploy:

## Method 1: GitHub Actions (Recommended)

1. **Push your code to GitHub** (if not already done):
   ```bash
   git add .
   git commit -m "Ready for Azure deployment"
   git push origin main
   ```

2. **Set up GitHub deployment in Azure Portal:**
   - Go to [Azure Portal](https://portal.azure.com)
   - Navigate to your `dtceai-backend` App Service
   - Go to **Deployment** → **Deployment Center**
   - Choose **GitHub** as the source
   - Authorize and select your repository
   - Choose branch: `main`
   - Click **Save**

3. **Add environment variables** (see step 4 below)

## Method 2: ZIP Upload (Easiest)

1. **Create a ZIP file of your project:**
   - Select all files in your project folder
   - Create a ZIP file (make sure `startup.py`, `requirements.txt` are included)

2. **Upload via Kudu:**
   - Go to Azure Portal → `dtceai-backend`
   - Go to **Development Tools** → **Advanced Tools** → **Go →**
   - This opens Kudu (Azure's deployment engine)
   - Go to **Tools** → **ZIP Push Deploy**
   - Drag and drop your ZIP file

3. **Add environment variables** (see step 4 below)

## Method 3: Direct Git Push

1. **Get deployment credentials:**
   - Azure Portal → `dtceai-backend` → **Deployment** → **Deployment Center**
   - Go to **FTPS credentials** tab
   - Note the Git clone URL

2. **Add Azure as remote and push:**
   ```bash
   git remote add azure [Git clone URL from step 1]
   git push azure main
   ```

## Method 4: Azure CLI (if you have it)

```bash
# First, login to Azure
az login

# Deploy using ZIP
az webapp deployment source config-zip \
  --resource-group AIChatBot \
  --name dtceai-backend \
  --src your-project.zip
```

## Step 4: Configure Environment Variables (Required for all methods)

After deployment, you MUST set environment variables:

1. **Go to Azure Portal** → `dtceai-backend`
2. **Settings** → **Configuration** → **Application settings**
3. **Add these variables** (get keys from Azure Portal):

```
Name: AZURE_STORAGE_ACCOUNT_NAME
Value: dtceaistorage

Name: AZURE_STORAGE_ACCOUNT_KEY  
Value: [Get from dtceaistorage → Access keys → key1]

Name: AZURE_STORAGE_CONTAINER
Value: documents

Name: AZURE_SEARCH_SERVICE_NAME
Value: dtceai-search

Name: AZURE_SEARCH_API_KEY
Value: [Get from dtceai-search → Keys → Primary admin key]

Name: AZURE_OPENAI_ENDPOINT
Value: https://dtceai-gpt.openai.azure.com/

Name: AZURE_OPENAI_API_KEY
Value: [Get from dtceai-gpt → Keys and Endpoint → KEY 1]

Name: AZURE_OPENAI_DEPLOYMENT_NAME
Value: gpt-4

Name: AZURE_FORM_RECOGNIZER_ENDPOINT
Value: https://dtceai-form-recognizer.cognitiveservices.azure.com/

Name: AZURE_FORM_RECOGNIZER_API_KEY
Value: [Get from dtceai-form-recognizer → Keys and Endpoint → KEY 1]

Name: ENVIRONMENT
Value: production

Name: API_HOST
Value: 0.0.0.0

Name: API_PORT
Value: 8000
```

4. **Click Save**

## Step 5: Set Startup Command

1. **In Configuration**, go to **General settings**
2. **Startup command**: `python startup.py`
3. **Save**

## Step 6: Test Your Deployment

Visit: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net`

**Check logs if issues:**
- Azure Portal → `dtceai-backend` → **Monitoring** → **Log stream**

## Recommended: Method 1 (GitHub Actions)
This is the best approach because:
- ✅ Automatic deployments when you push code
- ✅ Built-in CI/CD pipeline
- ✅ Easy to manage and rollback
- ✅ Shows deployment history

Choose the method that works best for you! 🚀
