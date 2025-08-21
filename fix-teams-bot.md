# Fix Teams Bot Configuration

## Issue
Teams shows "Failed to send" because the bot authentication is not properly configured.

## Solution

### 1. Set these environment variables in Azure App Service

Go to Azure Portal → App Services → dtceai-backend → Settings → Configuration → Application settings

Add these environment variables:

```
MICROSOFT_APP_ID=YOUR_APP_ID_FROM_STEP_1
MICROSOFT_APP_PASSWORD=YOUR_APP_SECRET_FROM_STEP_1  
MICROSOFT_APP_TENANT_ID=YOUR_TENANT_ID_FROM_STEP_1
MICROSOFT_APP_TYPE=MultiTenant
```

### 2. Create Azure Bot Service

In Azure Portal, create a new Azure Bot Service:

1. Search for "Azure Bot" → Create
2. Bot handle: `dtce-ai-assistant` 
3. Subscription: Your subscription
4. Resource group: `AIChatBot-97aa`
5. Pricing tier: F0 (Free)
6. Microsoft App ID: Use the App ID from Step 1 above
7. Messaging endpoint: `https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/api/teams/messages`

### 3. Configure Teams Channel

In your Azure Bot Service:

1. Go to Channels
2. Click on Microsoft Teams icon
3. Click "Apply" to enable Teams channel
4. Test the bot connection

### 4. Upload Teams App Package

1. Go to: https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/api/teams/manifest/download
2. Download the zip file
3. In Microsoft Teams: Apps → Manage your apps → Upload an app → Upload a custom app
4. Select the downloaded zip file
5. Click "Add"

### 5. Test

After completing these steps:
1. Open the DTCE AI Assistant in Teams
2. Send a test message like "hello"
3. You should get a response instead of "Failed to send"

## Alternative Quick Test

You can test if the web chat works by going to:
https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net

If web chat works but Teams doesn't, it confirms the authentication issue.
