"""Create Azure Search Data Source and Indexer to automatically extract ALL documents"""
import os
from azure.search.documents.indexes import SearchIndexerClient, SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SearchIndexer,
    FieldMapping,
    IndexingParameters,
    IndexingParametersConfiguration
)
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings

load_dotenv()
settings = get_settings()

def create_indexer():
    print("\n🔄 AZURE SEARCH INDEXER - Auto-extract ALL documents\n" + "=" * 80)
    
    # Indexer client
    indexer_client = SearchIndexerClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    # Step 1: Create data source
    print("\n📁 Creating data source connection...")
    data_source_name = "dtce-documents-datasource"
    
    data_source = SearchIndexerDataSourceConnection(
        name=data_source_name,
        type="azureblob",
        connection_string=settings.azure_storage_connection_string,
        container=SearchIndexerDataContainer(name="dtce-documents")
    )
    
    try:
        indexer_client.create_or_update_data_source_connection(data_source)
        print(f"✅ Data source '{data_source_name}' created")
    except Exception as e:
        print(f"❌ Data source error: {str(e)[:200]}")
        return
    
    # Step 2: Create indexer with OCR/text extraction
    print("\n🤖 Creating indexer with document extraction...")
    indexer_name = "dtce-documents-indexer"
    
    indexer = SearchIndexer(
        name=indexer_name,
        data_source_name=data_source_name,
        target_index_name="dtce-documents-index",
        parameters=IndexingParameters(
            configuration=IndexingParametersConfiguration(
                parsing_mode="default",
                excluded_file_name_extensions=".jpg,.jpeg,.png,.gif,.bmp,.dwg,.dxf",  # Skip images/CAD
                indexed_file_name_extensions=".pdf,.docx,.doc,.txt,.md,.rtf,.xlsx,.xls,.pptx,.ppt"
            )
        ),
        field_mappings=[
            FieldMapping(source_field_name="metadata_storage_name", target_field_name="filename"),
            FieldMapping(source_field_name="metadata_storage_path", target_field_name="blob_url"),
        ]
    )
    
    try:
        indexer_client.create_or_update_indexer(indexer)
        print(f"✅ Indexer '{indexer_name}' created")
    except Exception as e:
        print(f"❌ Indexer error: {str(e)[:200]}")
        return
    
    # Step 3: Run the indexer
    print("\n▶️  Running indexer (this will process ALL text documents)...")
    try:
        indexer_client.run_indexer(indexer_name)
        print("✅ Indexer started!")
        print("\n" + "=" * 80)
        print("\n📊 INDEXER IS RUNNING")
        print("\nThe indexer will:")
        print("  1. Scan ALL blobs in dtce-documents container")
        print("  2. Extract text from PDFs, DOCX, etc.")
        print("  3. Update search index automatically")
        print("  4. Skip photos/images/CAD files")
        print("\n💡 Check status with: .venv/bin/python check_indexer_status.py")
        print("   This will take 10-30 minutes depending on document count.")
    except Exception as e:
        print(f"❌ Run error: {str(e)[:200]}")

if __name__ == "__main__":
    create_indexer()
