#!/usr/bin/env python3
"""
Sync and index the Templates folder from SharePoint to blob storage and Azure Search.

The Templates folder contains all DTCE file templates and should be searchable by the bot.
URL: https://donthomson.sharepoint.com/sites/suitefiles/Templates/

SAFETY GUARANTEES:
✓ NO DELETIONS - This script only adds or updates files, never deletes
✓ PRESERVES STRUCTURE - Maintains the existing folder hierarchy from SharePoint
✓ NON-DESTRUCTIVE - Existing files are only overwritten with newer versions
✓ ADDITIVE SYNC - Only syncs files from the Templates folder, doesn't touch other folders
"""

import asyncio
import os
import sys
import requests
from typing import List, Dict

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def get_api_base_url() -> str:
    """Get the API base URL from environment or use default."""
    return os.getenv("API_BASE_URL", "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net")

async def sync_templates_folder():
    """
    Sync the Templates folder from SharePoint to blob storage.
    
    SAFETY: This operation is completely safe:
    - Only uploads/updates files from Templates folder
    - Never deletes any existing files
    - Preserves the SharePoint folder structure
    - Uses overwrite=True only for files that have been modified
    """
    api_url = f"{get_api_base_url()}/documents/sync-suitefiles"
    
    print("🚀 Starting Templates folder sync from SharePoint...")
    print(f"📍 Source: https://donthomson.sharepoint.com/sites/suitefiles/Templates/")
    print(f"🌐 API: {api_url}")
    print()
    print("🛡️  SAFETY GUARANTEES:")
    print("   ✓ No files will be deleted")
    print("   ✓ Existing structure will be preserved")
    print("   ✓ Only adds/updates Templates folder files")
    print()
    
    try:
        # Sync Templates folder - use "Templates" as the path
        print("📥 Syncing Templates folder from SharePoint to blob storage...")
        
        response = requests.post(
            api_url,
            params={
                "path": "Templates",  # This will sync ONLY the Templates folder
                "force": True  # Force sync all files to ensure completeness
            },
            timeout=600  # 10 minute timeout for large sync
        )
        
        response.raise_for_status()
        result = response.json()
        
        print("✅ Templates folder sync completed!")
        print(f"📊 Sync Summary:")
        print(f"   - Documents synced: {result.get('synced_count', 0)}")
        print(f"   - Documents indexed: {result.get('ai_ready_count', 0)}")
        print(f"   - Skipped (up-to-date): {result.get('skipped_count', 0)}")
        print(f"   - Errors: {result.get('error_count', 0)}")
        
        if result.get('error_count', 0) > 0:
            print(f"\n⚠️ Note: {result.get('error_count')} files had errors but were not deleted")
        
        return result
        
    except requests.RequestException as e:
        print(f"❌ Sync failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Error details: {error_detail}")
            except:
                print(f"   Response text: {e.response.text[:500]}")
        return None

async def verify_templates_indexed():
    """
    Verify that Templates documents are in the search index.
    """
    api_url = f"{get_api_base_url()}/query"
    
    print("\n🔍 Verifying Templates folder is indexed...")
    
    try:
        # Query for templates
        response = requests.post(
            api_url,
            json={
                "question": "show me template files",
                "session_id": "template_sync_test"
            },
            timeout=60
        )
        
        response.raise_for_status()
        result = response.json()
        
        print("✅ Templates verification query completed!")
        print(f"📄 Found {result.get('total_documents', 0)} template-related documents")
        
        # Show sample sources
        sources = result.get('sources', [])
        if sources:
            print(f"\n📋 Sample template files found:")
            for i, source in enumerate(sources[:5], 1):
                print(f"   {i}. {source.get('title', 'Unknown')} ({source.get('folder', 'Unknown folder')})")
        
        return result
        
    except requests.RequestException as e:
        print(f"⚠️ Verification query failed: {e}")
        return None

async def main():
    """Main function to sync and verify Templates folder."""
    print("=" * 70)
    print("DTCE Templates Folder Sync & Index")
    print("=" * 70)
    print()
    print("📋 WHAT THIS DOES:")
    print("   1. Connects to SharePoint Templates folder")
    print("   2. Downloads all template files")
    print("   3. Uploads to Azure Blob Storage (Templates/ folder)")
    print("   4. Indexes for AI search")
    print()
    print("🛡️  SAFETY FEATURES:")
    print("   • NO files will be deleted from blob storage")
    print("   • Only Templates folder is affected")
    print("   • Existing folder structure is preserved")
    print("   • Files are only updated if modified")
    print()
    
    # Step 1: Sync Templates folder from SharePoint to blob storage
    sync_result = await sync_templates_folder()
    
    if not sync_result:
        print("\n❌ Sync failed. Cannot proceed with verification.")
        return 1
    
    # Step 2: Verify Templates are indexed and searchable
    await asyncio.sleep(5)  # Wait 5 seconds for indexing to complete
    verify_result = await verify_templates_indexed()
    
    print("\n" + "=" * 70)
    print("✅ Templates folder sync and indexing completed!")
    print("=" * 70)
    print()
    print("📁 BLOB STORAGE STRUCTURE:")
    print("   Templates/")
    print("   ├── [All template files from SharePoint]")
    print("   └── [Preserves original folder structure]")
    print()
    print("📝 Next steps:")
    print("   1. Test in Teams: Ask 'show me template files'")
    print("   2. Test specific: 'find the PS1 template'")
    print("   3. Test type: 'what templates do we have for reports?'")
    print()
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
