#!/usr/bin/env python3
"""
Setup script for DTCE Teams Bot deployment.
This script helps configure the Teams bot for Microsoft Teams.
"""

import os
import json
import zipfile
from pathlib import Path
import shutil


def create_teams_app_package():
    """Create Teams app package (.zip file) for deployment."""
    
    print("📦 Creating Teams App Package...")
    
    # Ensure we have the required environment variables
    app_id = os.getenv('MICROSOFT_APP_ID')
    if not app_id:
        print("❌ MICROSOFT_APP_ID not found in environment variables")
        print("   Please set this in your .env file")
        return False
    
    # Create manifest with actual app ID
    manifest_path = Path("teams-app/manifest.json")
    with open(manifest_path, 'r') as f:
        manifest_content = f.read()
    
    # Replace placeholders with actual values
    manifest_content = manifest_content.replace("{{MICROSOFT_APP_ID}}", app_id)
    
    # Write updated manifest
    updated_manifest_path = Path("teams-app/manifest_generated.json")
    with open(updated_manifest_path, 'w') as f:
        f.write(manifest_content)
    
    # Create app package zip
    package_path = Path("teams-app/DTCE-AI-Assistant.zip")
    
    with zipfile.ZipFile(package_path, 'w') as zip_file:
        # Add manifest
        zip_file.write(updated_manifest_path, "manifest.json")
        
        # Add icons (using placeholders for now)
        create_placeholder_icons()
        zip_file.write("teams-app/icon-color.png", "icon-color.png")
        zip_file.write("teams-app/icon-outline.png", "icon-outline.png")
    
    print(f"✅ Teams app package created: {package_path}")
    print(f"📋 App ID: {app_id}")
    
    # Clean up
    updated_manifest_path.unlink()
    
    return True


def create_placeholder_icons():
    """Create placeholder icon files."""
    
    # This creates simple placeholder PNG files
    # In production, you should create proper icons
    
    import base64
    
    # Minimal PNG data (1x1 pixel blue)
    color_png_data = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    )
    
    # Minimal PNG data (1x1 pixel transparent)
    outline_png_data = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQIHWNgAAIAAAUAAY27m/MAAAAASUVORK5CYII='
    )
    
    with open("teams-app/icon-color.png", 'wb') as f:
        f.write(color_png_data)
    
    with open("teams-app/icon-outline.png", 'wb') as f:
        f.write(outline_png_data)


def print_teams_setup_instructions():
    """Print instructions for setting up the Teams bot."""
    
    print("\n" + "="*60)
    print("🤖 MICROSOFT TEAMS BOT SETUP INSTRUCTIONS")
    print("="*60)
    
    print("""
1. REGISTER BOT IN AZURE:
   a) Go to Azure Portal → Bot Services → Create
   b) Choose "Multi Tenant" bot
   c) Set messaging endpoint: https://your-domain.com/api/messages
   d) Note down App ID and create App Password
   e) Update .env file with:
      - MICROSOFT_APP_ID=<your-app-id>
      - MICROSOFT_APP_PASSWORD=<your-app-password>
      - MICROSOFT_APP_TENANT_ID=<your-tenant-id>

2. DEPLOY YOUR BOT:
   a) Deploy this application to Azure App Service
   b) Ensure the /api/messages endpoint is accessible
   c) Test with Bot Framework Emulator

3. INSTALL IN TEAMS:
   a) Go to Teams Admin Center
   b) Navigate to Teams apps → Manage apps
   c) Upload the DTCE-AI-Assistant.zip package
   d) Approve the app for your organization

4. ADD TO TEAMS:
   a) In Microsoft Teams, go to Apps
   b) Search for "DTCE AI Assistant"
   c) Click "Add" to install the bot
   d) Start chatting with the bot!

5. TEAM/CHANNEL INSTALLATION:
   a) Go to any Team or Channel
   b) Click + to add a tab/app
   c) Search for "DTCE AI Assistant"
   d) Add the bot to enable team-wide access

EXAMPLE USAGE:
- Personal chat: Direct message the bot
- Team chat: @mention the bot in channels
- Commands: /help, /projects, /health
- Queries: "Show me bridge projects from 2024"
""")


def validate_teams_configuration():
    """Validate Teams bot configuration."""
    
    print("🔍 Validating Teams Bot Configuration...")
    
    required_vars = [
        "MICROSOFT_APP_ID",
        "MICROSOFT_APP_PASSWORD", 
        "MICROSOFT_APP_TENANT_ID"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required Teams bot variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    
    print("✅ Teams bot environment variables configured")
    
    # Check if manifest exists
    manifest_path = Path("teams-app/manifest.json")
    if not manifest_path.exists():
        print("❌ Teams manifest.json not found")
        return False
    
    print("✅ Teams manifest found")
    return True


def main():
    """Main setup function for Teams bot."""
    
    print("🤖 DTCE Teams Bot Setup")
    print("="*30)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Validate configuration
    if not validate_teams_configuration():
        print("\n⚠️  Please configure Teams bot settings in .env file")
        print_teams_setup_instructions()
        return
    
    # Create app package
    if create_teams_app_package():
        print_teams_setup_instructions()
        print("\n✅ Teams bot setup completed!")
        print("\nNext steps:")
        print("1. Deploy your bot to Azure App Service")
        print("2. Upload DTCE-AI-Assistant.zip to Teams Admin Center")
        print("3. Install the bot in Microsoft Teams")
    else:
        print("\n❌ Teams bot setup failed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
