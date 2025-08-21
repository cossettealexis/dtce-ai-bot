#!/bin/bash

# Quick Setup Script for Existing Azure Resources
# This script configures your existing Azure resources for the DTCE AI Bot

echo "🚀 DTCE AI Bot - Azure Deployment Setup"
echo "========================================"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI is not installed. Please install it first."
    echo "   Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if user is logged in to Azure
if ! az account show &> /dev/null; then
    echo "❌ Please log in to Azure CLI first:"
    echo "   Run: az login"
    exit 1
fi

echo "✅ Azure CLI is ready"

# Get resource group
echo ""
echo "📋 Finding your resource group..."
RESOURCE_GROUPS=$(az group list --query "[?contains(name, 'dtce') || contains(name, 'ai') || contains(name, 'chat')].name" -o tsv)

if [ -z "$RESOURCE_GROUPS" ]; then
    echo "❓ Could not auto-detect resource group. Please enter it manually:"
    read -p "Resource Group Name: " RESOURCE_GROUP
else
    echo "Found resource groups:"
    echo "$RESOURCE_GROUPS"
    echo ""
    read -p "Enter your resource group name: " RESOURCE_GROUP
fi

echo "Using resource group: $RESOURCE_GROUP"

# Verify resources exist
echo ""
echo "🔍 Verifying your Azure resources..."

# Check App Service
if az webapp show --name dtceai-backend --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo "✅ App Service 'dtceai-backend' found"
else
    echo "❌ App Service 'dtceai-backend' not found in resource group '$RESOURCE_GROUP'"
    exit 1
fi

# Check Storage Account
if az storage account show --name dtceaistorage --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo "✅ Storage Account 'dtceaistorage' found"
else
    echo "❌ Storage Account 'dtceaistorage' not found in resource group '$RESOURCE_GROUP'"
    exit 1
fi

# Check Cognitive Search
if az search service show --name dtceai-search --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo "✅ Cognitive Search 'dtceai-search' found"
else
    echo "❌ Cognitive Search 'dtceai-search' not found in resource group '$RESOURCE_GROUP'"
    exit 1
fi

# Check OpenAI
if az cognitiveservices account show --name dtceai-gpt --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo "✅ Azure OpenAI 'dtceai-gpt' found"
else
    echo "❌ Azure OpenAI 'dtceai-gpt' not found in resource group '$RESOURCE_GROUP'"
    exit 1
fi

# Check Form Recognizer
if az cognitiveservices account show --name dtceai-form-recognizer --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo "✅ Form Recognizer 'dtceai-form-recognizer' found"
else
    echo "❌ Form Recognizer 'dtceai-form-recognizer' not found in resource group '$RESOURCE_GROUP'"
    exit 1
fi

echo ""
echo "🔧 Configuring environment variables..."

# Get Azure OpenAI deployment name
echo "Getting OpenAI deployments..."
DEPLOYMENTS=$(az cognitiveservices account deployment list --name dtceai-gpt --resource-group $RESOURCE_GROUP --query "[].name" -o tsv)
if [ -n "$DEPLOYMENTS" ]; then
    echo "Available OpenAI deployments:"
    echo "$DEPLOYMENTS"
    read -p "Enter your OpenAI deployment name (e.g., gpt-4, gpt-35-turbo): " OPENAI_DEPLOYMENT
else
    echo "❓ Could not find OpenAI deployments. Using default 'gpt-4'"
    OPENAI_DEPLOYMENT="gpt-4"
fi

# Set environment variables
echo "Setting up environment variables..."
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
    AZURE_OPENAI_DEPLOYMENT_NAME=$OPENAI_DEPLOYMENT \
    AZURE_FORM_RECOGNIZER_ENDPOINT="$(az cognitiveservices account show --name dtceai-form-recognizer --resource-group $RESOURCE_GROUP --query 'properties.endpoint' -o tsv)" \
    AZURE_FORM_RECOGNIZER_API_KEY="$(az cognitiveservices account keys list --name dtceai-form-recognizer --resource-group $RESOURCE_GROUP --query 'key1' -o tsv)"

echo "✅ Base environment variables configured!"

# Set startup command
echo "Setting startup command..."
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name dtceai-backend \
  --startup-file "python startup.py"

echo "✅ Startup command configured!"

# Setup git deployment
echo ""
read -p "Do you want to set up Git deployment? (y/n): " SETUP_GIT

if [[ $SETUP_GIT == "y" || $SETUP_GIT == "Y" ]]; then
    echo "Setting up Git deployment..."
    
    # Configure local git deployment
    az webapp deployment source config-local-git \
      --name dtceai-backend \
      --resource-group $RESOURCE_GROUP
    
    # Get deployment URL
    DEPLOY_URL=$(az webapp deployment list-publishing-credentials --name dtceai-backend --resource-group $RESOURCE_GROUP --query 'scmUri' -o tsv)
    
    echo ""
    echo "📝 Git deployment configured!"
    echo "To deploy your code, run:"
    echo "  git remote add azure $DEPLOY_URL"
    echo "  git push azure main"
fi

echo ""
echo "🎉 Setup Complete!"
echo "==================="
echo "Your Azure resources are now configured for the DTCE AI Bot."
echo ""
echo "⚠️  IMPORTANT: You still need to set these environment variables manually:"
echo "   - MICROSOFT_TENANT_ID"
echo "   - MICROSOFT_CLIENT_ID" 
echo "   - MICROSOFT_CLIENT_SECRET"
echo ""
echo "Add these in the Azure Portal:"
echo "1. Go to your App Service 'dtceai-backend'"
echo "2. Navigate to Configuration > Application settings"
echo "3. Add the Microsoft credentials"
echo ""
echo "🌐 Your app will be available at:"
echo "   https://dtceai-backend.azurewebsites.net"
echo ""
echo "📋 To check the deployment status:"
echo "   az webapp log tail --name dtceai-backend --resource-group $RESOURCE_GROUP"
