#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

from dtce_ai_bot.integrations.azure_search import get_search_client
from dtce_ai_bot.config.settings import get_settings

async def debug_azure_search():
    """Debug Azure Search directly to see what's happening."""
    
    print("🔍 Testing Azure Search Direct Connection")
    print("=" * 60)
    
    try:
        # Get settings and search client
        settings = get_settings()
        print(f"Search service: {settings.azure_search_service_name}")
        print(f"Index name: {settings.azure_search_index_name}")
        
        search_client = get_search_client()
        print("✅ Search client created successfully")
        
        # Test 1: Simple search for any documents
        print("\n🔍 Test 1: Simple search for ANY documents...")
        try:
            results = search_client.search(
                search_text="*",  # Search for everything
                top=5,
                select=["id", "filename", "content"]
            )
            
            docs = list(results)
            print(f"Found {len(docs)} documents with wildcard search")
            
            if docs:
                for i, doc in enumerate(docs[:3]):
                    print(f"  {i+1}. ID: {doc.get('id', 'no id')}")
                    print(f"     File: {doc.get('filename', 'no filename')}")
                    print(f"     Content preview: {doc.get('content', 'no content')[:100]}...")
                    print()
            else:
                print("❌ No documents found with wildcard search!")
                
        except Exception as e:
            print(f"❌ Wildcard search failed: {e}")
        
        # Test 2: Search for a common term
        print("\n🔍 Test 2: Search for 'project'...")
        try:
            results = search_client.search(
                search_text="project",
                top=5,
                select=["id", "filename", "content"]
            )
            
            docs = list(results)
            print(f"Found {len(docs)} documents with 'project' search")
            
            if docs:
                for i, doc in enumerate(docs[:2]):
                    print(f"  {i+1}. File: {doc.get('filename', 'no filename')}")
                    print(f"     Content preview: {doc.get('content', 'no content')[:100]}...")
                    print()
            else:
                print("❌ No documents found searching for 'project'!")
                
        except Exception as e:
            print(f"❌ Project search failed: {e}")
            
        # Test 3: Test semantic search (this might be the issue)
        print("\n🔍 Test 3: Test semantic search...")
        try:
            results = search_client.search(
                search_text="engineering standards",
                top=5,
                query_type="semantic",
                semantic_configuration_name="default",
                select=["id", "filename", "content"]
            )
            
            docs = list(results)
            print(f"Found {len(docs)} documents with semantic search")
            
        except Exception as e:
            print(f"❌ Semantic search failed: {e}")
            print("This might be why the system is failing!")
            
    except Exception as e:
        print(f"❌ Azure Search connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_azure_search())
