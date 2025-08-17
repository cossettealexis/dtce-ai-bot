#!/usr/bin/env python3
"""
Script to verify Bot Framework registration after setup.
Run this AFTER creating the Bot Channels Registration in Azure.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

async def verify_bot_registration():
    """Verify if the bot is now properly registered."""
    
    print("🔍 Verifying Bot Framework Registration")
    print("=" * 50)
    
    import httpx
    
    try:
        from dtce_ai_bot.config.settings import get_settings
        settings = get_settings()
        
        # Test the Microsoft Bot Framework authentication
        auth_url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
        
        data = {
            "grant_type": "client_credentials",
            "client_id": settings.microsoft_app_id,
            "client_secret": settings.microsoft_app_password,
            "scope": "https://api.botframework.com/.default"
        }
        
        print(f"🔑 Testing App ID: {settings.microsoft_app_id}")
        print(f"🔒 Testing Password: ***{settings.microsoft_app_password[-4:]}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(auth_url, data=data)
            
            print(f"\n📊 Auth Response: {response.status_code}")
            
            if response.status_code == 200:
                auth_data = response.json()
                print("✅ SUCCESS: Bot is properly registered with Bot Framework!")
                print(f"  ✅ Access token obtained")
                print(f"  ✅ Token type: {auth_data.get('token_type', 'N/A')}")
                print(f"  ✅ Expires in: {auth_data.get('expires_in', 'N/A')} seconds")
                
                # Now test the messaging endpoint
                print(f"\n🌐 Testing messaging endpoint...")
                return await test_messaging_endpoint_with_valid_token(auth_data['access_token'])
                
            else:
                print(f"❌ FAILED: Bot registration issue")
                error_data = response.text
                print(f"📄 Error: {error_data}")
                
                if "invalid_client" in error_data:
                    print("\n🔧 SOLUTION: Create Bot Channels Registration in Azure Portal")
                    print("   1. Go to Azure Portal")
                    print("   2. Create Resource → Bot Channels Registration")
                    print("   3. Use existing App ID: c185c174-26f6-4876-b847-0a423d07d1f3")
                    print("   4. Set messaging endpoint: https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/api/teams/messages")
                    
                return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def test_messaging_endpoint_with_valid_token(access_token):
    """Test the messaging endpoint with a valid Microsoft token."""
    
    print("📨 Testing messaging endpoint with valid token...")
    
    import httpx
    from datetime import datetime, UTC
    
    # Create a proper Teams message
    teams_activity = {
        "type": "message",
        "id": "test-message-123",
        "timestamp": datetime.now(UTC).isoformat(),
        "channelId": "msteams",
        "serviceUrl": "https://smba.trafficmanager.net/teams/",
        "from": {
            "id": "29:test-user-id",
            "name": "Test User"
        },
        "conversation": {
            "id": "a:test-conversation-id"
        },
        "recipient": {
            "id": "28:c185c174-26f6-4876-b847-0a423d07d1f3",
            "name": "DTCE AI Assistant"
        },
        "text": "Hello bot! This is a test message."
    }
    
    endpoint = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/api/teams/messages"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            endpoint,
            json=teams_activity,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Microsoft-BotFramework/3.1"
            }
        )
        
        print(f"📊 Endpoint Response: {response.status_code}")
        print(f"📄 Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Messaging endpoint is working!")
            return True
        else:
            print(f"⚠️  Endpoint issue: {response.status_code}")
            return False

async def main():
    """Main verification process."""
    
    print("🤖 Bot Framework Registration Verification")
    print("=" * 60)
    print("Run this AFTER creating Bot Channels Registration in Azure!")
    print("=" * 60)
    
    success = await verify_bot_registration()
    
    print(f"\n🏁 Verification Complete!")
    print("=" * 60)
    
    if success:
        print("🎉 CELEBRATION: Your bot is fully working!")
        print("📱 Next steps:")
        print("   1. Add Teams channel in Azure Bot registration")
        print("   2. Install the Teams app using your manifest")
        print("   3. Test real conversations in Teams")
    else:
        print("🔧 ACTION REQUIRED:")
        print("   1. Create Bot Channels Registration in Azure Portal")
        print("   2. Use App ID: c185c174-26f6-4876-b847-0a423d07d1f3")
        print("   3. Set messaging endpoint: https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/api/teams/messages")
        print("   4. Run this script again to verify")

if __name__ == "__main__":
    asyncio.run(main())
