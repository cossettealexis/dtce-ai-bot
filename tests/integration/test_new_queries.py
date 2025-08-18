#!/usr/bin/env python3
"""
Test script for the new sophisticated query types.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from dtce_ai_bot.services.query_classification import QueryClassificationService
from dtce_ai_bot.services.document_qa import DocumentQAService
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import Settings
from openai import AsyncOpenAI

async def test_new_query_types():
    """Test the three new sophisticated query types."""
    
    # Load environment variables
    load_dotenv()
    
    # Initialize services
    settings = Settings()
    
    # Build search endpoint URL
    search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    classification_service = QueryClassificationService(
        openai_client=openai_client,
        model_name=settings.openai_model_name
    )
    qa_service = DocumentQAService(search_client)
    
    # Test queries for each new type
    test_queries = [
        {
            'type': 'Best Practices & Templates',
            'query': "What's our standard approach to designing steel portal frames for industrial buildings?"
        },
        {
            'type': 'Materials & Methods',
            'query': "When have we chosen precast concrete over in-situ concrete for floor slabs, and why?"
        },
        {
            'type': 'Internal Knowledge',
            'query': "Which engineers have experience with tilt-slab construction?"
        }
    ]
    
    print("🔍 Testing New Sophisticated Query Types\n")
    print("=" * 80)
    
    for i, test_case in enumerate(test_queries, 1):
        print(f"\n📝 Test {i}: {test_case['type']}")
        print(f"Query: {test_case['query']}")
        print("-" * 40)
        
        try:
            # Test classification
            classification = await classification_service.classify_query_intent(test_case['query'])
            print(f"✅ Classification: {classification.get('intent', 'Unknown')}")
            print(f"   Confidence: {classification.get('confidence', 'Unknown')}")
            
            # Test QA processing
            result = await qa_service.answer_question(test_case['query'])
            
            print(f"📊 Documents Found: {result.get('documents_searched', 0)}")
            print(f"🎯 Confidence: {result.get('confidence', 'Unknown')}")
            print(f"🔍 Search Type: {result.get('search_type', 'Unknown')}")
            
            # Show sources with enhanced info
            sources = result.get('sources', [])
            if sources:
                print(f"📁 Top Sources:")
                for j, source in enumerate(sources[:3], 1):
                    filename = source.get('filename', 'Unknown')
                    project_id = source.get('project_id', 'Unknown')
                    score = source.get('relevance_score', 0)
                    folder = source.get('folder_path', '')
                    
                    print(f"   {j}. {filename}")
                    print(f"      Project: {project_id}")
                    if folder:
                        print(f"      Folder: {folder}")
                    print(f"      Score: {score:.2f}")
            
            # Show answer preview
            answer = result.get('answer', '')
            if answer:
                preview = answer[:200] + "..." if len(answer) > 200 else answer
                print(f"💡 Answer Preview: {preview}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print("\n" + "=" * 80)
    
    print("\n✅ Testing Complete!")

if __name__ == "__main__":
    asyncio.run(test_new_query_types())
