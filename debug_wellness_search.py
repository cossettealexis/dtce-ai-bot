#!/usr/bin/env python3
"""
Debug what's actually being retrieved for wellness policy
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import get_settings

async def debug_wellness_search():
    """Debug what documents are found for wellness policy"""
    
    print("🔍 DEBUGGING WELLNESS POLICY SEARCH")
    print("=" * 60)
    
    try:
        settings = get_settings()
        
        # Create search client
        search_client = SearchClient(
            endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_admin_key)
        )
        
        # Test different search queries
        test_queries = [
            "wellness policy",
            "wellbeing policy", 
            "wellness",
            "wellbeing",
            "policy wellness"
        ]
        
        for query in test_queries:
            print(f"\n🔍 Searching for: '{query}'")
            print("-" * 40)
            
            try:
                # Direct search
                results = search_client.search(
                    search_text=query,
                    top=10,
                    include_total_count=True
                )
                
                total_count = results.get_count()
                print(f"📊 Total documents found: {total_count}")
                
                count = 0
                for doc in results:
                    count += 1
                    filename = doc.get('filename', 'Unknown')
                    content_snippet = doc.get('content', '')[:200] + "..."
                    score = doc.get('@search.score', 0)
                    
                    print(f"\n📄 Document {count}:")
                    print(f"   File: {filename}")
                    print(f"   Score: {score:.3f}")
                    print(f"   Content: {content_snippet}")
                    
                    if count >= 5:  # Show top 5 only
                        break
                        
                if count == 0:
                    print("❌ No documents found!")
                    
            except Exception as e:
                print(f"❌ Search failed: {e}")
        
        print(f"\n🎯 DEBUG COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_wellness_search())
