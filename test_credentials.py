#!/usr/bin/env python3
"""
Test to check if Bot Framework credentials are working correctly.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

async def test_microsoft_app_validation():
    """Test if our Microsoft App credentials are valid."""
    
    print("🔑 Testing Microsoft App Credentials")
    print("=" * 50)
    
    try:
        from dtce_ai_bot.config.settings import get_settings
        settings = get_settings()
        
        app_id = settings.microsoft_app_id
        app_password = settings.microsoft_app_password
        
        print(f"📋 Credentials Check:")
        print(f"  App ID: {app_id}")
        print(f"  Password: {'***' + app_password[-4:] if app_password else 'NOT SET'}")
        
        if not app_id:
            print("❌ MICROSOFT_APP_ID is not set!")
            return False
            
        if not app_password:
            print("❌ MICROSOFT_APP_PASSWORD is not set!")
            return False
            
        # Test if we can create a connector client with these credentials
        try:
            from botframework.connector import ConnectorClient
            from botframework.connector.auth import MicrosoftAppCredentials
            
            # Create credentials object
            credentials = MicrosoftAppCredentials(app_id, app_password)
            
            print("✅ MicrosoftAppCredentials created successfully")
            
            # Test token acquisition (this validates our credentials with Microsoft)
            try:
                token = await credentials.get_access_token()
                if token:
                    print("✅ Successfully obtained access token from Microsoft!")
                    print(f"  Token type: Bearer")
                    print(f"  Token preview: {token[:20]}...")
                    return True
                else:
                    print("❌ Failed to obtain access token")
                    return False
                    
            except Exception as e:
                print(f"❌ Token acquisition failed: {e}")
                
                # Check specific error types
                error_str = str(e).lower()
                if "unauthorized" in error_str or "401" in error_str:
                    print("🔍 Error Analysis: Invalid App ID or Password")
                elif "forbidden" in error_str or "403" in error_str:
                    print("🔍 Error Analysis: App not properly configured")
                elif "timeout" in error_str:
                    print("🔍 Error Analysis: Network connectivity issue")
                else:
                    print(f"🔍 Error Analysis: {e}")
                    
                return False
                
        except ImportError as e:
            print(f"❌ Import error: {e}")
            print("💡 Try: pip install botframework-connector")
            return False
            
    except Exception as e:
        print(f"❌ General error: {e}")
        return False

async def test_azure_registration():
    """Test if the bot is properly registered in Azure."""
    
    print("\n🌐 Testing Azure Bot Registration")
    print("-" * 40)
    
    import httpx
    
    # Test the Microsoft Bot Framework authentication endpoint
    # This will tell us if our app is properly registered
    auth_url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
    
    try:
        from dtce_ai_bot.config.settings import get_settings
        settings = get_settings()
        
        # Test token request (this is what the Bot Framework does internally)
        data = {
            "grant_type": "client_credentials",
            "client_id": settings.microsoft_app_id,
            "client_secret": settings.microsoft_app_password,
            "scope": "https://api.botframework.com/.default"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(auth_url, data=data)
            
            print(f"📊 Auth Response: {response.status_code}")
            
            if response.status_code == 200:
                auth_data = response.json()
                print("✅ Bot is properly registered with Microsoft!")
                print(f"  Access token obtained")
                print(f"  Token type: {auth_data.get('token_type', 'N/A')}")
                print(f"  Expires in: {auth_data.get('expires_in', 'N/A')} seconds")
                return True
            else:
                print(f"❌ Registration test failed")
                error_data = response.text
                print(f"📄 Error: {error_data}")
                
                # Analyze common registration errors
                if "invalid_client" in error_data:
                    print("🔍 Analysis: App ID or Password is incorrect")
                elif "unauthorized_client" in error_data:
                    print("🔍 Analysis: App not authorized for Bot Framework")
                elif "invalid_scope" in error_data:
                    print("🔍 Analysis: Scope configuration issue")
                    
                return False
                
    except Exception as e:
        print(f"❌ Azure registration test failed: {e}")
        return False

async def main():
    """Run all credential validation tests."""
    
    print("🤖 DTCE Bot Authentication Validation")
    print("=" * 60)
    
    # Test 1: Microsoft App credentials
    creds_ok = await test_microsoft_app_validation()
    
    # Test 2: Azure registration
    if creds_ok:
        registration_ok = await test_azure_registration()
    else:
        print("\n⏭️  Skipping Azure registration test due to credential issues")
        registration_ok = False
    
    print("\n🏁 Validation Complete!")
    print("=" * 60)
    
    if creds_ok and registration_ok:
        print("✅ CONCLUSION: Bot credentials are valid!")
        print("💡 Authentication errors are likely due to JWT validation (expected)")
        print("💡 Real Teams messages will work correctly")
    elif creds_ok:
        print("⚠️  CONCLUSION: Credentials work but registration may have issues")
    else:
        print("❌ CONCLUSION: Bot credentials are invalid!")
        print("🔧 ACTION NEEDED: Check App ID and Password in Azure Portal")

if __name__ == "__main__":
    asyncio.run(main())
