#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_scenario_queries():
    """Test scenario-based technical queries."""
    
    # Initialize search client and QA service
    search_client = get_search_client()
    service = DocumentQAService(search_client)
    
    # Test scenarios from user request
    test_queries = [
        "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed.",
        "What foundation systems have we used for houses on steep slopes in Wellington?",
        "Find projects where we designed concrete shear walls for seismic strengthening.",
        "What connection details have we used for balconies on coastal apartment buildings?"
    ]
    
    print("🔬 Testing Scenario-Based Technical Queries")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🧪 Test {i}: {query}")
        print("-" * 50)
        
        try:
            # Test the query
            result = await service.answer_question(query)
            
            print(f"✅ Query Type: {result.get('search_type', 'general')}")
            print(f"📊 Confidence: {result.get('confidence', 'unknown')}")
            print(f"📚 Documents Found: {result.get('documents_searched', 0)}")
            
            if 'scenario_components' in result:
                print(f"🎯 Scenario Components: {result['scenario_components']['summary']}")
            
            print(f"💬 Answer Preview: {result['answer'][:200]}...")
            
            if result.get('sources'):
                print(f"📄 Top Sources:")
                for j, source in enumerate(result['sources'][:3], 1):
                    print(f"   {j}. {source['filename']} (Project: {source['project_id']})")
                    if 'scenario_score' in source:
                        print(f"      Scenario Match: {source['scenario_score']}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print()

if __name__ == "__main__":
    asyncio.run(test_scenario_queries())
