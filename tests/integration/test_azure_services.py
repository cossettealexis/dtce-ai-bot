#!/usr/bin/env python3
"""
Test script to verify Azure services connectivity.
Run this after setting up your Azure services and updating .env file.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.azure_blob_client import AzureBlobClient
from src.azure_search_client import AzureSearchClient
from src.azure_openai_client import AzureOpenAIClient
from src.models import DocumentMetadata, SearchQuery, DocumentType


async def test_blob_storage():
    """Test Azure Blob Storage connectivity."""
    
    print("☁️ Testing Azure Blob Storage...")
    
    try:
        client = AzureBlobClient()
        
        # Test container creation
        success = await client.ensure_container_exists()
        if success:
            print("✅ Blob Storage container is ready")
            
            # Test listing (should be empty initially)
            blobs = await client.list_documents()
            print(f"📄 Found {len(blobs)} existing documents in storage")
            
            return True
        else:
            print("❌ Failed to create/access blob storage container")
            return False
            
    except Exception as e:
        print(f"❌ Blob Storage test failed: {e}")
        return False


async def test_cognitive_search():
    """Test Azure Cognitive Search connectivity."""
    
    print("\n🔍 Testing Azure Cognitive Search...")
    
    try:
        client = AzureSearchClient()
        
        # Test index creation
        success = await client.create_or_update_index()
        if success:
            print("✅ Search index is ready")
            
            # Test getting statistics
            stats = await client.get_index_statistics()
            doc_count = stats.get('document_count', 0)
            print(f"📊 Search index contains {doc_count} documents")
            
            # Test a simple search (should return empty results initially)
            query = SearchQuery(query="test", max_results=5)
            response = await client.search_documents(query)
            print(f"🔍 Test search returned {len(response.results)} results")
            
            return True
        else:
            print("❌ Failed to create/access search index")
            return False
            
    except Exception as e:
        print(f"❌ Cognitive Search test failed: {e}")
        return False


async def test_openai():
    """Test Azure OpenAI connectivity."""
    
    print("\n🤖 Testing Azure OpenAI...")
    
    try:
        client = AzureOpenAIClient()
        
        # Test a simple completion
        response = await client.client.chat.completions.create(
            model=client.deployment_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello DTCE!' to test the connection."}
            ],
            max_tokens=50
        )
        
        message = response.choices[0].message.content
        print(f"✅ OpenAI response: {message}")
        
        # Test search summary generation (with empty results)
        from src.models import SearchResponse
        empty_response = SearchResponse(
            query="test query",
            total_results=0,
            results=[],
            processing_time=0.1
        )
        
        summary = await client.generate_search_summary(empty_response)
        print(f"📝 Summary generation test: {summary[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")
        return False


async def test_full_pipeline():
    """Test the full document processing pipeline with a sample document."""
    
    print("\n⚙️ Testing Full Pipeline...")
    
    try:
        # Create a sample document metadata
        sample_doc = DocumentMetadata(
            file_id="test_001",
            file_name="test_document.txt",
            file_path="Tests/test_document.txt",
            file_size=1024,
            file_type=".txt",
            modified_date="2024-01-01T12:00:00Z",
            sharepoint_url="https://test.sharepoint.com/test_document.txt",
            project_id="999",
            document_type=DocumentType.REPORTS_SPECS,
            folder_path="Tests",
            content_preview="This is a test document for DTCE AI Assistant",
            extracted_text="This is a test document for DTCE AI Assistant. It contains sample engineering content about structural analysis and seismic design.",
            client_name="Test Client",
            project_title="Test Project",
            keywords=["test", "structural", "seismic"]
        )
        
        # Test blob upload
        blob_client = AzureBlobClient()
        blob_url = await blob_client.upload_document_metadata(sample_doc)
        
        if blob_url:
            print("✅ Sample document uploaded to Blob Storage")
            sample_doc.blob_url = blob_url
        else:
            print("❌ Failed to upload to Blob Storage")
            return False
        
        # Test search indexing
        search_client = AzureSearchClient()
        index_success = await search_client.index_document(sample_doc)
        
        if index_success:
            print("✅ Sample document indexed in Cognitive Search")
        else:
            print("❌ Failed to index document")
            return False
        
        # Wait a moment for indexing to complete
        await asyncio.sleep(2)
        
        # Test searching for the document
        query = SearchQuery(query="test structural", max_results=5)
        search_response = await search_client.search_documents(query)
        
        if search_response.results:
            print(f"✅ Found {len(search_response.results)} results for test query")
            
            # Test AI summary generation
            openai_client = AzureOpenAIClient()
            summary = await openai_client.generate_search_summary(search_response)
            print(f"✅ AI summary generated: {summary[:100]}...")
            
        else:
            print("⚠️ No results found for test query (indexing may still be in progress)")
        
        return True
        
    except Exception as e:
        print(f"❌ Full pipeline test failed: {e}")
        return False


async def main():
    """Main test function."""
    
    # Load environment variables
    load_dotenv()
    
    print("🚀 DTCE AI Assistant - Azure Services Test")
    print("=" * 50)
    
    # Check required environment variables
    required_vars = [
        "AZURE_STORAGE_CONNECTION_STRING",
        "AZURE_SEARCH_SERVICE_NAME",
        "AZURE_SEARCH_ADMIN_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease check your .env file and ensure all Azure credentials are set.")
        return
    
    print("✅ Environment variables loaded")
    
    # Run tests
    tests = [
        ("Blob Storage", test_blob_storage),
        ("Cognitive Search", test_cognitive_search),
        ("OpenAI", test_openai),
        ("Full Pipeline", test_full_pipeline)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running {test_name} Test")
        print('='*60)
        
        try:
            results[test_name] = await test_func()
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:<20}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All Azure services are working correctly!")
        print("\nNext steps:")
        print("1. Run 'python test_sharepoint.py' if you haven't already")
        print("2. Start the FastAPI server with 'python main.py'")
        print("3. Begin document ingestion with POST /api/ingest/start")
    else:
        print("\n🚨 Some tests failed! Please check your Azure configuration.")


if __name__ == "__main__":
    asyncio.run(main())
