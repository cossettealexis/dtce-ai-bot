#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_project_extraction():
    """Test the project extraction method."""
    
    search_client = get_search_client()
    service = DocumentQAService(search_client)
    
    print("🔧 Testing Project Extraction")
    print("=" * 40)
    
    # Get some sample documents
    try:
        results = search_client.search(
            search_text="council",
            top=3,
            select=["id", "filename", "content", "blob_url", "project_name", "folder"]
        )
        
        print("🧪 Testing project extraction on sample documents:")
        print("-" * 50)
        
        for i, doc in enumerate(results, 1):
            print(f"\n📋 Document {i}:")
            print(f"   ID: {doc.get('id', 'None')}")
            print(f"   Filename: {doc.get('filename', 'None')}")
            print(f"   Project Name Field: '{doc.get('project_name', 'None')}'")
            print(f"   Blob URL: {doc.get('blob_url', 'None')}")
            
            # Test our extraction method
            extracted_project = service._extract_project_from_document(doc)
            print(f"   🎯 EXTRACTED PROJECT: '{extracted_project}'")
            
            # Test individual extraction methods
            url_project = service._extract_project_from_url(doc.get('blob_url', ''))
            print(f"   URL extraction: '{url_project}'")
            
            # Test ID extraction manually
            doc_id = doc.get('id', '')
            if doc_id:
                import re
                match = re.search(r'Projects_(\d+)_(\d+)_', doc_id)
                if match:
                    print(f"   ID extraction (specific): '{match.group(2)}'")
                    print(f"   ID extraction (general): '{match.group(1)}'")
                else:
                    match = re.search(r'Projects_(\d+)_', doc_id)
                    if match:
                        print(f"   ID extraction (fallback): '{match.group(1)}'")
                    else:
                        print(f"   ID extraction: No match")
            
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_project_extraction())
