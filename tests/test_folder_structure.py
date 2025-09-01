#!/usr/bin/env python3
"""
Diagnostic test to see what folder structures exist in the search index.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.integrations.azure_search import get_search_client

# Load environment variables
load_dotenv()

async def analyze_folder_structure():
    """Analyze the actual folder structure in the search index."""
    
    search_client = get_search_client()
    
    print("🔍 ANALYZING ACTUAL FOLDER STRUCTURE")
    print("=" * 50)
    
    # Search for a few documents to see their folder structure
    try:
        # Get a sample of documents
        results = search_client.search(
            search_text="*",
            top=50,
            select=["filename", "folder", "project_name"]
        )
        
        folders = set()
        filenames = []
        
        for result in results:
            folder = result.get('folder', 'No folder')
            filename = result.get('filename', 'No filename')
            
            folders.add(folder)
            filenames.append((filename, folder))
            
            if len(filenames) <= 10:  # Show first 10 examples
                print(f"📁 {folder}")
                print(f"   📄 {filename}")
                print()
        
        print(f"📊 SUMMARY:")
        print(f"   Total unique folders found: {len(folders)}")
        print(f"   Sample folders:")
        
        for i, folder in enumerate(sorted(folders)[:20], 1):
            print(f"   {i:2d}. {folder}")
        
        if len(folders) > 20:
            print(f"   ... and {len(folders) - 20} more folders")
            
    except Exception as e:
        print(f"❌ Error analyzing folders: {str(e)}")

async def test_simple_search():
    """Test simple search without folder filters."""
    
    search_client = get_search_client()
    
    print("\n🔍 TESTING SIMPLE SEARCH")
    print("=" * 50)
    
    queries = ["wellness", "policy", "health", "safety", "standard"]
    
    for query in queries:
        try:
            results = search_client.search(
                search_text=query,
                top=5,
                select=["filename", "folder"]
            )
            
            result_list = list(results)
            print(f"Query '{query}': {len(result_list)} results")
            
            for i, result in enumerate(result_list[:3], 1):
                filename = result.get('filename', 'Unknown')
                folder = result.get('folder', 'Unknown')
                print(f"  {i}. {filename}")
                print(f"     Folder: {folder}")
            
            if len(result_list) > 3:
                print(f"  ... and {len(result_list) - 3} more results")
            print()
            
        except Exception as e:
            print(f"Error searching '{query}': {str(e)}")

if __name__ == "__main__":
    asyncio.run(analyze_folder_structure())
    asyncio.run(test_simple_search())
