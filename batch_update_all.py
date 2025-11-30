"""Batch update: Process all text documents in manageable batches"""
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

# Text-extractable extensions
TEXT_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf', '.xlsx', '.xls', '.pptx', '.ppt'}

# Folders to skip
SKIP_FOLDERS = ['photos', '09 photos', 'images', 'backup', 'superseded', 'temp', 'archive', 'drafts']

async def extract_text(blob_data: bytes) -> str:
    """Extract text using Form Recognizer"""
    try:
        credential = AzureKeyCredential(settings.azure_form_recognizer_key)
        client = DocumentAnalysisClient(endpoint=settings.azure_form_recognizer_endpoint, credential=credential)
        poller = client.begin_analyze_document("prebuilt-document", blob_data)
        result = poller.result()
        content = "\n".join(line.content for page in result.pages for line in page.lines)
        return content.strip()
    except Exception as e:
        return ""

async def generate_embedding(text: str, openai_client) -> list:
    """Generate embedding"""
    try:
        response = await openai_client.embeddings.create(model="text-embedding-3-small", input=text[:8000])
        return response.data[0].embedding
    except:
        return None

async def process_documents():
    print("\n🔄 BATCH UPDATE: All Text Documents\n" + "=" * 80)
    
    # Initialize
    blob_service = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    container = blob_service.get_container_client("dtce-documents")
    search_client = SearchClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        index_name="dtce-documents-index",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    # Find all text documents - process incrementally to avoid memory issues
    print("📁 Scanning for text documents (this may take a moment)...")
    text_docs = []
    blob_count = 0
    
    try:
        # Use by_page() without arguments - it will paginate automatically
        blob_iterator = container.list_blobs()
        
        for blob in blob_iterator:
            blob_count += 1
            if blob_count % 1000 == 0:
                print(f"   Scanned {blob_count} blobs, found {len(text_docs)} text documents...")
            
            ext = os.path.splitext(blob.name)[1].lower()
            if ext in TEXT_EXTENSIONS:
                # Skip certain folders
                if any(skip in blob.name.lower() for skip in SKIP_FOLDERS):
                    continue
                if blob.name.endswith('.keep'):
                    continue
                text_docs.append((blob.name, blob.size))
                
    except Exception as e:
        print(f"⚠️  Scanning error: {str(e)[:200]}")
        print(f"   Continuing with {len(text_docs)} documents found so far...")
    
    print(f"✅ Scanned {blob_count} total blobs")
    print(f"✅ Found {len(text_docs)} text documents to process\n")
    
    success = error = skipped = 0
    
    for i, (blob_name, size) in enumerate(text_docs, 1):
        print(f"[{i}/{len(text_docs)}] {os.path.basename(blob_name)[:60]}")
        
        try:
            # Download
            blob_client = container.get_blob_client(blob_name)
            blob_data = blob_client.download_blob().readall()
            
            # Extract
            content = await extract_text(blob_data)
            if not content or len(content) < 50:
                print(f"   ⚠️  No content ({len(content)} chars)")
                skipped += 1
                continue
            
            # Embed
            embedding = await generate_embedding(content, openai_client)
            if not embedding:
                print("   ⚠️  No embedding")
                error += 1
                continue
            
            # Update index
            blob_url = f"https://{blob_service.account_name}.blob.core.windows.net/dtce-documents/{blob_name}"
            doc_id = hashlib.md5(blob_url.encode()).hexdigest()
            
            # Extract project name
            project = ""
            for part in blob_name.split('/'):
                if part.startswith('219') or part.startswith('220'):
                    project = part
                    break
            
            document = {
                "id": doc_id,
                "filename": os.path.basename(blob_name),
                "content": content,
                "content_vector": embedding,
                "blob_url": blob_url,
                "folder": os.path.dirname(blob_name),
                "project_name": project if project else "Company Documents"
            }
            
            search_client.merge_or_upload_documents([document])
            print(f"   ✅ {len(content):,} chars")
            success += 1
            
        except Exception as e:
            print(f"   ❌ {str(e)[:100]}")
            error += 1
    
    print("\n" + "=" * 80)
    print(f"\n📊 COMPLETE: ✅ {success} updated | ⚠️  {skipped} skipped | ❌ {error} errors")
    print(f"💡 All updates used merge_or_upload - no documents were deleted!")

if __name__ == "__main__":
    asyncio.run(process_documents())
