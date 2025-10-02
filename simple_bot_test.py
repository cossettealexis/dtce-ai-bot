#!/usr/bin/env python3
"""
Simple test script to test basic bot functionality
"""

import asyncio
import httpx
import time
import json

async def simple_bot_test():
    """Test basic bot functionality"""
    
    # Test different endpoints
    base_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # 1. Test root endpoint
        print("Testing root endpoint...")
        try:
            response = await client.get(base_url)
            print(f"✅ Root endpoint: {response.status_code}")
            if response.status_code == 200:
                print(f"Response: {response.json()}")
        except Exception as e:
            print(f"❌ Root endpoint failed: {e}")
        
        # 2. Test health endpoint
        print("\nTesting health endpoint...")
        try:
            response = await client.get(f"{base_url}/health")
            print(f"✅ Health endpoint: {response.status_code}")
            if response.status_code == 200:
                print(f"Health: {response.json()}")
        except Exception as e:
            print(f"❌ Health endpoint failed: {e}")
        
        # 3. Test a very simple message
        print("\nTesting simple message...")
        try:
            simple_payload = {
                "type": "message",
                "text": "hello",
                "from": {"id": "test", "name": "Test"},
                "recipient": {"id": "bot"},
                "conversation": {"id": "test"}
            }
            
            response = await client.post(
                f"{base_url}/api/messages",
                json=simple_payload,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"Message response: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Bot responded successfully")
                if 'activities' in result and result['activities']:
                    activity = result['activities'][0]
                    if 'text' in activity:
                        print(f"Bot said: {activity['text'][:100]}...")
            else:
                print(f"❌ Bot returned error {response.status_code}")
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"❌ Message test failed: {e}")

if __name__ == "__main__":
    asyncio.run(simple_bot_test())
