#!/usr/bin/env python3
"""
Test the new intelligent folder routing system.
Verifies that queries are properly classified and routed to appropriate folders.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.services.intelligent_query_router import IntelligentQueryRouter, SearchCategory
from dtce_ai_bot.integrations.azure_search import get_search_client
from dtce_ai_bot.config.settings import get_settings
from openai import AsyncAzureOpenAI

# Load environment variables
load_dotenv()

def get_openai_client(settings):
    """Create OpenAI client for testing."""
    return AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )

async def test_query_classification():
    """Test that queries are properly classified into folder categories."""
    
    # Initialize the components
    settings = get_settings()
    openai_client = get_openai_client(settings)
    
    router = IntelligentQueryRouter(openai_client, settings.azure_openai_deployment_name)
    
    # Define test queries for each category
    test_queries = [
        # Policy queries
        ("wellness policy", SearchCategory.POLICY),
        ("health and safety procedures", SearchCategory.POLICY), 
        ("employee handbook", SearchCategory.POLICY),
        ("hr policy", SearchCategory.POLICY),
        
        # Procedure queries
        ("how do I use the wind speed spreadsheet", SearchCategory.PROCEDURES),
        ("technical procedures", SearchCategory.PROCEDURES),
        ("h2h handbook", SearchCategory.PROCEDURES),
        ("workflow guidelines", SearchCategory.PROCEDURES),
        
        # Standards queries
        ("nz engineering standards", SearchCategory.STANDARDS),
        ("building codes", SearchCategory.STANDARDS),
        ("NZS specifications", SearchCategory.STANDARDS),
        ("design criteria", SearchCategory.STANDARDS),
        
        # Project queries
        ("find projects in wellington", SearchCategory.PROJECTS),
        ("construction project details", SearchCategory.PROJECTS),
        ("past residential projects", SearchCategory.PROJECTS),
        ("site information", SearchCategory.PROJECTS),
        
        # Client queries
        ("NZTA client details", SearchCategory.CLIENTS),
        ("council projects", SearchCategory.CLIENTS),
        ("client contact information", SearchCategory.CLIENTS),
        ("customer details", SearchCategory.CLIENTS)
    ]
    
    print("🎯 INTELLIGENT QUERY ROUTING TEST")
    print("=" * 60)
    print("Testing that queries are correctly classified into folder categories")
    print("=" * 60)
    
    correct_classifications = 0
    total_queries = len(test_queries)
    
    for query, expected_category in test_queries:
        try:
            classified_category, confidence = await router.classify_query(query)
            
            is_correct = classified_category == expected_category
            status = "✅" if is_correct else "❌"
            
            print(f"{status} Query: '{query}'")
            print(f"    Expected: {expected_category.value}")
            print(f"    Got: {classified_category.value} ({confidence:.2f} confidence)")
            
            if is_correct:
                correct_classifications += 1
            else:
                print(f"    ⚠️  MISCLASSIFICATION!")
            
            # Show folder filters that would be applied
            folder_filters = router.get_folder_filters(classified_category)
            print(f"    Folder filters: {len(folder_filters)} filters")
            
            print()
            
        except Exception as e:
            print(f"❌ Query: '{query}' - ERROR: {str(e)}")
            print()
    
    # Calculate accuracy
    accuracy = correct_classifications / total_queries
    
    print("=" * 60)
    print(f"📊 CLASSIFICATION ACCURACY: {correct_classifications}/{total_queries} ({accuracy:.0%})")
    
    if accuracy >= 0.8:
        print("🎉 EXCELLENT! Query routing is working well")
        print("✅ Queries are being routed to correct folders")
    elif accuracy >= 0.6:
        print("⚠️  DECENT: Query routing is mostly working but could be improved")
    else:
        print("❌ POOR: Query routing needs significant improvement")
    
    print("=" * 60)
    return accuracy

async def test_folder_search_integration():
    """Test the integrated folder search functionality."""
    
    from dtce_ai_bot.services.semantic_search import SemanticSearchService
    
    settings = get_settings()
    search_client = get_search_client()
    openai_client = get_openai_client(settings)
    
    # Initialize with intelligent routing
    search_service = SemanticSearchService(search_client, openai_client, settings.azure_openai_deployment_name)
    
    print("\n🔍 INTEGRATED FOLDER SEARCH TEST")
    print("=" * 50)
    
    test_searches = [
        ("wellness policy", "Should find policy documents"),
        ("how to use wind speed spreadsheet", "Should find procedure documents"),
        ("nz engineering standards", "Should find standards documents"),
        ("wellington construction projects", "Should find project documents"),
        ("NZTA client information", "Should find client documents")
    ]
    
    for query, description in test_searches:
        print(f"\n📋 Testing: '{query}'")
        print(f"    Expected: {description}")
        
        try:
            results = await search_service.search_documents(query)
            
            if results:
                print(f"    ✅ Found {len(results)} results")
                
                # Show top 3 results
                for i, result in enumerate(results[:3], 1):
                    filename = result.get('filename', 'Unknown')
                    folder = result.get('folder', 'Unknown')
                    print(f"      {i}. {filename}")
                    print(f"         Folder: {folder}")
            else:
                print(f"    ❌ No results found")
                
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
    
    print("\n" + "=" * 50)

async def test_search_instructions():
    """Test that appropriate search instructions are generated for each category."""
    
    settings = get_settings()
    openai_client = get_openai_client(settings)
    
    router = IntelligentQueryRouter(openai_client, settings.azure_openai_deployment_name)
    
    print("\n📝 SEARCH INSTRUCTIONS TEST")
    print("=" * 50)
    
    categories = [
        SearchCategory.POLICY,
        SearchCategory.PROCEDURES, 
        SearchCategory.STANDARDS,
        SearchCategory.PROJECTS,
        SearchCategory.CLIENTS
    ]
    
    for category in categories:
        instructions = router.get_search_instructions(category)
        print(f"\n📁 {category.value.upper()} Instructions:")
        print("-" * 30)
        # Show first few lines of instructions
        instruction_lines = instructions.strip().split('\n')[:4]
        for line in instruction_lines:
            print(f"  {line.strip()}")
        print(f"  ... (total: {len(instructions)} chars)")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    async def main():
        print("🚀 Starting Intelligent Folder Routing Test...")
        print("🎯 Testing AI-powered query classification and folder targeting")
        print()
        
        # Test query classification
        accuracy = await test_query_classification()
        
        # Test integrated search
        await test_folder_search_integration()
        
        # Test search instructions
        await test_search_instructions()
        
        print("\n🏁 FINAL ASSESSMENT")
        print("=" * 50)
        if accuracy >= 0.8:
            print("✅ INTELLIGENT FOLDER ROUTING IS WORKING!")
            print("✅ Queries are correctly classified and routed")
            print("✅ Search is now folder-aware and targeted")
            print("✅ No more 'dumb' searching across everything!")
        else:
            print("⚠️  FOLDER ROUTING NEEDS IMPROVEMENT")
            print("🔧 Classification accuracy is below 80%")
            print("🔧 Consider tuning the classification logic")
        print("=" * 50)
    
    asyncio.run(main())
