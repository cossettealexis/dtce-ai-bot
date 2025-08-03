#!/usr/bin/env python3
"""
Setup script for DTCE AI Assistant.
This script helps with initial configuration and Azure service setup.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.10 or higher."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("❌ Python 3.10 or higher is required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        import pip
        result = subprocess.run([sys.executable, "-m", "pip", "check"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ All dependencies are properly installed")
            return True
        else:
            print("⚠️ Some dependency issues found:")
            print(result.stdout)
            return False
            
    except Exception as e:
        print(f"❌ Error checking dependencies: {e}")
        return False


def install_dependencies():
    """Install required dependencies."""
    print("📦 Installing dependencies...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True, capture_output=True, text=True)
        
        print("✅ Dependencies installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print(e.stdout)
        print(e.stderr)
        return False


def create_env_file():
    """Create .env file from template if it doesn't exist."""
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    if not env_example.exists():
        print("❌ .env.example template not found")
        return False
    
    try:
        shutil.copy(env_example, env_file)
        print("✅ Created .env file from template")
        print("⚠️  Please edit .env file with your actual credentials")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False


def validate_env_file():
    """Validate that .env file has required variables."""
    
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        return False
    
    required_vars = [
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_TENANT_ID",
        "SHAREPOINT_SITE_ID",
        "AZURE_STORAGE_CONNECTION_STRING",
        "AZURE_SEARCH_SERVICE_NAME",
        "AZURE_SEARCH_ADMIN_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY"
    ]
    
    try:
        with open(env_file, 'r') as f:
            content = f.read()
        
        missing_vars = []
        for var in required_vars:
            if f"{var}=your_" in content or f"{var}=" not in content:
                missing_vars.append(var)
        
        if missing_vars:
            print("⚠️  Please configure these variables in .env:")
            for var in missing_vars:
                print(f"   - {var}")
            return False
        else:
            print("✅ .env file appears to be configured")
            return True
            
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False


def print_azure_setup_guide():
    """Print guide for setting up Azure services."""
    
    print("\n" + "="*60)
    print("🔧 AZURE SERVICES SETUP GUIDE")
    print("="*60)
    
    print("""
1. Create Resource Group:
   - Name: AIChatBot (or your preferred name)
   - Region: East US (recommended)

2. Create Storage Account:
   - Name: dtceaistorage (must be unique)
   - Performance: Standard
   - Replication: LRS
   - Note the connection string

3. Create Cognitive Search:
   - Name: dtceai-search (must be unique)  
   - Pricing Tier: Basic (for testing)
   - Note the admin key

4. Create OpenAI Service:
   - Name: dtceai-gpt (must be unique)
   - Region: East US
   - Deploy gpt-35-turbo model
   - Note the endpoint and API key

5. Create App Service (optional, for deployment):
   - Name: dtceai-backend
   - Runtime: Python 3.10
   - OS: Linux
   - Plan: Basic B1 (for testing)

6. Configure Microsoft Graph API:
   - Register app in Azure AD
   - Add permissions: Sites.Read.All, Files.Read.All
   - Note client ID and tenant ID
   - Optional: Create client secret for production
""")


def print_next_steps():
    """Print next steps after setup."""
    
    print("\n" + "="*60)
    print("🚀 NEXT STEPS")
    print("="*60)
    
    print("""
1. Configure your .env file with actual credentials

2. Test SharePoint connection:
   python test_sharepoint.py

3. Test Azure services:
   python test_azure.py

4. Start the application:
   python main.py

5. Test the API:
   curl http://localhost:8000/health

6. Begin document ingestion:
   curl -X POST http://localhost:8000/api/ingest/start

For detailed instructions, see README.md
""")


def main():
    """Main setup function."""
    
    print("🚀 DTCE AI Assistant Setup")
    print("="*40)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install dependencies
    print("\n📦 Checking dependencies...")
    if not check_dependencies():
        print("Installing missing dependencies...")
        if not install_dependencies():
            return False
    
    # Create .env file
    print("\n⚙️ Setting up configuration...")
    if not create_env_file():
        return False
    
    # Validate environment
    print("\n🔍 Validating configuration...")
    env_configured = validate_env_file()
    
    # Print setup guides
    if not env_configured:
        print_azure_setup_guide()
    
    print_next_steps()
    
    if env_configured:
        print("✅ Setup completed! You're ready to run the application.")
    else:
        print("⚠️  Setup partially completed. Please configure your .env file.")
    
    return True


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
