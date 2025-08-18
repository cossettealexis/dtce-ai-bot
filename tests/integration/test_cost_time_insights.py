#!/usr/bin/env python3
"""Test script for Cost & Time Insights query functionality."""

import asyncio
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dtce_ai_bot.services.document_qa import DocumentQAService
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import Settings

async def test_cost_time_insights():
    """Test the new Cost & Time Insights query functionality."""
    
    print("💰 Testing Cost & Time Insights Queries")
    print("=" * 60)
    
    # Initialize services
    settings = Settings()
    
    # Build search endpoint URL
    search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    service = DocumentQAService(search_client=search_client)
    
    # Test queries
    test_queries = [
        "How long does it typically take from concept to PS1 for small commercial alterations?",
        "What's the typical cost range for structural design of multi-unit residential projects?",
        "Find projects where the structural scope expanded significantly after concept design."
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🧪 Test {i}: {query}")
        print("-" * 50)
        
        try:
            result = await service.answer_question(query)
            print(f"✅ Query Type: {result.get('query_type', 'unknown')}")
            print(f"📊 Confidence: {result.get('confidence', 'unknown')}")
            print(f"📚 Documents Found: {result.get('documents_searched', 0)}")
            
            # Show cost/time components if available
            components = result.get('cost_time_components', {})
            if components and components.get('summary'):
                print(f"🎯 Cost/Time Components: {components['summary']}")
            
            # Show answer preview
            answer = result.get('answer', '')
            if answer:
                preview = answer[:200] + '...' if len(answer) > 200 else answer
                print(f"💬 Answer Preview: {preview}")
            
            # Show top sources
            sources = result.get('sources', [])
            if sources:
                print("📄 Top Sources:")
                for j, source in enumerate(sources[:3], 1):
                    filename = source.get('filename', 'Unknown')
                    project = source.get('project_id', 'Unknown')
                    cost_time_score = source.get('cost_time_score', 'N/A')
                    print(f"   {j}. {filename} (Project: {project}, Score: {cost_time_score})")
            else:
                print("📄 No sources found")
                
        except Exception as e:
            print(f"❌ Test {i} failed: {e}")
    
    print("\n💰 Cost & Time Insights Testing Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_cost_time_insights())
