# 🚀 Easy Deployment to Your Azure App Service

## Your Azure Setup:
- **App Service**: `dtceai-backend` 
- **Resource Group**: `AIChatBot`
- **URL**: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net`

## Step 1: Setup Your Environment Variables

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Get your Azure keys from the portal:**
   
   Go to [Azure Portal](https://portal.azure.com) and get these keys:

   **For Storage (dtceaistorage):**
   - Go to `dtceaistorage` → Security + networking → Access keys
   - Copy **key1** value

   **For Search (dtceai-search):**
   - Go to `dtceai-search` → Settings → Keys  
   - Copy **Primary admin key**

   **For OpenAI (dtceai-gpt):**
   - Go to `dtceai-gpt` → Resource Management → Keys and Endpoint
   - Copy **KEY 1**

   **For Form Recognizer (dtceai-form-recognizer):**
   - Go to `dtceai-form-recognizer` → Resource Management → Keys and Endpoint
   - Copy **KEY 1**

3. **Edit your `.env` file** and paste the keys you copied

## Step 2: Deploy Using VS Code (Easiest Method)

1. **Install Azure Extension:**
   - Open VS Code
   - Go to Extensions (Ctrl+Shift+X)
   - Search for "Azure App Service"
   - Install it

2. **Sign in to Azure:**
   - Press `Ctrl+Shift+P` (Cmd+Shift+P on Mac)
   - Type "Azure: Sign In"
   - Sign in with your Azure account

3. **Deploy:**
   - Right-click on your project folder
   - Select "Deploy to Web App..."
   - Choose your subscription
   - Select `dtceai-backend`
   - Click "Deploy"

## Step 3: Set Environment Variables in Azure

After deployment, you need to set your environment variables in Azure:

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to `dtceai-backend`
3. Go to **Settings** → **Configuration**
4. Click **"+ New application setting"** for each variable from your `.env` file

**Add these settings:**
```
AZURE_STORAGE_ACCOUNT_NAME = dtceaistorage
AZURE_STORAGE_ACCOUNT_KEY = [your storage key]
AZURE_STORAGE_CONTAINER = documents
AZURE_SEARCH_SERVICE_NAME = dtceai-search
AZURE_SEARCH_API_KEY = [your search key]
AZURE_OPENAI_ENDPOINT = https://dtceai-gpt.openai.azure.com/
AZURE_OPENAI_API_KEY = [your openai key]
AZURE_OPENAI_DEPLOYMENT_NAME = gpt-4
AZURE_FORM_RECOGNIZER_ENDPOINT = https://dtceai-form-recognizer.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_API_KEY = [your form recognizer key]
ENVIRONMENT = production
API_HOST = 0.0.0.0
API_PORT = 8000
```

5. Click **Save**

## Step 4: Set Startup Command

1. In your App Service configuration, go to **General settings**
2. Set **Startup command** to: `python startup.py`
3. Click **Save**

## Step 5: Test Your App

Visit: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net`

**Test endpoints:**
- Health: `/health`
- API docs: `/docs`

## Alternative: ZIP Upload Method

If VS Code doesn't work:

1. **Create a ZIP file** of your entire project
2. Go to Azure Portal → `dtceai-backend` → **Advanced Tools** → **Go→**
3. Go to **Tools** → **ZIP Push Deploy**  
4. Drag your ZIP file and drop it

## Troubleshooting

**Check logs:**
- Azure Portal → `dtceai-backend` → **Monitoring** → **Log stream**

**Restart app:**
- Azure Portal → `dtceai-backend` → **Overview** → **Restart**

**Common issues:**
- Missing environment variables (check Configuration)
- Wrong startup command (should be `python startup.py`)
- Missing files in deployment

That's it! Your enhanced AI bot should now be running! 🎉
