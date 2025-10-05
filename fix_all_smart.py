"""Fix ALL documents by folder-by-folder scanning to avoid list_blobs timeout"""
import asyncio
import os
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from openai import AsyncAzureOpenAI
import sys
import hashlib
from urllib.parse import unquote
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings
from dotenv import load_dotenv

load_dotenv()
settings = get_settings()

TEXT_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf', '.xlsx', '.xls', '.pptx', '.ppt'}
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

async def scan_folder(container, prefix: str, text_docs: list):
    """Scan a specific folder prefix"""
    try:
        count = 0
        for blob in container.list_blobs(name_starts_with=prefix):
            count += 1
            ext = os.path.splitext(blob.name)[1].lower()
            if ext in TEXT_EXTENSIONS:
                if not any(skip in blob.name.lower() for skip in SKIP_FOLDERS):
                    text_docs.append(blob.name)
        return count
    except Exception as e:
        print(f"   ⚠️  Error scanning {prefix}: {str(e)[:100]}")
        return 0

async def process_documents():
    print("\n🔄 FIX ALL DOCUMENTS - Folder by Folder Approach\n" + "=" * 80)
    
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
    
    # Scan by common folder prefixes (project folders)
    print("📁 Scanning folders for text documents...")
    text_docs = []
    
    # Common project prefixes
    prefixes = [
        "219", "220", "221", "222",  # Project numbers
        "Company Documents/",
        "Technical Library/",
        "Standards/",
        "Templates/",
        "Policies/",
        "Procedures/"
    ]
    
    for prefix in prefixes:
        count = await scan_folder(container, prefix, text_docs)
        if count > 0:
            print(f"   {prefix}: {count} blobs, {len(text_docs)} text docs so far")
    
    # Remove duplicates
    text_docs = list(set(text_docs))
    print(f"\n✅ Found {len(text_docs)} unique text documents\n")
    
    success = error = skipped = 0
    
    for i, blob_name in enumerate(text_docs, 1):
        print(f"[{i}/{len(text_docs)}] {os.path.basename(blob_name)[:60]}")
        
        try:
            # Check if already has content in index
            blob_url = f"https://{blob_service.account_name}.blob.core.windows.net/dtce-documents/{blob_name}"
            doc_id = hashlib.md5(blob_url.encode()).hexdigest()
            
            # Check current content
            try:
                existing = search_client.get_document(key=doc_id)
                current_content = existing.get('content', '')
                if len(current_content) > 200:  # Has real content
                    print(f"   ⏭️  Already has {len(current_content):,} chars, skipping")
                    skipped += 1
                    continue
            except:
                pass  # Document not in index yet
            
            # Download and extract
            blob_client = container.get_blob_client(blob_name)
            blob_data = blob_client.download_blob().readall()
            
            content = await extract_text(blob_data)
            if not content or len(content) < 50:
                print(f"   ⚠️  No content ({len(content)} chars)")
                skipped += 1
                continue
            
            # Generate embedding
            embedding = await generate_embedding(content, openai_client)
            if not embedding:
                print("   ⚠️  No embedding")
                error += 1
                continue
            
            # Extract project name
            project = ""
            for part in blob_name.split('/'):
                if part.startswith('219') or part.startswith('220'):
                    project = part
                    break
            
            # Update index
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
            
            # Throttle
            if i % 10 == 0:
                await asyncio.sleep(1)
            
        except Exception as e:
            print(f"   ❌ {str(e)[:100]}")
            error += 1
    
    print("\n" + "=" * 80)
    print(f"\n📊 COMPLETE: ✅ {success} | ⏭️  {skipped} | ❌ {error}")

if __name__ == "__main__":
    asyncio.run(process_documents())
