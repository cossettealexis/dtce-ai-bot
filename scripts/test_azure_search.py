#!/usr/bin/env python3
"""
Test Azure Cognitive Search Integration
Quick script to verify the search service is working
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dtce_ai_bot.integrations.azure_search import create_search_index_if_not_exists, get_search_index_client
from dtce_ai_bot.config.settings import get_settings


async def test_search_connection():
    """Test connection to Azure Cognitive Search."""
    try:
        settings = get_settings()
        
        print("🔍 Testing Azure Cognitive Search Connection...")
        print(f"Service Name: {settings.azure_search_service_name}")
        print(f"Index Name: {settings.azure_search_index_name}")
        
        # Test index client connection
        index_client = get_search_index_client()
        
        # Try to list indexes to test connection
        indexes = list(index_client.list_indexes())
        print(f"✅ Connected! Found {len(indexes)} existing indexes")
        
        # Create our index if it doesn't exist
        print("\n📋 Creating search index if needed...")
        await create_search_index_if_not_exists()
        print("✅ Index ready!")
        
        # Verify our index exists
        try:
            our_index = index_client.get_index(settings.azure_search_index_name)
            print(f"✅ Index '{settings.azure_search_index_name}' confirmed with {len(our_index.fields)} fields")
            
            # List field names
            field_names = [field.name for field in our_index.fields]
            print(f"📊 Index fields: {', '.join(field_names)}")
            
        except Exception as e:
            print(f"❌ Could not verify index: {e}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Azure Search connection failed: {e}")
        print("\n💡 Make sure you have:")
        print("   - AZURE_SEARCH_SERVICE_NAME=dtceai-search")
        print("   - AZURE_SEARCH_ADMIN_KEY=<your-admin-key>")
        print("   - Valid Azure credentials")
        return False


async def main():
    """Main test function."""
    print("🚀 DTCE AI Bot - Azure Search Integration Test")
    print("=" * 50)
    
    # Check environment variables
    settings = get_settings()
    
    required_vars = [
        "azure_search_service_name",
        "azure_search_admin_key",
        "azure_search_index_name"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not getattr(settings, var):
            missing_vars.append(var.upper())
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file")
        return
    
    # Test connection
    success = await test_search_connection()
    
    if success:
        print("\n🎉 Azure Cognitive Search integration is ready!")
        print("You can now:")
        print("   - Upload documents via POST /documents/upload")
        print("   - Index documents via POST /documents/index")
        print("   - Search documents via GET /documents/search")
    else:
        print("\n❌ Integration test failed")
        print("Check your Azure configuration and try again")


if __name__ == "__main__":
    asyncio.run(main())
