"""Update specific important documents - avoid the blob listing issue"""
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

# Specific important documents to update (skip the broken blob listing)
IMPORTANT_DOCS = [
    "DTCE Workplace Essentials/Health & Safety/01_Policy/Health & Safety Policy.pdf",
    "DTCE Workplace Essentials/Health & Safety/01_Policy/Wellbeing Policy.docx",
    "DTCE Workplace Essentials/Employment & Onboarding/Employment Policy/Formal Disciplinary Process.pdf",
    "Engineering/NZS Codes/NZS 3604.pdf",  # If exists
]

async def extract_text(blob_data: bytes) -> str:
    try:
        credential = AzureKeyCredential(settings.azure_form_recognizer_key)
        client = DocumentAnalysisClient(endpoint=settings.azure_form_recognizer_endpoint, credential=credential)
        poller = client.begin_analyze_document("prebuilt-document", blob_data)
        result = poller.result()
        return "\n".join(line.content for page in result.pages for line in page.lines).strip()
    except:
        return ""

async def generate_embedding(text: str, openai_client) -> list:
    try:
        response = await openai_client.embeddings.create(model="text-embedding-3-small", input=text[:8000])
        return response.data[0].embedding
    except:
        return None

async def update_specific_docs():
    print("\n⚡ TARGETED UPDATE: Key Documents Only\n" + "=" * 80)
    
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
    
    success = error = 0
    
    for blob_name in IMPORTANT_DOCS:
        print(f"\n📄 {os.path.basename(blob_name)}")
        
        try:
            blob_client = container.get_blob_client(blob_name)
            blob_data = blob_client.download_blob().readall()
            print(f"   ✅ Downloaded {len(blob_data):,} bytes")
            
            content = await extract_text(blob_data)
            if not content or len(content) < 50:
                print(f"   ⚠️  No content")
                error += 1
                continue
            
            print(f"   ✅ Extracted {len(content):,} chars")
            
            embedding = await generate_embedding(content, openai_client)
            if not embedding:
                print("   ⚠️  No embedding")
                error += 1
                continue
            
            blob_url = f"https://{blob_service.account_name}.blob.core.windows.net/dtce-documents/{blob_name}"
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
            
            search_client.merge_or_upload_documents([document])
            print(f"   ✅ UPDATED in search index")
            success += 1
            
        except Exception as e:
            print(f"   ❌ {str(e)[:100]}")
            error += 1
    
    print("\n" + "=" * 80)
    print(f"\n📊 COMPLETE: ✅ {success} updated | ❌ {error} errors")
    print(f"💡 Used merge_or_upload - no documents deleted!")

if __name__ == "__main__":
    asyncio.run(update_specific_docs())
