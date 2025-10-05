"""Quick update: Just process priority policy documents"""
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

# Priority policy documents to update
PRIORITY_DOCUMENTS = [
    "DTCE Workplace Essentials/Health & Safety/01_Policy/Health & Safety Policy.pdf",
    "DTCE Workplace Essentials/Health & Safety/01_Policy/Wellbeing Policy.docx",
    "DTCE Workplace Essentials/Employment & Onboarding/Employment Policy/Formal Disciplinary Process.pdf",
]

async def extract_text_from_blob_bytes(blob_data: bytes) -> str:
    """Extract text from PDF/DOCX bytes"""
    try:
        credential = AzureKeyCredential(settings.azure_form_recognizer_key)
        client = DocumentAnalysisClient(
            endpoint=settings.azure_form_recognizer_endpoint,
            credential=credential
        )
        
        poller = client.begin_analyze_document("prebuilt-document", blob_data)
        result = poller.result()
        
        content = ""
        for page in result.pages:
            for line in page.lines:
                content += line.content + "\n"
        
        return content.strip()
    except Exception as e:
        print(f"      ❌ Error: {str(e)[:200]}")
        return ""

async def generate_embedding(text: str, openai_client) -> list:
    """Generate embedding"""
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000]
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"      ❌ Error: {str(e)[:200]}")
        return None

async def update_priority_documents():
    print("\n⚡ QUICK UPDATE: Priority Policy Documents\n")
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
    
    success_count = 0
    error_count = 0
    
    for i, blob_name in enumerate(PRIORITY_DOCUMENTS, 1):
        print(f"\n⭐ [{i}/{len(PRIORITY_DOCUMENTS)}] {os.path.basename(blob_name)}")
        print(f"      Path: {blob_name}")
        
        try:
            # Download
            blob_client = container_client.get_blob_client(blob_name)
            print("      📥 Downloading...")
            blob_data = blob_client.download_blob().readall()
            print(f"      ✅ Downloaded {len(blob_data):,} bytes")
            
            # Extract text
            print("      📄 Extracting text...")
            content = await extract_text_from_blob_bytes(blob_data)
            
            if not content or len(content) < 50:
                print(f"      ⚠️  Insufficient content ({len(content)} chars) - skipping")
                error_count += 1
                continue
            
            print(f"      ✅ Extracted {len(content):,} characters")
            
            # Generate embedding
            print("      🧠 Generating embedding...")
            embedding = await generate_embedding(content, openai_client)
            
            if not embedding:
                print("      ⚠️  Failed to generate embedding")
                error_count += 1
                continue
            
            print(f"      ✅ Generated embedding ({len(embedding)} dims)")
            
            # Create blob URL
            blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/dtce-documents/{blob_name}"
            
            # Create document
            doc_id = hashlib.md5(blob_url.encode()).hexdigest()
            document = {
                "id": doc_id,
                "filename": os.path.basename(blob_name),
                "content": content,
                "content_vector": embedding,
                "blob_url": blob_url,
                "folder": os.path.dirname(blob_name),
                "project_name": "Company Documents"
            }
            
            # Update in search index
            print("      💾 Updating search index...")
            result = search_client.merge_or_upload_documents([document])
            print(f"      ✅ UPDATED!")
            success_count += 1
            
        except Exception as e:
            print(f"      ❌ Error: {str(e)[:200]}")
            error_count += 1
    
    print("\n" + "=" * 80)
    print(f"\n📊 QUICK UPDATE COMPLETE")
    print(f"   ✅ Successfully updated: {success_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"\n   💡 Priority policy documents are now updated with full content!")

if __name__ == "__main__":
    asyncio.run(update_priority_documents())
