#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dtce_ai_bot.integrations.azure_search import get_search_client

async def debug_search_results():
    """Debug what's actually in the search results."""
    
    search_client = get_search_client()
    
    print("🔍 Debugging Azure Search Results")
    print("=" * 50)
    
    # Test a simple search to see the data structure
    try:
        results = search_client.search(
            search_text="council",
            top=5,
            select=["id", "filename", "content", "blob_url", "project_name", "folder"]
        )
        
        print("📄 Sample Search Results:")
        print("-" * 30)
        
        for i, result in enumerate(results, 1):
            print(f"\n📋 Document {i}:")
            print(f"   ID: {result.get('id', 'None')}")
            print(f"   Filename: {result.get('filename', 'None')}")
            print(f"   Project Name: {result.get('project_name', 'None')}")
            print(f"   Folder: {result.get('folder', 'None')}")
            print(f"   Blob URL: {result.get('blob_url', 'None')}")
            
            # Show available fields
            print(f"   Available Fields: {list(result.keys())}")
            
            if result.get('content'):
                preview = result['content'][:100].replace('\n', ' ')
                print(f"   Content Preview: {preview}...")
                
        print(f"\n🔍 Field Analysis:")
        print("=" * 30)
        
        # Analyze all results to see field population
        all_results = list(search_client.search(search_text="council", top=20))
        
        total_docs = len(all_results)
        has_project_name = sum(1 for doc in all_results if doc.get('project_name'))
        has_folder = sum(1 for doc in all_results if doc.get('folder'))
        has_filename = sum(1 for doc in all_results if doc.get('filename'))
        
        print(f"Total Documents: {total_docs}")
        print(f"Documents with project_name: {has_project_name} ({has_project_name/total_docs*100:.1f}%)")
        print(f"Documents with folder: {has_folder} ({has_folder/total_docs*100:.1f}%)")
        print(f"Documents with filename: {has_filename} ({has_filename/total_docs*100:.1f}%)")
        
        # Check if project info might be in folder path
        print(f"\n📁 Sample Folder Paths:")
        for doc in all_results[:5]:
            if doc.get('folder'):
                print(f"   Folder: {doc['folder']}")
            if doc.get('filename'):
                print(f"   Filename: {doc['filename']}")
            print()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_search_results())
