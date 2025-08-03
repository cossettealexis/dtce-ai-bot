#!/usr/bin/env python3
"""
Deployment script for DTCE Teams Bot to Azure App Service.
"""

import os
import subprocess
import json
from pathlib import Path


def create_azure_deploy_config():
    """Create Azure deployment configuration files."""
    
    print("🚀 Creating Azure deployment configuration...")
    
    # Create requirements.txt for Azure
    requirements_content = """
# FastAPI and web framework
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6

# Microsoft Teams Bot Framework
botbuilder-core==4.15.0
botbuilder-schema==4.15.0
botbuilder-integration-aiohttp==4.15.0
aiohttp==3.8.5
aiohttp-cors==0.7.0

# Microsoft Graph API and authentication
msal==1.25.0
requests==2.31.0

# Azure services
azure-storage-blob==12.19.0
azure-search-documents==11.4.0
azure-cognitiveservices-language-textanalytics==5.3.0
openai==1.3.7

# Document processing
python-docx==1.1.0
PyPDF2==3.0.1
openpyxl==3.1.2
python-magic==0.4.27

# Environment and configuration
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Logging and utilities
structlog==23.2.0
rich==13.7.0
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements_content.strip())
    
    # Create startup script for Azure App Service
    startup_script = """#!/bin/bash
echo "Starting DTCE AI Assistant Teams Bot..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000
"""
    
    with open("startup.sh", "w") as f:
        f.write(startup_script)
    
    # Make startup script executable
    os.chmod("startup.sh", 0o755)
    
    # Create .deployment file for Azure
    deployment_config = """[config]
command = startup.sh
"""
    
    with open(".deployment", "w") as f:
        f.write(deployment_config)
    
    print("✅ Azure deployment files created")


def create_docker_config():
    """Create Docker configuration for container deployment."""
    
    print("🐳 Creating Docker configuration...")
    
    dockerfile_content = """
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    
    with open("Dockerfile", "w") as f:
        f.write(dockerfile_content.strip())
    
    # Docker compose for local testing
    docker_compose_content = """
version: '3.8'
services:
  dtce-ai-bot:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
"""
    
    with open("docker-compose.yml", "w") as f:
        f.write(docker_compose_content.strip())
    
    print("✅ Docker configuration created")


def print_deployment_instructions():
    """Print deployment instructions."""
    
    print("\n" + "="*60)
    print("🚀 AZURE DEPLOYMENT INSTRUCTIONS")
    print("="*60)
    
    print("""
1. PREPARE AZURE APP SERVICE:
   az webapp create \\
     --resource-group AIChatBot \\
     --plan <your-plan> \\
     --name dtceai-backend \\
     --runtime "PYTHON|3.10"

2. CONFIGURE ENVIRONMENT VARIABLES:
   Go to Azure Portal → App Service → Configuration
   Add all variables from your .env file:
   - MICROSOFT_APP_ID
   - MICROSOFT_APP_PASSWORD
   - MICROSOFT_APP_TENANT_ID
   - MICROSOFT_CLIENT_ID
   - MICROSOFT_TENANT_ID
   - MICROSOFT_CLIENT_SECRET
   - SHAREPOINT_SITE_ID
   - AZURE_STORAGE_CONNECTION_STRING
   - AZURE_SEARCH_SERVICE_NAME
   - AZURE_SEARCH_ADMIN_KEY
   - AZURE_OPENAI_ENDPOINT
   - AZURE_OPENAI_API_KEY

3. DEPLOY CODE:
   Option A - ZIP Deploy:
   az webapp deployment source config-zip \\
     --resource-group AIChatBot \\
     --name dtceai-backend \\
     --src deployment.zip

   Option B - Git Deploy:
   git remote add azure <git-url-from-azure>
   git push azure main

   Option C - GitHub Actions:
   Connect your GitHub repo in Azure Portal

4. SET BOT MESSAGING ENDPOINT:
   - Go to Azure Bot Service
   - Set messaging endpoint: https://dtceai-backend.azurewebsites.net/api/messages
   - Test the endpoint

5. DEPLOY TEAMS APP:
   - Upload teams-app/DTCE-AI-Assistant.zip to Teams Admin Center
   - Approve for your organization
   - Install in Teams

6. TEST DEPLOYMENT:
   curl https://dtceai-backend.azurewebsites.net/health
   
ALTERNATIVE - DOCKER DEPLOYMENT:
   docker build -t dtceai-bot .
   docker run -p 8000:8000 --env-file .env dtceai-bot
""")


def create_deployment_package():
    """Create deployment package."""
    
    print("📦 Creating deployment package...")
    
    import zipfile
    
    # Files to include in deployment
    files_to_include = [
        "main.py",
        "config.py",
        "requirements.txt",
        "startup.sh",
        ".deployment",
        "src/",
        "teams-app/"
    ]
    
    # Create zip file
    with zipfile.ZipFile("deployment.zip", "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in files_to_include:
            path = Path(file_path)
            if path.is_file():
                zip_file.write(path, path.name)
            elif path.is_dir():
                for file in path.rglob("*"):
                    if file.is_file():
                        zip_file.write(file, file.relative_to("."))
    
    print("✅ Deployment package created: deployment.zip")


def main():
    """Main deployment preparation function."""
    
    print("🚀 DTCE Teams Bot Deployment Preparation")
    print("="*45)
    
    # Create deployment configurations
    create_azure_deploy_config()
    create_docker_config()
    create_deployment_package()
    
    # Print instructions
    print_deployment_instructions()
    
    print("\n✅ Deployment preparation completed!")
    print("\nFiles created:")
    print("- requirements.txt (updated)")
    print("- startup.sh (Azure startup script)")
    print("- .deployment (Azure config)")
    print("- Dockerfile")
    print("- docker-compose.yml") 
    print("- deployment.zip (ready for Azure)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Deployment preparation failed: {e}")
