"""Fast update: Process key folders containing policy and standards documents"""
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

# Key folders to process (most important documents)
KEY_FOLDERS = [
    "DTCE Workplace Essentials/Health & Safety/01_Policy/",
    "DTCE Workplace Essentials/Employment & Onboarding/",
    "Engineering/Standards/",
    "Engineering/NZS Standards/",
]

TEXT_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.md'}

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
        print(f"      Extract error: {str(e)[:100]}")
        return ""

async def generate_embedding(text: str, openai_client) -> list:
    """Generate embedding"""
    try:
        response = await openai_client.embeddings.create(model="text-embedding-3-small", input=text[:8000])
        return response.data[0].embedding
    except Exception as e:
        print(f"      Embed error: {str(e)[:100]}")
        return None

async def process_key_folders():
    print("\n⚡ FAST UPDATE: Key Policy & Standards Folders\n" + "=" * 80)
    
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
    
    total_success = total_error = total_skipped = 0
    
    for folder in KEY_FOLDERS:
        print(f"\n📁 Processing: {folder}")
        print("-" * 80)
        
        try:
            blobs = list(container.list_blobs(name_starts_with=folder))
            text_docs = [
                b for b in blobs 
                if os.path.splitext(b.name)[1].lower() in TEXT_EXTENSIONS 
                and 'superseded' not in b.name.lower()
                and 'draft' not in b.name.lower()
                and not b.name.endswith('.keep')
            ]
            
            print(f"   Found {len(text_docs)} documents")
            
            for i, blob in enumerate(text_docs, 1):
                filename = os.path.basename(blob.name)
                print(f"   [{i}/{len(text_docs)}] {filename[:60]}")
                
                try:
                    # Download
                    blob_client = container.get_blob_client(blob.name)
                    blob_data = blob_client.download_blob().readall()
                    print(f"      📥 {len(blob_data):,} bytes")
                    
                    # Extract
                    content = await extract_text(blob_data)
                    if not content or len(content) < 50:
                        print(f"      ⚠️  No content extracted")
                        total_skipped += 1
                        continue
                    
                    print(f"      📄 {len(content):,} chars extracted")
                    
                    # Embed
                    embedding = await generate_embedding(content, openai_client)
                    if not embedding:
                        print("      ⚠️  No embedding")
                        total_error += 1
                        continue
                    
                    # Update index
                    blob_url = f"https://{blob_service.account_name}.blob.core.windows.net/dtce-documents/{blob.name}"
                    doc_id = hashlib.md5(blob_url.encode()).hexdigest()
                    
                    document = {
                        "id": doc_id,
                        "filename": filename,
                        "content": content,
                        "content_vector": embedding,
                        "blob_url": blob_url,
                        "folder": os.path.dirname(blob.name),
                        "project_name": "Company Documents"
                    }
                    
                    search_client.merge_or_upload_documents([document])
                    print(f"      ✅ Updated in search index")
                    total_success += 1
                    
                except Exception as e:
                    print(f"      ❌ Error: {str(e)[:100]}")
                    total_error += 1
                    
        except Exception as e:
            print(f"   ❌ Folder error: {str(e)[:100]}")
    
    print("\n" + "=" * 80)
    print(f"\n📊 COMPLETE:")
    print(f"   ✅ Successfully updated: {total_success}")
    print(f"   ⚠️  Skipped (no content): {total_skipped}")
    print(f"   ❌ Errors: {total_error}")
    print(f"\n   💡 All updates used merge_or_upload - no documents were deleted!")

if __name__ == "__main__":
    asyncio.run(process_key_folders())
