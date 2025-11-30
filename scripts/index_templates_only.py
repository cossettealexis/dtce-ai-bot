#!/usr/bin/env python3
"""
Index ONLY Templates and Master_Project_Folder_Aug24 files from blob storage.
This script DOES NOT DELETE anything - it only ADDS/UPDATES documents to the index.
"""

import os
import sys
import requests
from typing import List, Dict

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def get_api_base_url() -> str:
    """Get the API base URL from environment or use default."""
    # Use localhost for local testing
    return os.getenv("API_BASE_URL", "http://localhost:8000")

def list_all_blobs() -> List[Dict]:
    """List all blobs from Azure Storage via the API."""
    api_url = f"{get_api_base_url()}/documents/list"
    
    try:
        print("📋 Listing all blobs from Azure Storage...")
        response = requests.get(api_url, params={"source": "storage"}, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        documents = data.get("documents", [])
        print(f"✅ Found {len(documents)} total blobs in storage")
        return documents
        
    except requests.RequestException as e:
        print(f"❌ Failed to list blobs: {e}")
        return []

def filter_templates_blobs(blobs: List[Dict]) -> List[Dict]:
    """Filter blobs to only include Templates and Master_Project_Folder_Aug24."""
    filtered = []
    
    for blob in blobs:
        blob_name = blob.get("blob_name", "")
        
        # Check if blob is in Templates or Master_Project_Folder_Aug24
        if "Templates/" in blob_name or "Master_Project_Folder_Aug24/" in blob_name:
            filtered.append(blob)
    
    return filtered

def index_blob(blob_name: str) -> bool:
    """Index a single blob via the API. This only ADDS/UPDATES, never deletes."""
    api_url = f"{get_api_base_url()}/documents/index"
    
    try:
        print(f"📄 Indexing: {blob_name}")
        response = requests.post(api_url, params={"blob_name": blob_name}, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        if result.get("status") == "indexed":
            print(f"  ✅ Success")
            return True
        else:
            print(f"  ⚠️ Status unclear: {result}")
            return False
            
    except requests.RequestException as e:
        print(f"  ❌ Failed: {e}")
        return False

def main():
    """Main function to index only Templates files."""
    print("="*80)
    print("🚀 INDEX TEMPLATES & MASTER_PROJECT_FOLDER_AUG24 ONLY")
    print("="*80)
    print("⚠️  SAFETY GUARANTEE: This script ONLY adds/updates documents")
    print("⚠️  It will NEVER delete any existing documents from the index")
    print("="*80)
    print(f"🌐 API Base URL: {get_api_base_url()}")
    print()
    
    # List all blobs
    all_blobs = list_all_blobs()
    
    if not all_blobs:
        print("❌ No blobs found or failed to list blobs. Exiting.")
        return
    
    # Filter to only Templates and Master_Project_Folder_Aug24
    templates_blobs = filter_templates_blobs(all_blobs)
    
    print(f"\n🔍 Filtered Results:")
    print(f"   Total blobs in storage: {len(all_blobs)}")
    print(f"   Templates/Master_Project_Folder_Aug24 files: {len(templates_blobs)}")
    print()
    
    if not templates_blobs:
        print("❌ No Templates or Master_Project_Folder_Aug24 files found. Exiting.")
        return
    
    # Show what will be indexed
    print("📝 Files to be indexed:")
    for blob in templates_blobs[:10]:  # Show first 10
        print(f"   - {blob.get('blob_name')}")
    if len(templates_blobs) > 10:
        print(f"   ... and {len(templates_blobs) - 10} more files")
    print()
    
    # Confirm before proceeding
    response = input(f"⚠️  Proceed to index {len(templates_blobs)} files? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Indexing cancelled by user.")
        return
    
    # Index each blob
    success_count = 0
    failure_count = 0
    
    print(f"\n📚 Starting to index {len(templates_blobs)} files...")
    print("="*80)
    
    for i, blob in enumerate(templates_blobs, 1):
        blob_name = blob.get("blob_name")
        if not blob_name:
            print(f"⚠️ Skipping blob {i}: No blob_name found")
            failure_count += 1
            continue
        
        print(f"\n[{i}/{len(templates_blobs)}] {blob_name}")
        
        if index_blob(blob_name):
            success_count += 1
        else:
            failure_count += 1
    
    # Summary
    print("\n" + "="*80)
    print("📊 INDEXING SUMMARY")
    print("="*80)
    print(f"✅ Successfully indexed: {success_count}")
    print(f"❌ Failed to index: {failure_count}")
    print(f"📈 Total processed: {len(templates_blobs)}")
    print("="*80)
    
    if failure_count > 0:
        print(f"\n⚠️ {failure_count} documents failed to index. Check the logs above for details.")
    else:
        print(f"\n🎉 All Templates files indexed successfully!")
    
    print("\n✅ SAFETY CONFIRMED: No existing documents were deleted")
    print("="*80)

if __name__ == "__main__":
    main()
