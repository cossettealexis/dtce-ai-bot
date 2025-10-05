"""Smart update: Scan actual blob storage and update search index with real content"""
import asyncio
import os
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from openai import AsyncAzureOpenAI
import sys
import hashlib
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

# Folders to prioritize (company policies and standards)
PRIORITY_FOLDERS = [
    'dtce workplace essentials',
    'health & safety',
    'policy',
    'standards',
    'engineering'
]

async def should_index_blob(blob_name: str) -> bool:
    """Determine if a blob should be indexed"""
    # Get file extension
    ext = os.path.splitext(blob_name)[1].lower()
    
    # Only process text-extractable files
    if ext not in TEXT_EXTRACTABLE_EXTENSIONS:
        return False
    
    # Skip .keep files
    if blob_name.endswith('.keep'):
        return False
    
    # Skip superseded/backup files unless they're important
    blob_lower = blob_name.lower()
    if 'superseded' in blob_lower or 'backup' in blob_lower or 'draft' in blob_lower:
        return False
    
    return True

async def extract_text_from_blob_bytes(blob_data: bytes) -> str:
    """Extract text from PDF/DOCX bytes using Azure Form Recognizer"""
    try:
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
        print(f"      ❌ Error extracting text: {str(e)[:200]}")
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
        print(f"      ❌ Error generating embedding: {str(e)[:200]}")
        return None

def generate_document_id(blob_url: str) -> str:
    """Generate a consistent document ID from blob URL"""
    # Use MD5 hash of URL for consistent, safe IDs
    return hashlib.md5(blob_url.encode()).hexdigest()

async def update_search_index_from_blob_storage():
    print("\n🔄 SMART UPDATE: Scanning Blob Storage & Updating Search Index\n")
    print("=" * 80)
    
    # Initialize clients
    blob_service_client = BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )
    container_client = blob_service_client.get_container_client("dtce-documents")
    
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
    
    # Scan all blobs in the container
    print("📁 Scanning blob storage for text-extractable files...\n")
    
    blobs_to_index = []
    total_blobs = 0
    
    for blob in container_client.list_blobs():
        total_blobs += 1
        if await should_index_blob(blob.name):
            # Prioritize policy/standards documents
            is_priority = any(folder in blob.name.lower() for folder in PRIORITY_FOLDERS)
            blobs_to_index.append((blob.name, blob.size, is_priority))
    
    # Sort: priority documents first, then by name
    blobs_to_index.sort(key=lambda x: (not x[2], x[0]))
    
    print(f"📊 Found {total_blobs} total blobs")
    print(f"✅ {len(blobs_to_index)} text-extractable documents to process")
    print(f"⚠️  {len([b for b in blobs_to_index if b[2]])} priority documents (policies/standards)\n")
    
    # Process each blob
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for i, (blob_name, blob_size, is_priority) in enumerate(blobs_to_index, 1):
        priority_marker = "⭐" if is_priority else "  "
        print(f"\n{priority_marker}[{i}/{len(blobs_to_index)}] {blob_name}")
        print(f"      Size: {blob_size:,} bytes")
        
        try:
            # Download blob
            blob_client = container_client.get_blob_client(blob_name)
            print("      📥 Downloading...")
            blob_data = blob_client.download_blob().readall()
            
            # Extract text
            print("      📄 Extracting text...")
            content = await extract_text_from_blob_bytes(blob_data)
            
            if not content or len(content) < 50:
                print(f"      ⚠️  Insufficient content extracted ({len(content)} chars) - skipping")
                skipped_count += 1
                continue
            
            print(f"      ✅ Extracted {len(content):,} characters")
            
            # Generate embedding
            print("      🧠 Generating embedding...")
            embedding = await generate_embedding(content, openai_client)
            
            if not embedding:
                print("      ⚠️  Failed to generate embedding - skipping")
                error_count += 1
                continue
            
            # Create blob URL
            blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/dtce-documents/{blob_name}"
            
            # Extract metadata
            filename = os.path.basename(blob_name)
            folder = os.path.dirname(blob_name)
            
            # Find project name from path
            project_name = ""
            path_parts = blob_name.split('/')
            for part in path_parts:
                if part.startswith('219') or part.startswith('220'):  # Project numbers
                    project_name = part
                    break
            
            # Create document
            doc_id = generate_document_id(blob_url)
            document = {
                "id": doc_id,
                "filename": filename,
                "content": content,
                "content_vector": embedding,
                "blob_url": blob_url,
                "folder": folder,
                "project_name": project_name if project_name else "Company Documents"
            }
            
            # Update search index (merge_or_upload will update if exists, create if not)
            print("      💾 Updating search index...")
            result = search_client.merge_or_upload_documents([document])
            print(f"      ✅ Updated in index (ID: {doc_id[:16]}...)")
            success_count += 1
            
        except Exception as e:
            print(f"      ❌ Error: {str(e)[:200]}")
            error_count += 1
    
    print("\n" + "=" * 80)
    print(f"\n📊 UPDATE COMPLETE")
    print(f"   ✅ Successfully updated: {success_count}")
    print(f"   ⚠️  Skipped (no content): {skipped_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   📁 Total processed: {success_count + skipped_count + error_count}")
    print(f"\n   💡 Note: Existing documents were UPDATED, not recreated")
    print(f"   💡 No documents were deleted from the index")

if __name__ == "__main__":
    asyncio.run(update_search_index_from_blob_storage())
