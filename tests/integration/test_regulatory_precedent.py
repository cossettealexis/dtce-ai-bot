#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_regulatory_precedent_queries():
    """Test regulatory precedent queries."""
    
    # Initialize search client and QA service
    search_client = get_search_client()
    service = DocumentQAService(search_client)
    
    # Test regulatory precedent queries
    test_queries = [
        "Give me examples of projects where council questioned our wind load calculations.",
        "How have we approached alternative solution applications for non-standard stair designs?",
        "Show me precedent for using non-standard bracing in heritage building retrofits."
    ]
    
    print("🏛️ Testing Regulatory & Consent Precedent Queries")
    print("=" * 65)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🧪 Test {i}: {query}")
        print("-" * 55)
        
        try:
            # Test the query
            result = await service.answer_question(query)
            
            print(f"✅ Query Type: {result.get('search_type', 'general')}")
            print(f"📊 Confidence: {result.get('confidence', 'unknown')}")
            print(f"📚 Documents Found: {result.get('documents_searched', 0)}")
            
            if 'regulatory_components' in result:
                print(f"🎯 Regulatory Components: {result['regulatory_components']['summary']}")
            
            print(f"💬 Answer Preview: {result['answer'][:200]}...")
            
            if result.get('sources'):
                print(f"📄 Top Sources:")
                for j, source in enumerate(result['sources'][:3], 1):
                    print(f"   {j}. {source['filename']} (Project: {source['project_id']})")
                    if 'regulatory_score' in source:
                        print(f"      Regulatory Relevance: {source['regulatory_score']}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print()

if __name__ == "__main__":
    asyncio.run(test_regulatory_precedent_queries())
