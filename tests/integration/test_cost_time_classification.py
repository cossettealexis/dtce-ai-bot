#!/usr/bin/env python3
"""Test AI classification for Cost & Time Insights queries."""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.query_classification import QueryClassificationService
from openai import AsyncOpenAI
from dtce_ai_bot.config.settings import Settings

async def test_cost_time_classification():
    """Test AI classification for cost/time queries."""
    
    print("🔍 Testing AI Classification for Cost & Time Insights")
    print("=" * 60)
    
    # Initialize services
    settings = Settings()
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    classification_service = QueryClassificationService(
        openai_client=openai_client,
        model_name=settings.openai_model_name
    )
    
    # Test cost/time queries
    test_queries = [
        "How long does it typically take from concept to PS1 for small commercial alterations?",
        "What's the typical cost range for structural design of multi-unit residential projects?", 
        "Find projects where the structural scope expanded significantly after concept design.",
        "What are typical timelines for heritage building retrofits?",
        "Show me fee estimates for similar warehouse projects."
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🧪 Test {i}: {query}")
        print("-" * 50)
        
        try:
            classification = await classification_service.classify_query_intent(query)
            print(f"🎯 Primary Intent: {classification.get('primary_intent', 'Unknown')}")
            print(f"📊 Confidence: {classification.get('confidence', 'Unknown')}")
            print(f"💭 Reasoning: {classification.get('reasoning', 'No reasoning provided')}")
            print(f"🚏 Suggested Routing: {classification.get('suggested_routing', 'Unknown')}")
            
            # Check if correctly identified as COST_TIME_INSIGHTS
            expected_intent = "COST_TIME_INSIGHTS"
            actual_intent = classification.get('primary_intent')
            
            if actual_intent == expected_intent:
                print(f"✅ Correctly identified as {expected_intent}")
            else:
                print(f"❌ Expected {expected_intent}, got {actual_intent}")
                
        except Exception as e:
            print(f"❌ Classification failed: {e}")
    
    print("\n🔍 Classification Testing Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_cost_time_classification())
