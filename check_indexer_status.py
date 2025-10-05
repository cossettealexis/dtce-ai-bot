"""Check Azure Search Indexer status"""
from azure.search.documents.indexes import SearchIndexerClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings

load_dotenv()
settings = get_settings()

def check_status():
    indexer_client = SearchIndexerClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    indexer_name = "dtce-documents-indexer"
    
    try:
        status = indexer_client.get_indexer_status(indexer_name)
        
        print("\n📊 INDEXER STATUS\n" + "=" * 80)
        print(f"Name: {indexer_name}")
        print(f"Status: {status.status}")
        print(f"Last result: {status.last_result.status if status.last_result else 'N/A'}")
        
        if status.last_result:
            result = status.last_result
            
            # Check for items_processed attribute
            if hasattr(result, 'items_processed'):
                print(f"\n✅ Documents processed: {result.items_processed}")
            if hasattr(result, 'items_failed'):
                print(f"❌ Documents failed: {result.items_failed}")
            if hasattr(result, 'start_time'):
                print(f"🕐 Start time: {result.start_time}")
            if hasattr(result, 'end_time') and result.end_time:
                print(f"🕐 End time: {result.end_time}")
            
            # Show errors
            if hasattr(result, 'errors') and result.errors:
                print(f"\n⚠️  Errors ({len(result.errors)}):")
                for err in result.errors[:10]:
                    if hasattr(err, 'error_message'):
                        print(f"  - {err.error_message}")
                    else:
                        print(f"  - {err}")
        
        # Show execution history
        if hasattr(status, 'execution_history') and status.execution_history:
            print(f"\n📜 Recent executions: {len(status.execution_history)}")
            for i, exec in enumerate(status.execution_history[:5], 1):
                print(f"  {i}. {exec.status} - {exec.start_time}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    check_status()
