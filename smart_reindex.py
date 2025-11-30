"""Smart reindexing: Only update documents that should contain text content"""
import asyncio
import os
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from openai import AsyncAzureOpenAI
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings
from dotenv import load_dotenv

load_dotenv()
settings = get_settings()

# File extensions that should contain extractable text
TEXT_EXTRACTABLE_EXTENSIONS = {
    '.pdf', '.docx', '.doc', '.txt', '.md', '.rtf', 
    '.odt', '.xlsx', '.xls', '.pptx', '.ppt'
}

# Extensions to IGNORE (binary files, images, etc.)
IGNORE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff',  # Images
    '.dwg', '.dxf',  # CAD files
    '.bak', '.tmp', '.log', '.slog',  # Backup/temp files
    '.zip', '.rar', '.7z',  # Archives
    '.msg',  # Email messages (often binary)
}

# Folders to ignore
IGNORE_FOLDERS = {
    'photos', '09 photos', 'images', 'backup', 'superseded', 
    'temp', 'archive', 'xref'
}

async def should_reindex(blob_url: str, filename: str) -> bool:
    """Determine if a document should be reindexed based on extension and folder"""
    # Get file extension
    ext = os.path.splitext(filename)[1].lower()
    
    # Skip ignored extensions
    if ext in IGNORE_EXTENSIONS:
        return False
    
    # Only process text-extractable files
    if ext not in TEXT_EXTRACTABLE_EXTENSIONS:
        return False
    
    # Check if in ignored folder
    blob_lower = blob_url.lower()
    for folder in IGNORE_FOLDERS:
        if f'/{folder}/' in blob_lower:
            return False
    
    return True

async def extract_text_from_blob(blob_url: str) -> str:
    """Extract text from PDF/DOCX using Azure Form Recognizer"""
    try:
        # Download blob content first
        blob_service_client = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        
        # Parse blob URL to get container and blob name
        url_parts = blob_url.split('/')
        container_name = url_parts[3]
        blob_name = '/'.join(url_parts[4:])
        
        # Download blob
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        blob_data = blob_client.download_blob().readall()
        
        # Initialize Form Recognizer client
        credential = AzureKeyCredential(settings.azure_form_recognizer_key)
        client = DocumentAnalysisClient(
            endpoint=settings.azure_form_recognizer_endpoint,
            credential=credential
        )
        
        # Analyze document from bytes
        poller = client.begin_analyze_document(
            "prebuilt-document", blob_data
        )
        result = poller.result()
        
        # Extract all text content
        content = ""
        for page in result.pages:
            for line in page.lines:
                content += line.content + "\n"
        
        return content.strip()
    except Exception as e:
        print(f"   ❌ Error extracting text: {str(e)}")
        return ""

async def generate_embedding(text: str, openai_client) -> list:
    """Generate embedding for text content"""
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000]  # Limit to avoid token limits
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"   ❌ Error generating embedding: {str(e)}")
        return None

async def reindex_documents():
    print("\n🔄 SMART REINDEXING: Text-Extractable Documents Only\n")
    print("=" * 80)
    
    # Read list of placeholder documents
    with open('files_to_reindex.txt', 'r') as f:
        placeholder_urls = [line.strip() for line in f.readlines()]
    
    print(f"\n📋 Found {len(placeholder_urls)} placeholder documents")
    
    # Filter to only text-extractable files
    docs_to_reindex = []
    for url in placeholder_urls:
        filename = url.split('/')[-1]
        if await should_reindex(url, filename):
            docs_to_reindex.append((url, filename))
    
    print(f"✅ Filtered to {len(docs_to_reindex)} text-extractable documents")
    print(f"⏭️  Skipping {len(placeholder_urls) - len(docs_to_reindex)} binary/image/backup files\n")
    
    if not docs_to_reindex:
        print("❌ No documents to reindex!")
        return
    
    # Initialize clients
    search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name="dtce-documents-index",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    # Process each document
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for i, (blob_url, filename) in enumerate(docs_to_reindex, 1):
        print(f"\n[{i}/{len(docs_to_reindex)}] {filename}")
        print(f"   URL: {blob_url[:100]}...")
        
        try:
            # Extract text content
            print("   📄 Extracting text...")
            content = await extract_text_from_blob(blob_url)
            
            if not content or len(content) < 50:
                print(f"   ⚠️  Insufficient content extracted ({len(content)} chars) - skipping")
                skipped_count += 1
                continue
            
            print(f"   ✅ Extracted {len(content)} characters")
            
            # Generate embedding
            print("   🧠 Generating embedding...")
            embedding = await generate_embedding(content, openai_client)
            
            if not embedding:
                print("   ⚠️  Failed to generate embedding - skipping")
                error_count += 1
                continue
            
            # Update document in search index
            print("   💾 Updating search index...")
            
            # Extract metadata from blob URL
            url_parts = blob_url.split('/')
            folder = '/'.join(url_parts[5:-1]) if len(url_parts) > 5 else ""
            
            # Find project name from URL
            project_name = ""
            for part in url_parts:
                if part.startswith('219'):  # Project numbers start with 219
                    project_name = part
                    break
            
            # Create updated document
            document = {
                "id": blob_url.replace('/', '_').replace(':', '_').replace('%20', '_'),
                "filename": filename,
                "content": content,
                "content_vector": embedding,
                "blob_url": blob_url,
                "folder": folder,
                "project_name": project_name
            }
            
            # Merge/upload document (updates if exists, creates if doesn't)
            result = search_client.merge_or_upload_documents([document])
            print(f"   ✅ Updated in index")
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            error_count += 1
    
    print("\n" + "=" * 80)
    print(f"\n📊 REINDEXING COMPLETE")
    print(f"   ✅ Successfully updated: {success_count}")
    print(f"   ⚠️  Skipped (no content): {skipped_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   📁 Total processed: {success_count + skipped_count + error_count}")

if __name__ == "__main__":
    asyncio.run(reindex_documents())
