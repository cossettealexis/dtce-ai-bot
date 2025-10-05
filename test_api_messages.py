#!/usr/bin/env python3
"""
Test the actual /api/messages endpoint that Teams uses
"""

import aiohttp
import asyncio
import json

async def test_api_messages():
    """Test the /api/messages endpoint exactly like Teams would"""
    
    azure_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    
    # Simulate a proper Teams message payload
    teams_message = {
        "type": "message",
        "id": "test-message-123",
        "timestamp": "2025-10-03T12:00:00.000Z",
        "serviceUrl": "https://smba.trafficmanager.net/teams/",
        "channelId": "msteams",
        "from": {
            "id": "test-user-id",
            "name": "Test User"
        },
        "conversation": {
            "id": "test-conversation-123"
        },
        "text": "test",
        "textFormat": "plain",
        "locale": "en-US"
    }
    
    print(f"🔍 Testing /api/messages endpoint with: '{teams_message['text']}'")
    print("-" * 60)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{azure_url}/api/messages",
                json=teams_message,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer test-token"  # Teams would send actual token
                },
                timeout=30
            ) as response:
                
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    try:
                        result = await response.json()
                        print(f"JSON Response: {json.dumps(result, indent=2)}")
                    except:
                        text = await response.text()
                        print(f"Text Response: {text}")
                else:
                    error_text = await response.text()
                    print(f"Error Response: {error_text}")
                    
    except Exception as e:
        print(f"Request failed: {e}")

    # Also test with a technical question
    print("\n" + "="*60)
    technical_message = teams_message.copy()
    technical_message["text"] = "What are the maximum spans for 90x45mm joists?"
    
    print(f"🔍 Testing technical question: '{technical_message['text']}'")
    print("-" * 60)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{azure_url}/api/messages",
                json=technical_message,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer test-token"
                },
                timeout=30
            ) as response:
                
                print(f"Status: {response.status}")
                
                if response.status == 200:
                    try:
                        result = await response.json()
                        print(f"JSON Response: {json.dumps(result, indent=2)}")
                    except:
                        text = await response.text()
                        print(f"Text Response: {text}")
                else:
                    error_text = await response.text()
                    print(f"Error Response: {error_text}")
                    
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_api_messages())
