#!/usr/bin/env python3
"""
Test the actual Teams bot API endpoint /api/messages
This simulates exactly what Microsoft Teams sends to our bot
"""

import aiohttp
import asyncio
import json

async def test_teams_api_endpoint():
    """Test the actual /api/messages endpoint that Teams uses"""
    
    # Use the deployed Azure URL
    base_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    
    # Create a proper Teams bot framework message payload
    teams_message = {
        "type": "message",
        "id": "test-message-id",
        "timestamp": "2025-10-03T13:40:00.000Z",
        "channelId": "msteams",
        "serviceUrl": "https://smba.trafficmanager.net/teams/",
        "from": {
            "id": "29:test-user-id",
            "name": "Test User"
        },
        "conversation": {
            "id": "a:test-conversation-id",
            "conversationType": "personal"
        },
        "recipient": {
            "id": "28:bot-id",
            "name": "DTCE AI Bot"
        },
        "text": "test",
        "channelData": {
            "tenant": {
                "id": "test-tenant-id"
            }
        }
    }
    
    print("🤖 TESTING TEAMS BOT API ENDPOINT")
    print("=" * 60)
    print(f"URL: {base_url}/api/messages")
    print(f"Testing message: '{teams_message['text']}'")
    print("-" * 60)
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test the actual /api/messages endpoint
            async with session.post(
                f"{base_url}/api/messages",
                json=teams_message,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer fake-token"  # Teams would send real token
                },
                timeout=30
            ) as response:
                
                print(f"📊 Response Status: {response.status}")
                print(f"📋 Response Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    try:
                        result = await response.json()
                        print("✅ SUCCESS - Bot Response:")
                        print(json.dumps(result, indent=2))
                    except:
                        text_response = await response.text()
                        print("✅ SUCCESS - Text Response:")
                        print(text_response)
                        
                elif response.status == 401:
                    print("🔐 AUTH ERROR (expected - we don't have real Teams token)")
                    text = await response.text()
                    print(f"Response: {text}")
                    
                else:
                    text_response = await response.text()
                    print(f"❌ ERROR Response:")
                    print(text_response)
                    
        except Exception as e:
            print(f"💥 Connection Error: {e}")
    
    # Also test with a construction question
    print("\n" + "=" * 60)
    teams_message["text"] = "What are the maximum spans for 90x45mm joists?"
    print(f"Testing construction query: '{teams_message['text']}'")
    print("-" * 60)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{base_url}/api/messages",
                json=teams_message,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer fake-token"
                },
                timeout=30
            ) as response:
                
                print(f"📊 Response Status: {response.status}")
                
                if response.status == 200:
                    try:
                        result = await response.json()
                        print("✅ Construction Query Response:")
                        print(json.dumps(result, indent=2))
                    except:
                        text_response = await response.text()
                        print("✅ Construction Query Response:")
                        print(text_response)
                        
                else:
                    text_response = await response.text()
                    print(f"Response: {text_response}")
                    
        except Exception as e:
            print(f"💥 Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_teams_api_endpoint())
