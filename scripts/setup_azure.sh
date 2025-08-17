#!/bin/bash
# =============================================================================
# DTCE AI Assistant - Azure Setup Helper
# =============================================================================
# This script helps set up Azure resources for the DTCE AI Assistant

set -e

echo "☁️  DTCE AI Assistant - Azure Setup Helper"
echo "This script will help you create the required Azure resources"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install it first:"
    echo "https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    echo "🔐 Please log in to Azure CLI:"
    az login
fi

# Get subscription info
SUBSCRIPTION=$(az account show --query "name" -o tsv)
echo "📋 Using subscription: $SUBSCRIPTION"

# Set default values
RESOURCE_GROUP="dtce-ai-rg"
LOCATION="eastus"
STORAGE_ACCOUNT="dtceaidocs$(date +%s)"
FORM_RECOGNIZER="dtce-form-recognizer"
APP_NAME="dtce-ai-assistant"

echo ""
echo "🏗️  Creating Azure resources..."
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "Storage Account: $STORAGE_ACCOUNT"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Create resource group
echo "📁 Creating resource group..."
az group create --name $RESOURCE_GROUP --location $LOCATION
echo "✅ Resource group created"

# Create storage account
echo "💾 Creating storage account..."
az storage account create \
    --name $STORAGE_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku Standard_LRS
echo "✅ Storage account created"

# Create storage container
echo "📦 Creating storage container..."
az storage container create \
    --name documents \
    --account-name $STORAGE_ACCOUNT
echo "✅ Storage container created"

# Create Form Recognizer
echo "🔍 Creating Form Recognizer service..."
az cognitiveservices account create \
    --name $FORM_RECOGNIZER \
    --resource-group $RESOURCE_GROUP \
    --kind FormRecognizer \
    --sku S0 \
    --location $LOCATION
echo "✅ Form Recognizer service created"

# Get storage account key
echo "🔑 Retrieving storage account key..."
STORAGE_KEY=$(az storage account keys list \
    --account-name $STORAGE_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --query "[0].value" -o tsv)

# Get Form Recognizer key and endpoint
echo "🔑 Retrieving Form Recognizer credentials..."
FORM_RECOGNIZER_KEY=$(az cognitiveservices account keys list \
    --name $FORM_RECOGNIZER \
    --resource-group $RESOURCE_GROUP \
    --query "key1" -o tsv)

FORM_RECOGNIZER_ENDPOINT=$(az cognitiveservices account show \
    --name $FORM_RECOGNIZER \
    --resource-group $RESOURCE_GROUP \
    --query "properties.endpoint" -o tsv)

# Display results
echo ""
echo "🎉 Azure resources created successfully!"
echo ""
echo "📋 Add these values to your .env file:"
echo "AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT"
echo "AZURE_STORAGE_ACCOUNT_KEY=$STORAGE_KEY"
echo "AZURE_FORM_RECOGNIZER_ENDPOINT=$FORM_RECOGNIZER_ENDPOINT"
echo "AZURE_FORM_RECOGNIZER_KEY=$FORM_RECOGNIZER_KEY"
echo ""
echo "🔗 Next steps:"
echo "1. Create an App Registration for Microsoft Graph API access"
echo "2. Configure SharePoint permissions"
echo "3. Update your .env file with all credentials"
echo "4. Run the application with './scripts/run_dev.sh'"
echo ""
echo "For detailed setup instructions, see README.md"
