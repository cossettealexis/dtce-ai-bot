"""Check specific project 225 document content"""
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings

load_dotenv()
settings = get_settings()

def check_doc():
    search_client = SearchClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        index_name="dtce-documents-index",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    print("\n🔍 Checking Project 225 Document Content\n" + "=" * 80)
    
    # Search for the specific file
    results = search_client.search(
        search_text="Optimized Advertising Strategy",
        select=["filename", "content", "folder", "project_name"],
        top=5
    )
    
    for doc in results:
        print(f"\nFile: {doc.get('filename')}")
        print(f"Folder: {doc.get('folder')}")
        print(f"Project: {doc.get('project_name')}")
        content = doc.get('content', '')
        print(f"Content length: {len(content)} chars")
        print(f"\nContent preview:\n{content[:500]}")
        print("\n" + "=" * 80)

if __name__ == "__main__":
    check_doc()
