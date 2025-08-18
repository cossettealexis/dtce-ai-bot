#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dtce_ai_bot.integrations.azure_search import get_search_client

async def debug_regulatory_documents():
    """Debug what fields are available in the documents returned by regulatory search."""
    
    search_client = get_search_client()
    
    print("🔍 Debugging Regulatory Document Fields")
    print("=" * 50)
    
    # Test the same search that would be used in regulatory queries
    search_terms = '"council" OR "questioned" OR "wind load" OR "calculations" OR "engineering report" OR "correspondence"'
    
    try:
        results = search_client.search(
            search_text=search_terms,
            top=5,
            highlight_fields="filename,project_name,content",
            select=["id", "filename", "content", "blob_url", "project_name", "folder"]
        )
        
        print(f"🧪 Search Terms: {search_terms}")
        print("-" * 50)
        
        for i, doc in enumerate(results, 1):
            print(f"\n📋 Document {i}:")
            print(f"   All available fields: {list(doc.keys())}")
            print(f"   ID: {doc.get('id', 'None')}")
            print(f"   Filename: {doc.get('filename', 'None')}")
            print(f"   Project Name: '{doc.get('project_name', 'None')}'")
            print(f"   Folder: {doc.get('folder', 'None')}")
            print(f"   Blob URL: {doc.get('blob_url', 'None')}")
            
            # Check if content contains project references
            content = doc.get('content', '')
            if content:
                print(f"   Content Length: {len(content)} chars")
                # Look for project numbers in content
                import re
                project_patterns = re.findall(r'\b\d{5,6}\b', content[:500])  # Look for 5-6 digit numbers
                if project_patterns:
                    print(f"   Potential project numbers in content: {project_patterns[:5]}")
                
                # Look for specific project identifiers
                if 'project' in content.lower():
                    project_mentions = re.findall(r'project[:\s]+([A-Z0-9]+)', content, re.IGNORECASE)
                    if project_mentions:
                        print(f"   Project mentions: {project_mentions[:3]}")
                        
                print(f"   Content Preview: {content[:150].replace(chr(10), ' ').replace(chr(13), ' ')}...")
            
        print(f"\n🔍 Analysis:")
        all_docs = list(search_client.search(search_text=search_terms, top=20))
        
        has_id = sum(1 for doc in all_docs if doc.get('id'))
        has_filename = sum(1 for doc in all_docs if doc.get('filename'))
        has_blob_url = sum(1 for doc in all_docs if doc.get('blob_url'))
        has_content = sum(1 for doc in all_docs if doc.get('content'))
        
        print(f"   Total docs: {len(all_docs)}")
        print(f"   Has ID: {has_id} ({has_id/len(all_docs)*100:.1f}%)")
        print(f"   Has filename: {has_filename} ({has_filename/len(all_docs)*100:.1f}%)")
        print(f"   Has blob_url: {has_blob_url} ({has_blob_url/len(all_docs)*100:.1f}%)")
        print(f"   Has content: {has_content} ({has_content/len(all_docs)*100:.1f}%)")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_regulatory_documents())
