#!/usr/bin/env python3
"""
Sync ONLY the Templates drive from SharePoint to blob storage.

This uses the new drive filtering feature to sync only the Templates document library,
avoiding the timeout issues caused by syncing all drives.
"""

import requests
import os

def sync_templates_drive():
    """Sync only the Templates drive from SharePoint."""
    api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    print("\n" + "="*80)
    print("TEMPLATES DRIVE SYNC")
    print("="*80)
    print("\n📁 Source: SharePoint Templates document library")
    print("☁️  Target: Azure Blob Storage")
    print("🔍 Files: ~75 template files")
    
    print("\n✅ SAFETY GUARANTEES:")
    print("   • Will NOT delete any existing files")
    print("   • Will NOT modify existing blobs")
    print("   • Will ONLY add new files or update changed files")
    print("   • Preserves all folder structure and metadata")
    
    # Ask for confirmation
    print("\n" + "-"*80)
    confirm = input("\n👉 Proceed with Templates drive sync? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("\n❌ Sync cancelled by user")
        return
    
    print("\n🚀 Starting sync...\n")
    print("📡 API: POST /documents/sync-suitefiles?drive=Templates&force=True")
    print("⏱️  Estimated time: 1-2 minutes for 75 files\n")
    
    try:
        response = requests.post(
            f"{api_url}/documents/sync-suitefiles",
            params={
                "drive": "Templates",  # Sync ONLY the Templates drive
                "force": "true"         # Force sync all files
            },
            timeout=300  # 5 minute timeout (should be plenty for 75 files)
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ SYNC COMPLETED SUCCESSFULLY!")
            print("\n📊 Results:")
            print(f"   • Files synced: {result.get('synced_count', 0)}")
            print(f"   • Files processed: {result.get('processed_count', 0)}")
            print(f"   • AI-ready documents: {result.get('ai_ready_count', 0)}")
            print(f"   • Files skipped (up-to-date): {result.get('skipped_count', 0)}")
            print(f"   • Errors: {result.get('error_count', 0)}")
            
            if result.get('performance_notes'):
                print("\n📝 Notes:")
                for note in result['performance_notes']:
                    print(f"   • {note}")
            
            # Verification
            print("\n🔍 Templates folder is now searchable!")
            print("   Try asking: 'Show me template files'")
            print("   Or: 'Find the PS1 template'")
            
        else:
            print(f"\n❌ Sync failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("\n⏱️  Request timed out after 5 minutes")
        print("The sync may still be running. Check API logs.")
        return False
    except Exception as e:
        print(f"\n❌ Error during sync: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    success = sync_templates_drive()
    exit(0 if success else 1)
