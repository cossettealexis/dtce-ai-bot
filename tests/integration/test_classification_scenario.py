#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.services.query_classification import QueryClassificationService
from dtce_ai_bot.config.settings import get_settings
from openai import AsyncAzureOpenAI

async def test_scenario_classification():
    """Test AI classification for scenario-based queries."""
    
    # Get settings
    settings = get_settings()
    
    # Initialize OpenAI client
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version
    )
    
    classification_service = QueryClassificationService(openai_client, settings.azure_openai_deployment_name)
    
    # Test scenarios from user request
    test_queries = [
        "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed.",
        "What foundation systems have we used for houses on steep slopes in Wellington?",
        "Find projects where we designed concrete shear walls for seismic strengthening.",
        "What connection details have we used for balconies on coastal apartment buildings?"
    ]
    
    print("🔍 Testing AI Classification for Scenario Queries")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🧪 Test {i}: {query}")
        print("-" * 50)
        
        try:
            # Test the classification
            classification = await classification_service.classify_query_intent(query)
            
            print(f"🎯 Primary Intent: {classification.get('primary_intent', 'unknown')}")
            print(f"📊 Confidence: {classification.get('confidence', 'unknown')}")
            print(f"💭 Reasoning: {classification.get('reasoning', 'no reasoning')}")
            print(f"🔑 Keywords: {classification.get('keywords', [])}")
            print(f"🚏 Suggested Routing: {classification.get('suggested_routing', 'unknown')}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print()

if __name__ == "__main__":
    asyncio.run(test_scenario_classification())
