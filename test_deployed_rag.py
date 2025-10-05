#!/usr/bin/env python3
"""
Test the deployed Azure RAG system via direct API call
"""

import asyncio
import aiohttp
import json

async def test_deployed_system():
    """Test the actual deployed Teams bot API"""
    
    azure_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    
    # Test both a simple query and a technical query
    test_cases = [
        {
            "query": "test",
            "description": "Simple test query"
        },
        {
            "query": "What are the maximum spans for 90x45mm joists?", 
            "description": "Technical construction query"
        }
    ]
    
    print("🔍 TESTING DEPLOYED AZURE RAG SYSTEM")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        
        # First check if the service is up
        print("1. Checking service health...")
        try:
            async with session.get(f"{azure_url}/health/") as response:
                if response.status == 200:
                    health = await response.json()
                    print(f"   ✅ Service is up: {health.get('status')}")
                else:
                    print(f"   ❌ Health check failed: {response.status}")
                    return
        except Exception as e:
            print(f"   ❌ Cannot reach service: {e}")
            return
        
        # Test the actual bot endpoints
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. Testing: {test_case['description']}")
            print(f"   Query: '{test_case['query']}'")
            
            # Simulate a Teams bot message
            bot_message = {
                "type": "message",
                "text": test_case['query'],
                "from": {
                    "id": "test-user",
                    "name": "Test User"
                },
                "conversation": {
                    "id": "test-conversation"
                },
                "recipient": {
                    "id": "bot-id"
                },
                "serviceUrl": "https://smba.trafficmanager.net/apis/"
            }
            
            try:
                async with session.post(
                    f"{azure_url}/api/messages",
                    json=bot_message,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer mock-token"  # This will test the endpoint
                    },
                    timeout=30
                ) as response:
                    
                    print(f"   Status: {response.status}")
                    
                    if response.status == 200:
                        try:
                            result = await response.json()
                            print("   ✅ SUCCESS: Bot responded")
                            
                            # Check if it's using the new RAG system
                            if 'activities' in result:
                                for activity in result.get('activities', []):
                                    text = activity.get('text', '')
                                    if text:
                                        print(f"   📝 Response: {text[:200]}...")
                                        
                                        # Check for indicators of new RAG system
                                        if any(phrase in text.lower() for phrase in [
                                            "retrieved documents", "azure", "nzs 3604", 
                                            "timber framing", "construction"
                                        ]):
                                            print("   🎯 USING NEW RAG SYSTEM")
                                        else:
                                            print("   ⚠️  Response pattern unclear")
                            else:
                                print(f"   📄 Raw response: {json.dumps(result, indent=2)}")
                                
                        except json.JSONDecodeError:
                            text_response = await response.text()
                            print(f"   📄 Text response: {text_response[:200]}...")
                            
                    elif response.status == 401 or response.status == 403:
                        print("   ⚠️  Authentication required (expected for production)")
                        print("   ℹ️  This means the endpoint is working but needs proper Teams auth")
                        
                    else:
                        error_text = await response.text()
                        print(f"   ❌ Error {response.status}: {error_text[:200]}...")
                        
            except Exception as e:
                print(f"   ❌ Request failed: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 TEST COMPLETE")
    print("\nTo fully test the RAG system, try asking:")
    print("• 'test' in Microsoft Teams")
    print("• 'What are the maximum spans for 90x45mm joists?' in Teams")
    print("\nIf you get proper construction-related responses instead of")
    print("generic templates, the RAG system is working!")

if __name__ == "__main__":
    asyncio.run(test_deployed_system())
