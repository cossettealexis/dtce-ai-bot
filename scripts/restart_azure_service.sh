#!/bin/bash
# Azure App Service Deployment and Restart Script

echo "🚀 DTCE AI Bot - Azure Deployment Check"
echo "=================================="

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install it first:"
    echo "   brew install azure-cli"
    exit 1
fi

# Variables
RESOURCE_GROUP="dtce-ai-rg"
APP_SERVICE_NAME="dtceai-backend-cyashrb8hnc2ayhp"
REGION="New Zealand North"

echo "📍 Resource Group: $RESOURCE_GROUP"
echo "🌐 App Service: $APP_SERVICE_NAME"
echo "📍 Region: $REGION"
echo ""

# Check Azure login status
echo "🔐 Checking Azure login status..."
if ! az account show &> /dev/null; then
    echo "❌ Not logged into Azure. Please run: az login"
    exit 1
fi

echo "✅ Azure CLI logged in"
echo ""

# Check App Service status
echo "🔍 Checking App Service status..."
APP_STATUS=$(az webapp show --resource-group "$RESOURCE_GROUP" --name "$APP_SERVICE_NAME" --query "state" -o tsv 2>/dev/null)

if [ $? -ne 0 ]; then
    echo "❌ Failed to get App Service status. Check resource group and app name."
    exit 1
fi

echo "📊 App Service Status: $APP_STATUS"

if [ "$APP_STATUS" != "Running" ]; then
    echo "⚠️ App Service is not running!"
    echo "🔄 Starting App Service..."
    az webapp start --resource-group "$RESOURCE_GROUP" --name "$APP_SERVICE_NAME"
    echo "✅ App Service start command sent"
else
    echo "✅ App Service is running"
    echo "🔄 Restarting App Service to refresh..."
    az webapp restart --resource-group "$RESOURCE_GROUP" --name "$APP_SERVICE_NAME"
    echo "✅ App Service restart command sent"
fi

echo ""
echo "⏳ Waiting for service to be ready..."
sleep 30

# Test health endpoint
echo "🏥 Testing health endpoint..."
HEALTH_URL="https://$APP_SERVICE_NAME.azurewebsites.net/health"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" --max-time 30)

if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ Health check passed! Bot should be working now."
    echo "🤖 Test the bot in Microsoft Teams"
else
    echo "❌ Health check failed (HTTP $HTTP_STATUS)"
    echo "🔍 Check the App Service logs in Azure Portal"
    echo "📋 Logs: Azure Portal > App Services > $APP_SERVICE_NAME > Monitoring > Log stream"
fi

echo ""
echo "🔗 Useful Links:"
echo "   📊 Azure Portal: https://portal.azure.com"
echo "   🤖 App Service: https://portal.azure.com/#resource/subscriptions/.../resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$APP_SERVICE_NAME"
echo "   📋 Logs: https://portal.azure.com/#resource/subscriptions/.../resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$APP_SERVICE_NAME/logStream"
