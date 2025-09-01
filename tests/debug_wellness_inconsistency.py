#!/usr/bin/env python3
"""
Debug the wellness policy inconsistency issue.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.services.semantic_search import SemanticSearchService
from dtce_ai_bot.integrations.azure_search import get_search_client

# Load environment variables
load_dotenv()

async def debug_wellness_queries():
    """Debug the inconsistency between wellness queries."""
    
    # Initialize the semantic search service
    search_client = get_search_client()
    search_service = SemanticSearchService(search_client)
    
    queries = [
        "wellness policy",
        "what's our wellness policy and what does it say"
    ]
    
    print("🔍 DEBUGGING WELLNESS POLICY INCONSISTENCY")
    print("=" * 60)
    
    for i, query in enumerate(queries, 1):
        print(f"\n📋 Query {i}: '{query}'")
        print("-" * 50)
        
        try:
            # Test the intelligent search
            results = await search_service.search_documents_intelligent(query)
            
            print(f"🎯 Intelligent Search Results:")
            if results:
                print(f"   ✅ Found {len(results)} results")
                for j, result in enumerate(results[:5], 1):
                    filename = result.get('filename', 'Unknown')
                    content_preview = result.get('content', '')[:150]
                    print(f"      {j}. {filename}")
                    print(f"         Content: {content_preview}...")
            else:
                print("   ❌ No results found")
            
            # Also test the basic search
            basic_results = await search_service.search_documents(query)
            print(f"\n🔍 Basic Search Results:")
            if basic_results:
                print(f"   ✅ Found {len(basic_results)} results")
                for j, result in enumerate(basic_results[:5], 1):
                    filename = result.get('filename', 'Unknown')
                    print(f"      {j}. {filename}")
            else:
                print("   ❌ No results found")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("🔍 ROOT CAUSE ANALYSIS")
    print("=" * 60)
    print("If the results are different, the issue is likely:")
    print("1. Different search processing between queries")
    print("2. Intent classification affecting search terms")
    print("3. Inconsistent semantic understanding")

if __name__ == "__main__":
    asyncio.run(debug_wellness_queries())
