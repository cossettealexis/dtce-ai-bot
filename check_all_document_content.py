"""Check ALL documents in the index for placeholder/minimal content"""
import asyncio
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings

load_dotenv()
settings = get_settings()

async def check_all_documents():
    # Initialize search client
    endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    search_client = SearchClient(
        endpoint=endpoint,
        index_name="dtce-documents-index",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    print("\n=== CHECKING ALL DOCUMENTS FOR PLACEHOLDER CONTENT ===\n")
    
    # Get ALL documents
    results = search_client.search(
        search_text="*",
        select=["filename", "content", "blob_url"],
        top=1000  # Get all documents
    )
    
    placeholder_docs = []
    good_docs = []
    
    for doc in results:
        filename = doc.get('filename', 'N/A')
        content = doc.get('content', '')
        content_length = len(content)
        blob_url = doc.get('blob_url', 'N/A')
        
        # Check if content is just "Document: [filename]" placeholder
        is_placeholder = (
            content_length < 100 and 
            content.startswith('Document: ')
        )
        
        if is_placeholder:
            placeholder_docs.append({
                'filename': filename,
                'content': content,
                'length': content_length,
                'blob_url': blob_url
            })
        else:
            good_docs.append({
                'filename': filename,
                'length': content_length
            })
    
    print(f"\n📊 SUMMARY:")
    print(f"Total documents: {len(placeholder_docs) + len(good_docs)}")
    print(f"✅ Good documents (with real content): {len(good_docs)}")
    print(f"❌ Placeholder documents (need reindexing): {len(placeholder_docs)}")
    
    print(f"\n\n❌ DOCUMENTS THAT NEED REINDEXING ({len(placeholder_docs)}):")
    print("=" * 100)
    
    for i, doc in enumerate(placeholder_docs, 1):
        print(f"\n{i}. {doc['filename']}")
        print(f"   Content Length: {doc['length']} chars")
        print(f"   Content: {doc['content']}")
        print(f"   Blob URL: {doc['blob_url']}")
    
    print(f"\n\n✅ SAMPLE OF GOOD DOCUMENTS (first 10):")
    print("=" * 100)
    for i, doc in enumerate(good_docs[:10], 1):
        print(f"{i}. {doc['filename']} - {doc['length']} chars")
    
    # Save list of files to reindex
    if placeholder_docs:
        with open('files_to_reindex.txt', 'w') as f:
            for doc in placeholder_docs:
                f.write(f"{doc['blob_url']}\n")
        print(f"\n\n💾 Saved {len(placeholder_docs)} blob URLs to 'files_to_reindex.txt'")

if __name__ == "__main__":
    asyncio.run(check_all_documents())
