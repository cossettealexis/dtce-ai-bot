#!/usr/bin/env python3
"""Final validation test for enhanced scenario and regulatory queries."""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import Settings

async def test_final_validation():
    """Test both scenario and regulatory queries with improved source naming."""
    
    print("🎯 Final Validation Test")
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
    
    # Test scenario query
    print("\n🧪 Testing Scenario Query:")
    print("-" * 40)
    scenario_query = "Show me timber buildings we've designed in high wind zones"
    
    try:
        result = await service.answer_question(scenario_query)
        print(f"✅ Query Type: {result.get('query_type', 'unknown')}")
        print(f"📊 Confidence: {result.get('confidence', 'unknown')}")
        print(f"📚 Documents Found: {result.get('documents_searched', 0)}")
        
        sources = result.get('sources', [])
        if sources:
            print("📄 Top Sources:")
            for i, source in enumerate(sources[:3], 1):
                filename = source.get('filename', 'Unknown')
                project = source.get('project_id', 'Unknown')
                print(f"   {i}. {filename} (Project: {project})")
        else:
            print("📄 No sources found")
            
    except Exception as e:
        print(f"❌ Scenario test failed: {e}")
    
    # Test regulatory query
    print("\n🧪 Testing Regulatory Query:")
    print("-" * 40)
    regulatory_query = "Show me projects where council questioned our calculations"
    
    try:
        result = await service.answer_question(regulatory_query)
        print(f"✅ Query Type: {result.get('query_type', 'unknown')}")
        print(f"📊 Confidence: {result.get('confidence', 'unknown')}")
        print(f"📚 Documents Found: {result.get('documents_searched', 0)}")
        
        sources = result.get('sources', [])
        if sources:
            print("📄 Top Sources:")
            for i, source in enumerate(sources[:3], 1):
                filename = source.get('filename', 'Unknown')
                project = source.get('project_id', 'Unknown')
                regulatory_score = source.get('regulatory_score', 'N/A')
                print(f"   {i}. {filename} (Project: {project}, Score: {regulatory_score})")
        else:
            print("📄 No sources found")
            
    except Exception as e:
        print(f"❌ Regulatory test failed: {e}")
    
    print("\n🎯 Validation Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_final_validation())
