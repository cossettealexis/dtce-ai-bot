#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_regulatory_sources_detailed():
    """Test regulatory precedent with detailed source inspection."""
    
    search_client = get_search_client()
    service = DocumentQAService(search_client)
    
    query = "Give me examples of projects where council questioned our wind load calculations."
    
    print("🔍 Detailed Regulatory Precedent Test")
    print("=" * 50)
    print(f"Query: {query}")
    print("=" * 50)
    
    try:
        result = await service.answer_question(query)
        
        print(f"✅ Query Type: {result.get('search_type', 'general')}")
        print(f"📚 Documents Found: {result.get('documents_searched', 0)}")
        
        if result.get('sources'):
            print(f"\n📄 Detailed Source Analysis:")
            print("-" * 30)
            
            for i, source in enumerate(result['sources'][:3], 1):
                print(f"\n🔍 Source {i}:")
                print(f"   Raw source data: {source}")
                print(f"   Filename: '{source.get('filename', 'None')}'")
                print(f"   Project ID: '{source.get('project_id', 'None')}'")
                print(f"   Regulatory Score: {source.get('regulatory_score', 'None')}")
                print(f"   Blob URL: {source.get('blob_url', 'None')}")
                
                # Show a bit of the excerpt
                excerpt = source.get('excerpt', '')
                if excerpt and len(excerpt) > 10:
                    print(f"   Content Preview: {excerpt[:100]}...")
                else:
                    print(f"   Content Preview: Empty or too short")
                    
        else:
            print("❌ No sources returned")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_regulatory_sources_detailed())
