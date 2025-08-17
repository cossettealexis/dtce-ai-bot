#!/usr/bin/env python3
"""
Test to debug the exact authentication issue with Teams bot.
"""

import asyncio
import json
import httpx
from datetime import datetime, UTC

async def test_with_proper_teams_structure():
    """Test with a more authentic Teams message structure."""
    
    base_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    endpoint = f"{base_url}/api/teams/messages"
    
    # More authentic Teams activity structure
    teams_activity = {
        "type": "message",
        "id": "1234567890123456",
        "timestamp": datetime.now(UTC).isoformat(),
        "localTimestamp": datetime.now(UTC).isoformat(),
        "channelId": "msteams",
        "serviceUrl": "https://smba.trafficmanager.net/teams/",
        "from": {
            "id": "29:1XJKJMvcL2l9gg4U9lAcQ123456789",
            "name": "Test User",
            "aadObjectId": "12345678-1234-1234-1234-123456789012"
        },
        "conversation": {
            "conversationType": "personal",
            "tenantId": "c5f056c8-2c25-49a4-934c-9b4f78be4220",
            "id": "a:1a2b3c4d5e6f7g8h9i0j"
        },
        "recipient": {
            "id": "28:c185c174-26f6-4876-b847-0a423d07d1f3",
            "name": "DTCE AI Assistant"
        },
        "textFormat": "plain",
        "text": "Hello",
        "locale": "en-US",
        "channelData": {
            "tenant": {
                "id": "c5f056c8-2c25-49a4-934c-9b4f78be4220"
            },
            "source": {
                "name": "message"
            }
        }
    }
    
    print("🔄 Testing with proper Teams message structure...")
    print(f"📤 Message: {teams_activity['text']}")
    
    # Test 1: No Authorization header
    print("\n1️⃣ Test without Authorization header:")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            endpoint,
            json=teams_activity,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Microsoft-BotFramework/3.1"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    
    # Test 2: Empty Authorization header
    print("\n2️⃣ Test with empty Authorization header:")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            endpoint,
            json=teams_activity,
            headers={
                "Content-Type": "application/json",
                "Authorization": "",
                "User-Agent": "Microsoft-BotFramework/3.1"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    
    # Test 3: Bearer token format (fake)
    print("\n3️⃣ Test with Bearer token format:")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            endpoint,
            json=teams_activity,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer fake-jwt-token-for-testing",
                "User-Agent": "Microsoft-BotFramework/3.1"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

async def test_bot_configuration():
    """Test the bot configuration and credentials."""
    
    print("🔧 Testing bot configuration...")
    
    try:
        # Test loading settings
        import sys
        import os
        sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')
        
        from dtce_ai_bot.config.settings import get_settings
        settings = get_settings()
        
        print(f"✅ Settings loaded")
        print(f"MICROSOFT_APP_ID: {settings.microsoft_app_id}")
        print(f"MICROSOFT_APP_PASSWORD: {'***' + settings.microsoft_app_password[-4:] if settings.microsoft_app_password else 'NOT SET'}")
        print(f"MICROSOFT_APP_TYPE: {getattr(settings, 'microsoft_app_type', 'NOT SET')}")
        print(f"MICROSOFT_APP_TENANT_ID: {getattr(settings, 'microsoft_app_tenant_id', 'NOT SET')}")
        
        # Test adapter configuration
        from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
        
        bot_settings = BotFrameworkAdapterSettings(
            app_id=settings.microsoft_app_id or "",
            app_password=settings.microsoft_app_password or ""
        )
        
        adapter = BotFrameworkAdapter(bot_settings)
        print(f"✅ BotFrameworkAdapter created successfully")
        
        # Check if credentials are properly set
        if not settings.microsoft_app_id:
            print("❌ MICROSOFT_APP_ID is not set!")
        if not settings.microsoft_app_password:
            print("❌ MICROSOFT_APP_PASSWORD is not set!")
            
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

async def main():
    """Run authentication debugging tests."""
    print("🔍 DTCE Teams Bot Authentication Debugging")
    print("=" * 60)
    
    # Test 1: Bot configuration
    print("\n🔧 Testing Bot Configuration")
    print("-" * 30)
    config_ok = await test_bot_configuration()
    
    if config_ok:
        # Test 2: Different message formats
        print("\n📨 Testing Message Authentication")
        print("-" * 30)
        await test_with_proper_teams_structure()
    else:
        print("❌ Skipping message tests due to configuration issues")
    
    print("\n🏁 Authentication Debug Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
