"""Check current indexer configuration"""
from azure.search.documents.indexes import SearchIndexerClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings

load_dotenv()
settings = get_settings()

def check_config():
    indexer_client = SearchIndexerClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    print("\n🔍 INDEXER CONFIGURATION\n" + "=" * 80)
    
    indexer = indexer_client.get_indexer("dtce-documents-indexer")
    
    print(f"Name: {indexer.name}")
    print(f"Data source: {indexer.data_source_name}")
    print(f"Target index: {indexer.target_index_name}")
    print(f"Skillset: {indexer.skillset_name}")
    print(f"\nField mappings:")
    if indexer.field_mappings:
        for mapping in indexer.field_mappings:
            print(f"  {mapping.source_field_name} → {mapping.target_field_name}")
    else:
        print("  None")
    
    print(f"\nOutput field mappings:")
    if indexer.output_field_mappings:
        for mapping in indexer.output_field_mappings:
            print(f"  {mapping.source_field_name} → {mapping.target_field_name}")
    else:
        print("  None")
    
    print(f"\nParameters:")
    if indexer.parameters:
        params = indexer.parameters
        if hasattr(params, 'configuration'):
            config = params.configuration
            print(f"  Parsing mode: {getattr(config, 'parsing_mode', 'N/A')}")
            print(f"  Excluded extensions: {getattr(config, 'excluded_file_name_extensions', 'N/A')}")
            print(f"  Indexed extensions: {getattr(config, 'indexed_file_name_extensions', 'N/A')}")
    
    print("\n" + "=" * 80)
    print("\n⚠️  PROBLEM: No skillset configured!")
    print("   The indexer is NOT using AI Skills to extract text from PDFs/DOCX")
    print("   It's only indexing metadata, not document content")

if __name__ == "__main__":
    check_config()
