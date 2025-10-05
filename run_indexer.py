"""Run the existing Azure Search Indexer to reindex ALL documents"""
from azure.search.documents.indexes import SearchIndexerClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings

load_dotenv()
settings = get_settings()

def run_indexer():
    print("\n▶️  RUNNING AZURE SEARCH INDEXER\n" + "=" * 80)
    
    indexer_client = SearchIndexerClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    # List all indexers
    print("📋 Available indexers:")
    for indexer in indexer_client.get_indexers():
        print(f"  - {indexer.name}")
    
    # Run the indexer
    indexer_name = "dtce-documents-indexer"
    print(f"\n▶️  Running '{indexer_name}'...")
    
    try:
        indexer_client.run_indexer(indexer_name)
        print(f"✅ Indexer '{indexer_name}' started!")
        print("\n" + "=" * 80)
        print("\n📊 INDEXER IS NOW RUNNING")
        print("\nThe indexer will:")
        print("  1. Scan ALL blobs in storage")
        print("  2. Extract text from documents")
        print("  3. Update search index")
        print("\n💡 Check progress: .venv/bin/python check_indexer_status.py")
        print("   Estimated time: 10-30 minutes for thousands of documents")
    except Exception as e:
        error_msg = str(e)
        if "is currently running" in error_msg:
            print(f"⏳ Indexer is ALREADY RUNNING!")
            print(f"\n💡 Check status: .venv/bin/python check_indexer_status.py")
        else:
            print(f"❌ Error: {error_msg[:300]}")

if __name__ == "__main__":
    run_indexer()
