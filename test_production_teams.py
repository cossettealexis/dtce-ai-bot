#!/usr/bin/env python3
"""
PRODUCTION DIAGNOSTIC: Test production environment through Teams webhook
This will test the exact same path that Teams calls in production
"""
import asyncio
import json
import aiohttp
import sys
import os

async def test_production_teams_bot():
    """Test the production Teams bot by calling its endpoint directly."""
    
    # Production Teams bot endpoint
    production_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/api/messages"
    
    # Create a test Teams message payload
    test_message = {
        "type": "message",
        "id": "test-message-id",
        "timestamp": "2025-09-09T12:00:00.000Z",
        "serviceUrl": "https://smba.trafficmanager.net/teams/",
        "channelId": "msteams",
        "from": {
            "id": "test-user-id",
            "name": "Test User"
        },
        "conversation": {
            "id": "test-conversation-id"
        },
        "recipient": {
            "id": "test-bot-id",
            "name": "DTCE AI Bot"
        },
        "text": "What is our wellness policy?",
        "textFormat": "plain",
        "locale": "en-US"
    }
    
    print("🔍 TESTING PRODUCTION TEAMS BOT")
    print("=" * 80)
    print(f"Endpoint: {production_url}")
    print(f"Test question: {test_message['text']}")
    print()
    
    try:
        async with aiohttp.ClientSession() as session:
            print("📤 Sending request to production...")
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'DebugClient/1.0'
            }
            
            async with session.post(
                production_url, 
                json=test_message,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                print(f"📊 Response Status: {response.status}")
                print(f"📊 Response Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    result = await response.text()
                    print("✅ SUCCESS - Production bot responded")
                    print(f"Response: {result}")
                else:
                    error_text = await response.text()
                    print(f"❌ ERROR - Status {response.status}")
                    print(f"Error: {error_text}")
                    
    except aiohttp.ClientError as e:
        print(f"❌ CONNECTION ERROR: {str(e)}")
    except asyncio.TimeoutError:
        print("❌ TIMEOUT: Production bot didn't respond within 30 seconds")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {str(e)}")

async def test_production_health_check():
    """Test if production service is running and configured."""
    
    health_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/health"
    config_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/api/config-status"
    
    print("🩺 PRODUCTION HEALTH CHECK")
    print("=" * 50)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test health endpoint
            print("Testing health endpoint...")
            async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    health_data = await response.json()
                    print(f"✅ Health: {health_data}")
                else:
                    print(f"❌ Health check failed: {response.status}")
            
            # Test config status
            print("\nTesting config status...")
            async with session.get(config_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    config_data = await response.json()
                    print(f"✅ Config: {json.dumps(config_data, indent=2)}")
                else:
                    print(f"❌ Config check failed: {response.status}")
                    
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")

async def main():
    """Run all production diagnostics."""
    await test_production_health_check()
    print("\n")
    await test_production_teams_bot()

if __name__ == "__main__":
    asyncio.run(main())
