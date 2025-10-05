"""Test reindexing just the Wellbeing Policy files"""
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
        
        print(f"      Container: {container_name}")
        print(f"      Blob: {blob_name}")
        
        # Download blob
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        blob_data = blob_client.download_blob().readall()
        print(f"      Downloaded {len(blob_data)} bytes")
        
        # Initialize Form Recognizer client
        credential = AzureKeyCredential(settings.azure_form_recognizer_key)
        client = DocumentAnalysisClient(
            endpoint=settings.azure_form_recognizer_endpoint,
            credential=credential
        )
        
        # Analyze document from bytes
        print("      Analyzing with Form Recognizer...")
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

async def test_wellbeing_reindex():
    print("\n🧪 TESTING WELLBEING POLICY REINDEXING\n")
    print("=" * 80)
    
    # Just the wellbeing policy URLs
    wellbeing_docs = [
        ("https://dtceaistorage.blob.core.windows.net/dtce-documents/DTCE%20Workplace%20Essentials/Health%20%26%20Safety/01_Policy/Wellbeing%20Policy.pdf", "Wellbeing Policy.pdf"),
        ("https://dtceaistorage.blob.core.windows.net/dtce-documents/DTCE%20Workplace%20Essentials/Health%20%26%20Safety/01_Policy/Wellbeing%20Policy.docx", "Wellbeing Policy.docx"),
    ]
    
    for blob_url, filename in wellbeing_docs:
        print(f"\n📄 {filename}")
        print(f"   URL: {blob_url}")
        
        content = await extract_text_from_blob(blob_url)
        
        if content:
            print(f"\n   ✅ Extracted {len(content)} characters")
            print(f"   📝 First 500 chars:")
            print(f"   {content[:500]}")
        else:
            print("   ❌ Failed to extract content")

if __name__ == "__main__":
    asyncio.run(test_wellbeing_reindex())
