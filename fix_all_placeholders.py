"""Fix ALL placeholder documents by querying index and extracting from blob URLs"""
import asyncio
import os
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from openai import AsyncAzureOpenAI
import sys
import hashlib
from urllib.parse import unquote, urlparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.utils.project_parser import extract_project_from_blob_path
from dotenv import load_dotenv

load_dotenv()
settings = get_settings()

TEXT_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf', '.xlsx', '.xls', '.pptx', '.ppt'}

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
    print("\n🔄 FIX ALL PLACEHOLDER DOCUMENTS\n" + "=" * 80)
    
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
    
    # Query for documents that likely have placeholder content
    # Search for "Document:" which is the placeholder pattern
    print("📋 Querying search index for placeholder documents...")
    placeholder_docs = []
    skip = 0
    batch_size = 1000
    max_results = 10000  # Limit to first 10k placeholders
    
    while skip < max_results:
        results = list(search_client.search(
            search_text="Document:",
            select=["id", "filename", "content", "blob_url"],
            top=batch_size,
            skip=skip
        ))
        
        if not results:
            break
        
        # Filter for actual placeholders (short content + text extensions)
        for doc in results:
            content = doc.get('content', '')
            filename = doc.get('filename', '')
            
            # Check if placeholder (< 300 chars) and is a text document
            if len(content) < 300:
                ext = os.path.splitext(filename)[1].lower()
                if ext in TEXT_EXTENSIONS:
                    blob_url = doc.get('blob_url', '')
                    if blob_url and not filename.endswith('.keep'):
                        placeholder_docs.append(doc)
        
        skip += batch_size
        print(f"   Found {len(placeholder_docs)} placeholder documents so far...")
        
        if len(results) < batch_size:
            break
    
    print(f"📝 Found {len(placeholder_docs)} documents with placeholder content\n")
    
    if len(placeholder_docs) == 0:
        print("🎉 No placeholder documents! All documents have content.")
        return
    
    success = error = skipped = 0
    
    for i, doc_info in enumerate(placeholder_docs, 1):
        filename = doc_info.get('filename', 'Unknown')
        blob_url = doc_info.get('blob_url', '')
        
        print(f"[{i}/{len(placeholder_docs)}] {filename[:60]}")
        
        try:
            # Extract blob name from URL
            parsed = urlparse(blob_url)
            blob_name = unquote(parsed.path.split('/dtce-documents/')[-1])
            
            # Download from blob storage
            blob_client = container.get_blob_client(blob_name)
            blob_data = blob_client.download_blob().readall()
            
            # Extract text
            content = await extract_text(blob_data)
            if not content or len(content) < 50:
                print(f"   ⚠️  No extractable content ({len(content)} chars)")
                skipped += 1
                continue
            
            # Generate embedding
            embedding = await generate_embedding(content, openai_client)
            if not embedding:
                print("   ⚠️  Failed to generate embedding")
                error += 1
                continue
            
            # Extract project name using proper parser
            project_name = extract_project_from_blob_path(blob_name)
            
            # Update document in index
            document = {
                "id": doc_info['id'],
                "filename": filename,
                "content": content,
                "content_vector": embedding,
                "blob_url": blob_url,
                "folder": os.path.dirname(blob_name),
                "project_name": project_name
            }
            
            search_client.merge_or_upload_documents([document])
            print(f"   ✅ Updated with {len(content):,} chars")
            success += 1
            
            # Throttle to avoid rate limits
            if i % 5 == 0:
                await asyncio.sleep(0.5)
            
        except Exception as e:
            error_msg = str(e)
            if "does not exist" in error_msg:
                print(f"   ⚠️  Blob no longer exists, skipping")
                skipped += 1
            else:
                print(f"   ❌ Error: {error_msg[:100]}")
                error += 1
    
    print("\n" + "=" * 80)
    print(f"\n📊 COMPLETE:")
    print(f"   ✅ {success} documents updated")
    print(f"   ⚠️  {skipped} documents skipped")
    print(f"   ❌ {error} errors")
    print(f"\n💡 All updates used merge_or_upload - no documents were deleted!")

if __name__ == "__main__":
    asyncio.run(process_documents())
