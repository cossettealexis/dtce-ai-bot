"""Check what documents exist for project 225"""
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings

load_dotenv()
settings = get_settings()

def check_project():
    search_client = SearchClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        index_name="dtce-documents-index",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    print("\n🔍 Searching for Project 225 Documents\n" + "=" * 80)
    
    # Search for project 225
    results = search_client.search(
        search_text="225",
        select=["id", "filename", "content", "project_name", "folder"],
        top=20
    )
    
    found = 0
    for doc in results:
        folder = doc.get('folder', '') or ''
        project_name = doc.get('project_name', '') or ''
        
        # Check if it's actually project 225
        if '225' in folder or '225' in project_name:
            found += 1
            content = doc.get('content', '')
            print(f"\n[{found}] {doc.get('filename', 'Unknown')}")
            print(f"    Project: {project_name}")
            print(f"    Folder: {folder}")
            print(f"    Content length: {len(content)} chars")
            print(f"    Content preview: {content[:200]}")
    
    if found == 0:
        print("\n❌ No documents found for project 225")
        print("\nSearching by folder pattern '225'...")
        
        # Try broader search
        results = search_client.search(
            search_text="*",
            filter="search.ismatch('225*', 'folder')",
            select=["filename", "folder", "project_name"],
            top=10
        )
        
        for doc in results:
            print(f"  - {doc.get('filename')} in {doc.get('folder')}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    check_project()
