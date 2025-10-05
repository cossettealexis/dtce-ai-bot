"""List actual files in the Wellbeing Policy folder"""
import os
from azure.storage.blob import BlobServiceClient
from urllib.parse import unquote
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings
from dotenv import load_dotenv

load_dotenv()
settings = get_settings()

def list_wellness_files():
    print("\n📁 LISTING ACTUAL FILES IN WELLBEING POLICY FOLDER\n")
    print("=" * 80)
    
    # Connect to blob storage
    blob_service_client = BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )
    
    container_client = blob_service_client.get_container_client("dtce-documents")
    
    # List all blobs in the Health & Safety/Policy folder
    prefix = "DTCE Workplace Essentials/Health & Safety/01_Policy/"
    
    print(f"Searching for files with prefix: {prefix}\n")
    
    blobs = container_client.list_blobs(name_starts_with=prefix)
    
    found_files = []
    for blob in blobs:
        found_files.append(blob.name)
        print(f"✅ Found: {blob.name}")
        print(f"   Size: {blob.size} bytes")
        print(f"   Last Modified: {blob.last_modified}")
        print()
    
    if not found_files:
        print("❌ No files found in this folder!")
        print("\nLet me try different variations:")
        
        # Try URL-encoded version
        variations = [
            "DTCE%20Workplace%20Essentials/Health%20%26%20Safety/01_Policy/",
            "DTCE Workplace Essentials/Health and Safety/01_Policy/",
            "DTCE Workplace Essentials/Health & Safety/Policy/",
        ]
        
        for variant in variations:
            print(f"\n🔍 Trying: {variant}")
            blobs = container_client.list_blobs(name_starts_with=variant)
            for blob in blobs:
                print(f"   ✅ {blob.name}")
    
    print("\n" + "=" * 80)
    print(f"\n📊 Total files found: {len(found_files)}")

if __name__ == "__main__":
    list_wellness_files()
