#!/usr/bin/env python3
"""
Bulk index all blobs from Azure Storage into the search index.
This script lists all blobs and indexes them one by one.
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

def list_all_blobs() -> List[Dict]:
    """List all blobs from Azure Storage via the API."""
    api_url = f"{get_api_base_url()}/documents/list"
    
    try:
        print("📋 Listing all blobs from Azure Storage...")
        response = requests.get(api_url, params={"source": "storage"})
        response.raise_for_status()
        
        data = response.json()
        documents = data.get("documents", [])
        print(f"✅ Found {len(documents)} blobs in storage")
        return documents
        
    except requests.RequestException as e:
        print(f"❌ Failed to list blobs: {e}")
        return []

def index_blob(blob_name: str) -> bool:
    """Index a single blob via the API."""
    api_url = f"{get_api_base_url()}/documents/index"
    
    try:
        print(f"📄 Indexing blob: {blob_name}")
        response = requests.post(api_url, params={"blob_name": blob_name})
        response.raise_for_status()
        
        result = response.json()
        if result.get("status") == "indexed":
            print(f"✅ Successfully indexed: {blob_name}")
            return True
        else:
            print(f"⚠️ Indexing status unclear for {blob_name}: {result}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Failed to index {blob_name}: {e}")
        return False

def main():
    """Main function to bulk index all blobs."""
    print("🚀 Starting bulk indexing of all blobs...")
    print(f"🌐 API Base URL: {get_api_base_url()}")
    
    # List all blobs
    blobs = list_all_blobs()
    
    if not blobs:
        print("❌ No blobs found or failed to list blobs. Exiting.")
        return
    
    # Index each blob
    success_count = 0
    failure_count = 0
    
    print(f"\n📚 Starting to index {len(blobs)} blobs...")
    
    for i, blob in enumerate(blobs, 1):
        blob_name = blob.get("blob_name")
        if not blob_name:
            print(f"⚠️ Skipping blob {i}: No blob_name found")
            failure_count += 1
            continue
            
        print(f"\n[{i}/{len(blobs)}] Processing: {blob_name}")
        
        if index_blob(blob_name):
            success_count += 1
        else:
            failure_count += 1
    
    # Summary
    print(f"\n📊 Bulk indexing completed!")
    print(f"✅ Successfully indexed: {success_count}")
    print(f"❌ Failed to index: {failure_count}")
    print(f"📈 Total processed: {len(blobs)}")
    
    if failure_count > 0:
        print(f"\n⚠️ {failure_count} documents failed to index. Check the logs above for details.")
    else:
        print(f"\n🎉 All documents indexed successfully!")

if __name__ == "__main__":
    main()
