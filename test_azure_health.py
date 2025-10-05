#!/usr/bin/env python3
"""
Test Azure health and basic endpoints
"""

import aiohttp
import asyncio

async def test_azure_health():
    """Test if Azure app is running and healthy"""
    
    base_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    
    endpoints_to_test = [
        "/health",
        "/",
        "/api/health"
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints_to_test:
            print(f"\n🔍 Testing: {base_url}{endpoint}")
            try:
                async with session.get(f"{base_url}{endpoint}", timeout=10) as response:
                    print(f"Status: {response.status}")
                    text = await response.text()
                    if text:
                        print(f"Response: {text[:500]}...")
                    else:
                        print("Response: (empty)")
                        
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_azure_health())
