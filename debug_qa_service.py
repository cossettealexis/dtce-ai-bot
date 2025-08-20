#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def debug_qa_service():
    """Debug the DocumentQAService directly to see where it fails."""
    
    print("🔍 Testing DocumentQAService Directly")
    print("=" * 60)
    
    try:
        # Create the service exactly like the API does
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        print("✅ DocumentQAService created successfully")
        
        # Test with a simple question
        test_question = "What projects do we have?"
        print(f"\n🧠 Testing question: '{test_question}'")
        
        # Call the main method
        result = await qa_service.answer_question(test_question)
        
        print(f"Result: {json.dumps(result, indent=2)}")
        
        # Let's also test the search method directly
        print(f"\n🔍 Testing _search_relevant_documents directly...")
        documents = qa_service._search_relevant_documents(test_question)
        print(f"Documents found: {len(documents)}")
        
        if documents:
            print("Sample documents:")
            for i, doc in enumerate(documents[:2]):
                print(f"  {i+1}. {doc.get('filename', 'no filename')}")
                print(f"     Content: {doc.get('content', 'no content')[:100]}...")
        else:
            print("❌ No documents found by _search_relevant_documents!")
            
    except Exception as e:
        print(f"❌ DocumentQAService failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_qa_service())
