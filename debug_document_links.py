#!/usr/bin/env python3
"""
Debug script to check what the actual retrieved content looks like for wellness policy queries.
This will help us see if the documents actually contain the Link: field.
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.semantic_search import SemanticSearchService
from dtce_ai_bot.config.settings import Settings

async def debug_wellness_policy_retrieval():
    """Debug what documents are retrieved for wellness policy query"""
    print("🔍 Debugging wellness policy document retrieval...")
    
    # Initialize the semantic search service
    settings = Settings()
    search_service = SemanticSearchService(settings)
    
    # Test query
    test_query = "what's our wellness policy"
    
    try:
        print(f"📝 Testing query: '{test_query}'")
        
        # Get raw search results
        results = await search_service.enhanced_search(test_query)
        
        print(f"\n📊 Found {len(results)} documents")
        
        for i, doc in enumerate(results[:3]):  # Show first 3 documents
            print(f"\n📄 Document {i+1}:")
            print(f"  Filename: {doc.get('filename', 'N/A')}")
            print(f"  Score: {doc.get('@search.score', 'N/A')}")
            
            # Check for various URL fields
            url_fields = ['blob_url', 'blobUrl', 'url', 'source_url', 'Link']
            for field in url_fields:
                if field in doc:
                    print(f"  {field}: {doc[field]}")
            
            # Show first 200 chars of content
            content = doc.get('content', '')
            print(f"  Content preview: {content[:200]}...")
            
            print(f"  All fields: {list(doc.keys())}")
            
    except Exception as e:
        print(f"❌ ERROR during debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_wellness_policy_retrieval())
