#!/usr/bin/env python3

import asyncio
import aiohttp
import json

async def debug_api_call():
    """Debug a single API call to see the actual error."""
    
    api_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    
    async with aiohttp.ClientSession() as session:
        # Test a simple engineering question
        test_question = "What projects do we have?"
        
        print(f"🔍 Testing question: '{test_question}'")
        print("=" * 60)
        
        url = f"{api_url}/documents/ask"
        params = {"question": test_question}
        
        async with session.post(url, params=params) as response:
            print(f"Status: {response.status}")
            print(f"Headers: {dict(response.headers)}")
            
            if response.status == 200:
                data = await response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
            else:
                text = await response.text()
                print(f"Error response: {text}")

if __name__ == "__main__":
    asyncio.run(debug_api_call())
