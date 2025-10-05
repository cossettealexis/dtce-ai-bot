"""Test updating just the Wellbeing Policy"""
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

async def extract_text_from_blob_bytes(blob_data: bytes) -> str:
    """Extract text from PDF/DOCX bytes using Azure Form Recognizer"""
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
        print(f"   ❌ Error: {str(e)}")
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
        print(f"   ❌ Error: {str(e)}")
        return None

async def test_wellbeing_update():
    print("\n🧪 TEST: Updating Wellbeing Policy in Search Index\n")
    print("=" * 80)
    
    # Initialize clients
    blob_service_client = BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )
    
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
    
    # Process Wellbeing Policy.pdf
    blob_name = "DTCE Workplace Essentials/Health & Safety/01_Policy/Wellbeing Policy.pdf"
    
    print(f"📄 Processing: {blob_name}\n")
    
    try:
        # Download
        container_client = blob_service_client.get_container_client("dtce-documents")
        blob_client = container_client.get_blob_client(blob_name)
        
        print("   📥 Downloading blob...")
        blob_data = blob_client.download_blob().readall()
        print(f"   ✅ Downloaded {len(blob_data):,} bytes")
        
        # Extract text
        print("   📄 Extracting text with Form Recognizer...")
        content = await extract_text_from_blob_bytes(blob_data)
        
        if content:
            print(f"   ✅ Extracted {len(content):,} characters")
            print(f"\n   📝 First 500 characters:")
            print(f"   {content[:500]}\n")
            
            # Generate embedding
            print("   🧠 Generating embedding...")
            embedding = await generate_embedding(content, openai_client)
            
            if embedding:
                print(f"   ✅ Generated embedding ({len(embedding)} dimensions)")
                
                # Create blob URL
                blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/dtce-documents/{blob_name}"
                
                # Create document
                doc_id = hashlib.md5(blob_url.encode()).hexdigest()
                document = {
                    "id": doc_id,
                    "filename": "Wellbeing Policy.pdf",
                    "content": content,
                    "content_vector": embedding,
                    "blob_url": blob_url,
                    "folder": "DTCE Workplace Essentials/Health & Safety/01_Policy",
                    "project_name": "Company Documents"
                }
                
                # Update in search index
                print("   💾 Updating search index...")
                result = search_client.merge_or_upload_documents([document])
                print(f"   ✅ SUCCESSFULLY UPDATED!")
                print(f"   📋 Document ID: {doc_id}")
                
                print("\n" + "=" * 80)
                print("✅ TEST PASSED - Wellbeing Policy updated in search index!")
                
        else:
            print("   ❌ No content extracted")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_wellbeing_update())
