#!/usr/bin/env python3
"""
Proper test of the deployed Azure RAG system by testing actual endpoints
"""

import asyncio
import aiohttp
import json

async def test_deployed_system_properly():
    """Test the actual deployed system with real validation"""
    
    azure_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    
    print("🔥 PROPER AZURE RAG SYSTEM TEST")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        
        # Test 1: Health check
        print("1. 🏥 Health Check...")
        try:
            async with session.get(f"{azure_url}/health/") as response:
                if response.status == 200:
                    health = await response.json()
                    print(f"   ✅ Service UP: {health.get('status')}")
                    print(f"   📍 Service: {health.get('service')}")
                else:
                    print(f"   ❌ Health check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ Cannot reach service: {e}")
            return False
        
        # Test 2: Bot config status
        print("\n2. 🤖 Bot Configuration Status...")
        try:
            async with session.get(f"{azure_url}/api/teams/config-status") as response:
                if response.status == 200:
                    config = await response.json()
                    print(f"   ✅ Bot Config Loaded")
                    print(f"   📱 App ID Configured: {config.get('microsoft_app_id_configured')}")
                    print(f"   🔑 Password Configured: {config.get('microsoft_app_password_configured')}")
                    print(f"   🚀 Bot Ready: {config.get('bot_ready')}")
                    if not config.get('bot_ready'):
                        print("   ⚠️  Bot not properly configured!")
                else:
                    print(f"   ❌ Config check failed: {response.status}")
        except Exception as e:
            print(f"   ❌ Config check error: {e}")
        
        # Test 3: Simple test endpoint (should work without auth)
        print("\n3. 🧪 Simple Test Endpoint...")
        try:
            simple_message = {
                "text": "test query",
                "user": "test-user"
            }
            
            async with session.post(
                f"{azure_url}/api/teams/simple-test",
                json=simple_message,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                print(f"   Status: {response.status}")
                if response.status == 200:
                    result = await response.json()
                    print("   ✅ Simple test endpoint works")
                    print(f"   📝 Response: {json.dumps(result, indent=2)}")
                elif response.status == 404:
                    print("   ⚠️  Simple test endpoint not found")
                else:
                    error_text = await response.text()
                    print(f"   ❌ Simple test failed: {error_text[:200]}")
                    
        except Exception as e:
            print(f"   ❌ Simple test error: {e}")
        
        # Test 4: Check if RAG components are loading
        print("\n4. 🔍 RAG Component Initialization Test...")
        
        # Try to access a document search endpoint or similar
        try:
            async with session.get(f"{azure_url}/api/documents/test-connection") as response:
                print(f"   Document service status: {response.status}")
                if response.status == 200:
                    result = await response.json()
                    print("   ✅ Document service accessible")
                    print(f"   📄 Response: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"   📄 Document service test: {e}")
        
        # Test 5: Try the actual messages endpoint with minimal data
        print("\n5. 💬 Messages Endpoint Basic Test...")
        try:
            # Create a minimal Teams-like message
            minimal_activity = {
                "type": "message",
                "text": "health check",
                "from": {
                    "id": "test-user-id",
                    "name": "Test User"
                },
                "conversation": {
                    "id": "test-conversation-id"
                },
                "recipient": {
                    "id": "bot-id"
                },
                "serviceUrl": "https://test.com/",
                "channelId": "test",
                "id": "test-message-id",
                "timestamp": "2024-10-03T00:00:00.000Z"
            }
            
            async with session.post(
                f"{azure_url}/api/teams/messages",
                json=minimal_activity,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Microsoft-BotFramework/3.1"
                },
                timeout=30
            ) as response:
                
                print(f"   Status: {response.status}")
                response_text = await response.text()
                
                if response.status == 200:
                    print("   ✅ Messages endpoint responding!")
                    try:
                        result = json.loads(response_text)
                        print(f"   📨 JSON Response: {json.dumps(result, indent=2)}")
                    except:
                        print(f"   📨 Text Response: {response_text[:300]}...")
                        
                elif response.status == 401 or response.status == 403:
                    print("   🔒 Authentication required (expected)")
                    print("   ℹ️  This means the endpoint is working but needs proper Teams auth")
                    
                elif response.status == 500:
                    print("   ❌ INTERNAL SERVER ERROR - This is the problem!")
                    print(f"   🐛 Error details: {response_text[:500]}")
                    
                else:
                    print(f"   ⚠️  Unexpected status: {response.status}")
                    print(f"   📄 Response: {response_text[:300]}")
                    
        except asyncio.TimeoutError:
            print("   ⏱️  Request timed out")
        except Exception as e:
            print(f"   ❌ Messages endpoint error: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 PROPER TEST COMPLETE")
    print("\nIf you see:")
    print("✅ Status 200: RAG system is working") 
    print("🔒 Status 401/403: Auth required but endpoint works")
    print("❌ Status 500: There's still a bug in the code")
    print("\nNow test in Teams to see the actual RAG responses!")

if __name__ == "__main__":
    asyncio.run(test_deployed_system_properly())
