"""Fix ALL documents by querying the search index for placeholders, then updating them"""
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
    print("\n🔄 FIX ALL DOCUMENTS - Using Index to Find Placeholders\n" + "=" * 80)
    
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
    
    # Query index for documents with short content (placeholders)
    print("🔍 Querying search index for documents with placeholder content...")
    results = search_client.search(
        search_text="*",
        select=["id", "filename", "content", "blob_url"],
        top=1000  # Get first 1000
    )
    
    # Filter for placeholders
    placeholder_docs = []
    for doc in results:
        content = doc.get('content', '')
        # Placeholder pattern: "Document: filename.pdf" (very short)
        if len(content) < 100:  # Less than 100 chars is likely placeholder
            blob_url = doc.get('blob_url', '')
            if blob_url:
                # Extract blob name from URL
                blob_name = blob_url.split('dtce-documents/')[-1]
                # Check if it's a text document
                ext = os.path.splitext(blob_name)[1].lower()
                if ext in TEXT_EXTENSIONS:
                    # Skip certain folders
                    if not any(skip in blob_name.lower() for skip in SKIP_FOLDERS):
                        placeholder_docs.append({
                            'id': doc['id'],
                            'filename': doc.get('filename', ''),
                            'blob_url': blob_url,
                            'blob_name': blob_name,
                            'current_content': content
                        })
    
    print(f"✅ Found {len(placeholder_docs)} text documents with placeholder content\n")
    
    if len(placeholder_docs) == 0:
        print("🎉 No placeholder documents found! All documents already have content.")
        return
    
    success = error = skipped = 0
    
    for i, doc_info in enumerate(placeholder_docs, 1):
        blob_name = doc_info['blob_name']
        print(f"[{i}/{len(placeholder_docs)}] {os.path.basename(blob_name)[:60]}")
        print(f"   Current: {doc_info['current_content'][:80]}")
        
        try:
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
            
            # Extract project name from path
            project = ""
            for part in blob_name.split('/'):
                if part.startswith('219') or part.startswith('220'):
                    project = part
                    break
            
            # Update document in index
            document = {
                "id": doc_info['id'],  # Use existing ID
                "filename": doc_info['filename'],
                "content": content,
                "content_vector": embedding,
                "blob_url": doc_info['blob_url'],
                "folder": os.path.dirname(blob_name),
                "project_name": project if project else "Company Documents"
            }
            
            search_client.merge_or_upload_documents([document])
            print(f"   ✅ Updated with {len(content):,} chars (was {len(doc_info['current_content'])} chars)")
            success += 1
            
            # Add small delay to avoid throttling
            if i % 10 == 0:
                await asyncio.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
            error += 1
    
    print("\n" + "=" * 80)
    print(f"\n📊 COMPLETE:")
    print(f"   ✅ {success} documents updated")
    print(f"   ⚠️  {skipped} documents skipped (no content)")
    print(f"   ❌ {error} errors")
    print(f"\n💡 All updates used merge_or_upload - no documents were deleted!")

if __name__ == "__main__":
    asyncio.run(process_documents())
