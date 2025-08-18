#!/usr/bin/env python3
"""Direct test for scope expansion component detection."""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dtce_ai_bot.services.document_qa import DocumentQAService
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import Settings

async def test_scope_detection():
    """Test scope expansion component detection."""
    
    print("🔍 Testing Scope Expansion Component Detection")
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
    
    # Test the component extraction directly
    test_query = "Find projects where the structural scope expanded significantly after concept design."
    
    print(f"🧪 Test Query: {test_query}")
    print("-" * 40)
    
    # Test component extraction
    components = service._extract_cost_time_components(test_query)
    
    print("🎯 Extracted Components:")
    for category, items in components.items():
        if items and category != 'summary':
            print(f"   {category}: {items}")
    print(f"📋 Summary: {components.get('summary', 'None')}")
    
    # Test search terms
    search_terms = service._build_cost_time_search_terms(test_query, components)
    print(f"\n🔍 Search Terms Preview: {search_terms[:200]}...")
    
    # Test direct handler call
    print(f"\n🚀 Testing Direct Handler Call:")
    print("-" * 40)
    
    result = await service._handle_cost_time_insights_query(test_query)
    
    print(f"✅ Handler Result:")
    print(f"   Confidence: {result.get('confidence', 'unknown')}")
    print(f"   Documents Found: {result.get('documents_searched', 0)}")
    print(f"   Search Type: {result.get('search_type', 'unknown')}")
    
    sources = result.get('sources', [])
    if sources:
        print("📄 Direct Handler Sources:")
        for i, source in enumerate(sources[:3], 1):
            filename = source.get('filename', 'Unknown')
            project = source.get('project_id', 'Unknown')
            score = source.get('cost_time_score', 'N/A')
            print(f"   {i}. {filename} (Project: {project}, Score: {score})")
    else:
        print("📄 No sources from direct handler")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_scope_detection())
