#!/usr/bin/env python3
"""
PDF-only reindexing script - optimized for PDF files
Run this in parallel with other file type scripts
"""

import os
import sys
import asyncio
import io
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import re
from datetime import datetime, timezone
import time
import PyPDF2
from openai import AsyncAzureOpenAI

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import PyMuPDF
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Load environment variables
load_dotenv()

# Configuration
MAX_PAGES_PER_PDF = 10  # Speed limit
MAX_CHARS_PER_PAGE = 2000  # Content limit
PDF_TIMEOUT = 15  # Max seconds per PDF

def fast_extract_pdf_content(blob_data: bytes, filename: str) -> str:
    """Ultra-fast PDF extraction optimized for speed."""
    try:
        # Skip huge files
        size_mb = len(blob_data) / (1024 * 1024)
        if size_mb > 100:
            return f"Large PDF file ({size_mb:.1f}MB - content extraction skipped for performance)"
        
        print(f"    📄 Extracting PDF content ({size_mb:.1f}MB)...")
        
        # Method 1: Try PyMuPDF (fastest but can be problematic)
        if PYMUPDF_AVAILABLE:
            try:
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("PDF timeout")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(PDF_TIMEOUT)
                
                try:
                    # Suppress PyMuPDF errors
                    with open(os.devnull, 'w') as devnull:
                        old_stderr = sys.stderr
                        sys.stderr = devnull
                        
                        doc = fitz.open(stream=blob_data, filetype="pdf")
                        text_content = ""
                        pages_processed = 0
                        
                        max_pages = min(MAX_PAGES_PER_PDF, len(doc))
                        
                        for page_num in range(max_pages):
                            try:
                                page = doc[page_num]
                                page_text = page.get_text()
                                
                                if page_text and page_text.strip():
                                    clean_text = page_text.strip()[:MAX_CHARS_PER_PAGE]
                                    text_content += f"\\n--- Page {page_num + 1} ---\\n{clean_text}"
                                    pages_processed += 1
                                    
                                    if len(text_content) > 8000:  # Stop if enough content
                                        break
                            except:
                                continue
                        
                        doc.close()
                        sys.stderr = old_stderr
                        
                        if pages_processed > 0:
                            print(f"    ✅ PyMuPDF: {pages_processed} pages, {len(text_content)} chars")
                            return text_content.strip()
                        
                finally:
                    signal.alarm(0)
                    
            except (TimeoutError, Exception) as e:
                print(f"    ⚠️  PyMuPDF failed: {str(e)[:50]}")
        
        # Method 2: PyPDF2 fallback (more reliable)
        print(f"    📄 Trying PyPDF2...")
        pdf_stream = io.BytesIO(blob_data)
        pdf_reader = PyPDF2.PdfReader(pdf_stream)
        
        # Handle encryption
        if pdf_reader.is_encrypted:
            try:
                if not pdf_reader.decrypt(""):
                    return "Encrypted PDF file (password protected)"
            except:
                return "Encrypted PDF file (cannot decrypt)"
        
        text_content = ""
        pages_processed = 0
        max_pages = min(MAX_PAGES_PER_PDF, len(pdf_reader.pages))
        
        for page_num in range(max_pages):
            try:
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                
                if page_text and page_text.strip():
                    clean_text = page_text.strip()[:MAX_CHARS_PER_PAGE]
                    text_content += f"\\n--- Page {page_num + 1} ---\\n{clean_text}"
                    pages_processed += 1
                    
                    if len(text_content) > 8000:
                        break
            except Exception as e:
                continue
        
        if pages_processed > 0:
            print(f"    ✅ PyPDF2: {pages_processed} pages, {len(text_content)} chars")
            return text_content.strip()
        else:
            return "PDF file (no extractable text - may be image-based or corrupted)"
            
    except Exception as e:
        return f"PDF file (extraction failed: {str(e)[:100]})"

def document_needs_update(blob, existing_docs: dict) -> bool:
    """Check if PDF needs updating."""
    document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
    document_id = re.sub(r'_+', '_', document_id).strip('_')
    
    if document_id not in existing_docs:
        return True
    
    existing_doc = existing_docs[document_id]
    existing_content = existing_doc.get('content', '')
    
    # Update if content is bad
    if (not existing_content or 
        len(existing_content) < 100 or
        'no extractable text' in existing_content.lower() or
        'extraction failed' in existing_content.lower() or
        existing_content.startswith('PDF file (')):
        return True
    
    # Update if blob is newer
    try:
        existing_modified = existing_doc.get('last_modified', '')
        if existing_modified and blob.last_modified:
            existing_time = datetime.fromisoformat(existing_modified.replace('Z', '+00:00'))
            if blob.last_modified.replace(tzinfo=timezone.utc) > existing_time:
                return True
    except:
        pass
    
    return False

async def generate_embeddings(openai_client: AsyncAzureOpenAI, text: str) -> list:
    """Generate embeddings with truncation."""
    try:
        truncated_text = text[:4000]  # Fast truncation
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=truncated_text
        )
        return response.data[0].embedding
    except:
        return []

async def process_pdfs():
    """Process only PDF files."""
    print("📄 PDF-ONLY REINDEXING SCRIPT")
    print("=" * 50)
    
    # Initialize clients
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    search_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "dtce-documents-index")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "dtce-documents")
    
    storage_client = BlobServiceClient.from_connection_string(connection_string)
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(search_key)
    )
    
    openai_client = AsyncAzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-15-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    
    container_client = storage_client.get_container_client(container_name)
    
    # Get existing documents
    print("📋 Loading existing PDFs from search index...")
    existing_docs = {}
    try:
        results = search_client.search("*", select=["id", "last_modified", "content"], top=10000)
        for doc in results:
            if doc.get('id'):
                existing_docs[doc['id']] = {
                    'last_modified': doc.get('last_modified'),
                    'content': doc.get('content', '')
                }
        print(f"✅ Loaded {len(existing_docs)} existing documents")
    except Exception as e:
        print(f"⚠️ Could not load existing docs: {e}")
    
    # Find PDF files that need updating
    print("🔍 Scanning for PDF files...")
    pdf_blobs = []
    
    # Projects PDFs first
    try:
        for blob in container_client.list_blobs(name_starts_with="Projects/"):
            if blob.name.lower().endswith('.pdf'):
                if document_needs_update(blob, existing_docs):
                    pdf_blobs.append(blob)
    except Exception as e:
        print(f"⚠️ Error scanning Projects PDFs: {e}")
    
    # Other PDFs
    try:
        for blob in container_client.list_blobs():
            if blob.name.lower().endswith('.pdf') and not blob.name.startswith("Projects/"):
                if document_needs_update(blob, existing_docs):
                    pdf_blobs.append(blob)
    except Exception as e:
        print(f"⚠️ Error scanning other PDFs: {e}")
    
    total_pdfs = len(pdf_blobs)
    print(f"📊 Found {total_pdfs} PDF files to process")
    
    if total_pdfs == 0:
        print("✅ All PDFs are up to date!")
        return
    
    # Process PDFs
    processed = 0
    errors = 0
    start_time = time.time()
    
    for i, blob in enumerate(pdf_blobs, 1):
        try:
            print(f"\\n[{i}/{total_pdfs}] Processing: {blob.name}")
            
            # Download blob
            blob_client = storage_client.get_blob_client(container=container_name, blob=blob.name)
            blob_data = blob_client.download_blob().readall()
            
            # Extract content
            content = fast_extract_pdf_content(blob_data, blob.name)
            
            # Extract metadata
            folder_path = blob.name.rsplit('/', 1)[0] if '/' in blob.name else ''
            filename = os.path.basename(blob.name)
            
            # Project info
            project_name = ""
            year = None
            if folder_path and '/Projects/' in f"/{folder_path}/":
                parts = folder_path.split('/')
                if 'Projects' in parts:
                    idx = parts.index('Projects')
                    if idx + 1 < len(parts):
                        project_name = parts[idx + 1]
                    if idx + 2 < len(parts):
                        try:
                            year = int(parts[idx + 2])
                        except:
                            pass
            
            # Generate embeddings
            content_vector = await generate_embeddings(openai_client, content)
            
            # Create document
            document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
            document_id = re.sub(r'_+', '_', document_id).strip('_')
            
            search_document = {
                "id": document_id,
                "blob_name": blob.name,
                "blob_url": blob_client.url,
                "filename": filename,
                "content_type": "application/pdf",
                "folder": folder_path,
                "size": blob.size or 0,
                "content": content,
                "content_vector": content_vector,
                "last_modified": blob.last_modified.isoformat(),
                "created_date": blob.creation_time.isoformat() if blob.creation_time else blob.last_modified.isoformat(),
                "project_name": project_name,
                "year": year
            }
            
            # Upload to search
            result = search_client.upload_documents([search_document])
            if result[0].succeeded:
                processed += 1
                print(f"    ✅ Indexed successfully")
            else:
                errors += 1
                print(f"    ❌ Index failed: {result[0].error_message}")
            
            # Progress
            if i % 10 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed * 60
                remaining = total_pdfs - i
                eta = remaining / rate if rate > 0 else 0
                print(f"    📊 Progress: {processed}/{total_pdfs}, {rate:.1f} PDFs/min, ETA: {eta:.1f}min")
                
        except Exception as e:
            errors += 1
            print(f"    ❌ Error: {str(e)[:100]}")
    
    # Summary
    elapsed = time.time() - start_time
    rate = processed / elapsed * 60 if elapsed > 0 else 0
    
    print(f"\\n🎉 PDF PROCESSING COMPLETE!")
    print(f"✅ Processed: {processed}")
    print(f"❌ Errors: {errors}")
    print(f"⏱️ Time: {elapsed/60:.1f} minutes")
    print(f"📈 Rate: {rate:.1f} PDFs/minute")

if __name__ == "__main__":
    asyncio.run(process_pdfs())
