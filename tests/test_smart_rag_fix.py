#!/usr/bin/env python3
"""
Test to prove the Smart RAG system fixes the "fucking dumb" problem.
Tests that equivalent queries now return consistent, useful answers.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.services.smart_rag_handler import SmartRAGHandler
from dtce_ai_bot.integrations.azure_search import get_search_client
from dtce_ai_bot.config.settings import get_settings
from openai import AsyncAzureOpenAI

# Load environment variables
load_dotenv()

async def test_smart_rag_consistency():
    """Test that the smart RAG system gives consistent answers."""
    
    # Initialize the smart RAG handler
    settings = get_settings()
    search_client = get_search_client()
    
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    smart_rag = SmartRAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
    
    # Test the EXACT queries that were "fucking dumb" before
    test_queries = [
        "wellness policy",
        "what's our welness policy and what does it say",  # Note: includes typo
        "show me the wellness policy",
        "health and safety policy",
        "what's our health and safety policy"
    ]
    
    print("🧠 SMART RAG CONSISTENCY TEST")
    print("=" * 60)
    print("Testing the exact queries that were inconsistent before...")
    print("=" * 60)
    
    results = []
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📋 Query {i}: '{query}'")
        print("-" * 40)
        
        try:
            result = await smart_rag.get_answer(query)
            
            answer = result.get("answer", "No answer")
            sources = result.get("sources", [])
            intent = result.get("intent", "unknown")
            
            print(f"🎯 Intent: {intent}")
            print(f"📚 Sources found: {len(sources)}")
            
            if sources:
                print(f"🔍 Top sources:")
                for j, source in enumerate(sources[:3], 1):
                    filename = source.get('filename', 'Unknown')
                    print(f"   {j}. {filename}")
            
            # Show first part of answer
            answer_preview = answer[:200] + "..." if len(answer) > 200 else answer
            print(f"💬 Answer preview: {answer_preview}")
            
            results.append({
                "query": query,
                "intent": intent,
                "sources": [s.get('filename', 'Unknown') for s in sources[:3]],
                "answer_length": len(answer),
                "has_sources": len(sources) > 0
            })
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            results.append({
                "query": query,
                "intent": "error",
                "sources": [],
                "answer_length": 0,
                "has_sources": False
            })
    
    # Analysis
    print("\n" + "=" * 60)
    print("📊 CONSISTENCY ANALYSIS")
    print("=" * 60)
    
    # Check if all wellness/health queries were classified consistently
    wellness_queries = [r for r in results if any(word in r["query"].lower() for word in ["wellness", "welness", "health"])]
    
    intents = [r["intent"] for r in wellness_queries]
    sources_found = [r["has_sources"] for r in wellness_queries]
    
    print(f"🎯 Intent consistency: {len(set(intents))} different intents detected")
    print(f"   Intents: {set(intents)}")
    
    print(f"📚 Source consistency: {sum(sources_found)}/{len(sources_found)} queries found sources")
    
    # Check for common sources
    all_sources = []
    for r in wellness_queries:
        all_sources.extend(r["sources"])
    
    from collections import Counter
    source_counts = Counter(all_sources)
    common_sources = [source for source, count in source_counts.items() if count >= 2]
    
    print(f"🔗 Common sources across queries: {len(common_sources)}")
    for source in common_sources:
        count = source_counts[source]
        print(f"   📄 {source} (appears in {count} queries)")
    
    # Final assessment
    print("\n" + "=" * 60)
    
    consistency_score = 0
    if len(set(intents)) == 1:  # All same intent
        consistency_score += 40
    
    if sum(sources_found) >= len(sources_found) * 0.8:  # 80% found sources
        consistency_score += 30
        
    if len(common_sources) > 0:  # Has common sources
        consistency_score += 30
    
    if consistency_score >= 80:
        print("🎉 SMART RAG IS WORKING!")
        print("✅ Consistent intent detection")
        print("✅ Reliable source finding")
        print("✅ Common documents across equivalent queries")
        print("✅ NO MORE 'FUCKING DUMB' RESPONSES!")
    elif consistency_score >= 60:
        print("🟡 SMART RAG IS MOSTLY WORKING")
        print("⚠️  Some consistency issues remain")
    else:
        print("❌ SMART RAG STILL HAS PROBLEMS")
        print("🔧 Need to debug the routing or search")
    
    print(f"\n📊 Consistency Score: {consistency_score}/100")
    print("=" * 60)

async def test_specific_wellness_query():
    """Test the exact queries that were problematic."""
    
    settings = get_settings()
    search_client = get_search_client()
    
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    smart_rag = SmartRAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
    
    print("\n🔍 DETAILED WELLNESS POLICY TEST")
    print("=" * 50)
    
    query = "what's our welness policy and what does it say"
    print(f"Query: '{query}'")
    print("-" * 50)
    
    try:
        result = await smart_rag.get_answer(query)
        
        print(f"🎯 Intent: {result.get('intent')}")
        print(f"📚 Sources: {len(result.get('sources', []))}")
        print(f"\n💬 Full Answer:")
        print(result.get("answer", "No answer"))
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    async def main():
        print("🚀 Testing Smart RAG Handler...")
        print("🎯 Goal: Fix the 'fucking dumb' inconsistency problem")
        print()
        
        # Test consistency across equivalent queries
        await test_smart_rag_consistency()
        
        # Test the specific problematic query
        await test_specific_wellness_query()
        
        print("\n🏁 SMART RAG TEST COMPLETE")
    
    asyncio.run(main())
