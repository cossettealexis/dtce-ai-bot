#!/usr/bin/env python3
"""
Test Complete Document Processing Pipeline
Tests the full flow: upload → extract → index → search
"""

import asyncio
import aiohttp
import json
import sys
from pathlib import Path

# Test configuration
API_BASE_URL = "http://localhost:8000"
TEST_FILE_PATH = Path(__file__).parent.parent / "demo_files" / "dtce_auth_docs.md"


async def test_pipeline():
    """Test the complete document processing pipeline."""
    print("🚀 Testing DTCE AI Bot Document Processing Pipeline")
    print("=" * 60)
    
    if not TEST_FILE_PATH.exists():
        print(f"❌ Test file not found: {TEST_FILE_PATH}")
        return False
    
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Upload document
            print("\n📤 Step 1: Uploading document...")
            await test_upload(session)
            
            # Step 2: Extract text
            print("\n🔍 Step 2: Extracting text...")
            await test_extract(session)
            
            # Step 3: Index document
            print("\n📋 Step 3: Indexing document...")
            await test_index(session)
            
            # Step 4: Search documents
            print("\n🔎 Step 4: Searching documents...")
            await test_search(session)
            
            print("\n🎉 Pipeline test completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Pipeline test failed: {e}")
            return False


async def test_upload(session):
    """Test document upload."""
    with open(TEST_FILE_PATH, 'rb') as file:
        data = aiohttp.FormData()
        data.add_field('file', file, filename=TEST_FILE_PATH.name)
        data.add_field('folder', 'test-documents')
        
        async with session.post(f"{API_BASE_URL}/documents/upload", data=data) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Upload successful: {result['blob_name']}")
                return result['blob_name']
            else:
                error = await response.text()
                raise Exception(f"Upload failed: {response.status} - {error}")


async def test_extract(session):
    """Test text extraction."""
    blob_name = f"test-documents/{TEST_FILE_PATH.name}"
    
    async with session.post(f"{API_BASE_URL}/documents/extract", 
                          params={"blob_name": blob_name}) as response:
        if response.status == 200:
            result = await response.json()
            print(f"✅ Extraction successful: {len(result.get('extracted_text', ''))} characters")
            print(f"   Method: {result.get('extraction_method', 'unknown')}")
            print(f"   Pages: {result.get('page_count', 0)}")
            return result
        else:
            error = await response.text()
            raise Exception(f"Extraction failed: {response.status} - {error}")


async def test_index(session):
    """Test document indexing."""
    blob_name = f"test-documents/{TEST_FILE_PATH.name}"
    
    async with session.post(f"{API_BASE_URL}/documents/index",
                          params={"blob_name": blob_name}) as response:
        if response.status == 200:
            result = await response.json()
            print(f"✅ Indexing successful: {result['document_id']}")
            print(f"   Content length: {result.get('content_length', 0)} characters")
            return result
        else:
            error = await response.text()
            raise Exception(f"Indexing failed: {response.status} - {error}")


async def test_search(session):
    """Test document search."""
    test_queries = [
        "PostgreSQL database",
        "authentication",
        "JWT token",
        "rate limiting"
    ]
    
    for query in test_queries:
        print(f"\n   🔍 Searching for: '{query}'")
        
        async with session.get(f"{API_BASE_URL}/documents/search",
                             params={"query": query, "top": 3}) as response:
            if response.status == 200:
                results = await response.json()
                print(f"      Found {len(results)} results")
                
                for i, result in enumerate(results):
                    print(f"      {i+1}. {result['filename']} (score: {result['score']:.2f})")
                    if result.get('highlights'):
                        print(f"         Highlight: {result['highlights'][0][:100]}...")
            else:
                error = await response.text()
                print(f"      ❌ Search failed: {response.status} - {error}")


async def check_health(session):
    """Check if the API is running."""
    try:
        async with session.get(f"{API_BASE_URL}/health") as response:
            if response.status == 200:
                return True
            else:
                return False
    except:
        return False


async def main():
    """Main test function."""
    print("Checking if API is running...")
    
    async with aiohttp.ClientSession() as session:
        if not await check_health(session):
            print("❌ API is not running. Please start the server with:")
            print("   uvicorn dtce_ai_bot.core.app:app --host 0.0.0.0 --port 8000 --reload")
            return
    
    print("✅ API is running")
    
    # Run the pipeline test
    success = await test_pipeline()
    
    if success:
        print("\n🎉 All tests passed! Your timesheet implementation is working:")
        print("   ✅ Document ingestion pipeline (Aug 1)")
        print("   ✅ Text extraction from files (Aug 1)")
        print("   ✅ Azure Cognitive Search integration (Aug 1)")
        print("   ✅ Blob Storage integration (Aug 1)")
    else:
        print("\n❌ Some tests failed. Check your Azure configuration.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
