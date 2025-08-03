#!/usr/bin/env python3
"""
Test script to verify SharePoint connectivity and list basic folder structure.
Run this script first to ensure your SharePoint configuration is working.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.sharepoint_client import SharePointClient


async def test_sharepoint_connection():
    """Test SharePoint connection and list folder structure."""
    
    print("🔍 Testing SharePoint Connection...")
    print("=" * 50)
    
    try:
        # Initialize client
        client = SharePointClient()
        
        # Test authentication
        print("🔐 Authenticating with Microsoft Graph API...")
        auth_success = await client.authenticate()
        
        if not auth_success:
            print("❌ Authentication failed!")
            return False
        
        print("✅ Authentication successful!")
        
        # Test listing Engineering folder
        print("\n📁 Testing Engineering folder access...")
        try:
            engineering_contents = await client.list_folder_contents("Engineering")
            print(f"✅ Found {len(engineering_contents)} items in Engineering folder")
            
            # Show first few items
            for i, item in enumerate(engineering_contents[:5]):
                item_type = "📁" if item.get("folder") else "📄"
                print(f"   {item_type} {item.get('name', 'Unknown')}")
            
            if len(engineering_contents) > 5:
                print(f"   ... and {len(engineering_contents) - 5} more items")
                
        except Exception as e:
            print(f"❌ Failed to access Engineering folder: {e}")
        
        # Test listing Projects folder
        print("\n📁 Testing Projects folder access...")
        try:
            projects_contents = await client.list_folder_contents("Projects")
            print(f"✅ Found {len(projects_contents)} items in Projects folder")
            
            # Show project numbers
            project_folders = [item for item in projects_contents if item.get("folder") and item.get("name", "").isdigit()]
            print(f"📊 Found {len(project_folders)} project folders:")
            
            for project in project_folders[:10]:  # Show first 10
                print(f"   📁 Project {project.get('name')}")
            
            if len(project_folders) > 10:
                print(f"   ... and {len(project_folders) - 10} more projects")
                
        except Exception as e:
            print(f"❌ Failed to access Projects folder: {e}")
        
        # Test scanning a single project
        if project_folders:
            test_project = project_folders[0]["name"]
            print(f"\n🔍 Testing scan of Project {test_project}...")
            try:
                project_docs = await client._scan_project_folder(f"Projects/{test_project}")
                print(f"✅ Found {len(project_docs)} documents in Project {test_project}")
                
                # Show document types
                doc_types = {}
                for doc in project_docs:
                    doc_type = doc.document_type.value
                    doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                
                print("📋 Document types found:")
                for doc_type, count in doc_types.items():
                    print(f"   {doc_type}: {count} documents")
                    
            except Exception as e:
                print(f"❌ Failed to scan Project {test_project}: {e}")
        
        print(f"\n✅ SharePoint connection test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ SharePoint connection test failed: {e}")
        return False


async def main():
    """Main test function."""
    
    # Load environment variables
    load_dotenv()
    
    print("🚀 DTCE AI Assistant - SharePoint Connection Test")
    print("=" * 60)
    
    # Check required environment variables
    required_vars = [
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_TENANT_ID", 
        "SHAREPOINT_SITE_ID"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease check your .env file and ensure all required variables are set.")
        return
    
    print("✅ Environment variables loaded")
    
    # Run SharePoint test
    success = await test_sharepoint_connection()
    
    if success:
        print("\n🎉 All tests passed! SharePoint connection is working correctly.")
        print("\nNext steps:")
        print("1. Set up Azure services (Blob Storage, Cognitive Search, OpenAI)")
        print("2. Update your .env file with Azure credentials")
        print("3. Run 'python test_azure.py' to test Azure connections")
        print("4. Start the FastAPI server with 'python main.py'")
    else:
        print("\n🚨 Tests failed! Please check your configuration and try again.")


if __name__ == "__main__":
    asyncio.run(main())
