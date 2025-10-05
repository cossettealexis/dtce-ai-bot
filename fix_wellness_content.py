"""
Fix wellness policy documents by reindexing with proper content extraction.
The documents exist but only have filenames as content - need to extract actual text.
"""

import asyncio
import os
import sys
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
import structlog

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dtce_ai_bot.config.settings import settings
from dtce_ai_bot.utils.text_extractor import AzureTextExtractor

logger = structlog.get_logger()

async def extract_and_reindex_document(blob_name: str, blob_client, search_client):
    """Extract text from document and update search index."""
    
    try:
        logger.info(f"Processing: {blob_name}")
        
        # Get blob properties
        props = blob_client.get_blob_properties()
        metadata = props.metadata or {}
        content_type = metadata.get('content_type', props.content_settings.content_type)
        
        # Download blob
        blob_data = blob_client.download_blob().readall()
        
        # Extract text using Azure Form Recognizer
        extractor = AzureTextExtractor(
            settings.azure_form_recognizer_endpoint,
            settings.azure_form_recognizer_key
        )
        
        extraction_result = await extractor.extract_text_from_blob(blob_client, content_type)
        
        if not extraction_result or not extraction_result.get('text'):
            logger.error(f"No text extracted from {blob_name}")
            return False
            
        extracted_text = extraction_result['text']
        logger.info(f"✅ Extracted {len(extracted_text)} characters from {blob_name}")
        
        # Prepare search document
        import re
        document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob_name)
        document_id = re.sub(r'_+', '_', document_id).strip('_')
        
        folder = metadata.get('folder', '')
        
        search_doc = {
            "id": document_id,
            "blob_name": blob_name,
            "blob_url": blob_client.url,
            "filename": metadata.get('original_filename', blob_name),
            "content_type": content_type,
            "folder": folder,
            "size": int(metadata.get('size', len(blob_data))),
            "content": extracted_text,  # THIS is the key fix!
            "last_modified": props.last_modified.isoformat(),
            "created_date": props.creation_time.isoformat() if props.creation_time else props.last_modified.isoformat(),
            "project_name": metadata.get('project_name', ''),
            "year": metadata.get('year')
        }
        
        # Generate embeddings
        from openai import AsyncAzureOpenAI
        openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        
        response = await openai_client.embeddings.create(
            input=extracted_text[:8000],  # Limit to token constraints
            model=settings.azure_openai_embedding_deployment
        )
        
        search_doc['content_vector'] = response.data[0].embedding
        
        # Upload to search
        result = search_client.upload_documents(documents=[search_doc])
        
        logger.info(f"✅ Reindexed {blob_name} with {len(extracted_text)} characters")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to process {blob_name}: {e}")
        return False


async def main():
    """Main function to fix wellness policy documents."""
    
    # Initialize clients
    storage_client = BlobServiceClient(
        account_url=f"https://{settings.azure_storage_account}.blob.core.windows.net",
        credential=settings.azure_storage_key
    )
    
    search_client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=AzureKeyCredential(settings.azure_search_api_key)
    )
    
    # Find wellness policy documents
    container_client = storage_client.get_container_client(settings.azure_storage_container)
    
    wellness_blobs = []
    logger.info("🔍 Searching for wellness policy documents...")
    
    async for blob in container_client.list_blobs():
        if 'wellbeing' in blob.name.lower() or 'wellness' in blob.name.lower():
            wellness_blobs.append(blob.name)
            logger.info(f"Found: {blob.name}")
    
    logger.info(f"\n📄 Found {len(wellness_blobs)} wellness policy documents")
    
    # Reindex each one
    success_count = 0
    for blob_name in wellness_blobs:
        blob_client = storage_client.get_blob_client(
            container=settings.azure_storage_container,
            blob=blob_name
        )
        
        if await extract_and_reindex_document(blob_name, blob_client, search_client):
            success_count += 1
    
    logger.info(f"\n✅ Successfully reindexed {success_count}/{len(wellness_blobs)} documents")


if __name__ == "__main__":
    asyncio.run(main())
