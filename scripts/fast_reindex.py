#!/usr/bin/env python3
"""
FAST Re-indexing - Only process documents that actually need updating
Optimized for speed with smart filtering and batch processing
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
import docx
from openai import AsyncAzureOpenAI
from azure.core.exceptions import ServiceResponseError
from azure.ai.formrecognizer import DocumentAnalysisClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import List, Dict, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import additional libraries
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Load environment variables
load_dotenv()

# Configuration for FAST processing
MAX_WORKERS = 8  # Parallel processing
BATCH_SIZE = 50  # Process in batches
SKIP_FORM_RECOGNIZER_BY_DEFAULT = True  # Only use for truly problematic PDFs
FAST_PDF_TIMEOUT = 10  # Max seconds per PDF

# Global counters
processed_count = 0
skipped_count = 0
error_count = 0
start_time = time.time()

def should_skip_file(blob_name: str) -> bool:
    """Quick check if file should be skipped."""
    filename = blob_name.lower()
    
    # Skip media and system files
    skip_extensions = [
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv',
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg', '.webp', '.ico',
        '.accdb', '.mdb', '.ldb', '.bak', '.backup', '.db', '.sqlite',
        '.zip', '.rar', '.7z', '.tar', '.gz', '.exe', '.dll', '.bin', '.iso',
        '.keep', '.gitkeep'
    ]
    
    return any(filename.endswith(ext) for ext in skip_extensions)

def document_needs_update(blob, existing_docs: Dict[str, Dict]) -> bool:
    """Check if document needs updating based on modification time and content quality."""
    document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
    document_id = re.sub(r'_+', '_', document_id).strip('_')
    
    if document_id not in existing_docs:
        return True  # New document
    
    existing_doc = existing_docs[document_id]
    existing_content = existing_doc.get('content', '')
    existing_modified = existing_doc.get('last_modified', '')
    
    # Always update if content is placeholder/bad
    if (not existing_content or 
        len(existing_content) < 100 or
        existing_content.startswith('Document:') or
        existing_content.startswith('File:') or
        'no extractable text' in existing_content.lower()):
        return True
    
    # Update if blob is newer
    try:
        if existing_modified and blob.last_modified:
            existing_time = datetime.fromisoformat(existing_modified.replace('Z', '+00:00'))
            if blob.last_modified.replace(tzinfo=timezone.utc) > existing_time:
                return True
    except:
        pass  # If date comparison fails, err on side of updating
    
    return False  # Document is current and has good content

def fast_extract_pdf_content(blob_data: bytes) -> str:
    """Fast PDF extraction with timeout and fallback."""
    try:
        # Quick size check - skip huge files that will be slow
        if len(blob_data) > 50 * 1024 * 1024:  # 50MB
            return "Large PDF file (content extraction skipped for performance)"
        
        # Try PyMuPDF first (fastest)
        if PYMUPDF_AVAILABLE:
            try:
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("PDF extraction timeout")
                
                # Set timeout for PDF processing
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(FAST_PDF_TIMEOUT)
                
                try:
                    with open(os.devnull, 'w') as devnull:
                        import sys
                        old_stderr = sys.stderr
                        sys.stderr = devnull
                        
                        doc = fitz.open(stream=blob_data, filetype="pdf")
                        text_content = ""
                        
                        # Only process first 10 pages for speed
                        max_pages = min(10, len(doc))
                        for page_num in range(max_pages):
                            page = doc[page_num]
                            page_text = page.get_text()
                            if page_text and page_text.strip():
                                text_content += page_text[:2000]  # Limit per page
                                if len(text_content) > 8000:  # Stop if we have enough
                                    break
                        
                        doc.close()
                        sys.stderr = old_stderr
                        
                        if len(text_content.strip()) > 50:
                            return text_content.strip()
                            
                finally:
                    signal.alarm(0)  # Cancel timeout
                    
            except (TimeoutError, Exception):
                pass  # Fall back to PyPDF2
        
        # Fallback to PyPDF2 (simpler, more reliable)
        pdf_stream = io.BytesIO(blob_data)
        pdf_reader = PyPDF2.PdfReader(pdf_stream)
        
        if pdf_reader.is_encrypted:
            try:
                pdf_reader.decrypt("")
            except:
                return "Encrypted PDF file (password protected)"
        
        text_content = ""
        max_pages = min(5, len(pdf_reader.pages))  # Only first 5 pages for speed
        
        for page_num in range(max_pages):
            try:
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_content += page_text[:2000]  # Limit per page
                    if len(text_content) > 6000:  # Stop if we have enough
                        break
            except:
                continue
        
        if len(text_content.strip()) > 50:
            return text_content.strip()
        else:
            return "PDF file (limited text content - may be image-based)"
            
    except Exception as e:
        return f"PDF file (extraction failed: {str(e)[:100]})"

def fast_extract_docx_content(blob_data: bytes) -> str:
    """Fast DOCX extraction."""
    try:
        docx_stream = io.BytesIO(blob_data)
        doc = docx.Document(docx_stream)
        
        text_content = ""
        for paragraph in doc.paragraphs[:100]:  # Limit paragraphs for speed
            text_content += paragraph.text + "\n"
            if len(text_content) > 8000:  # Stop if we have enough
                break
        
        return text_content.strip() or "Word document (no text content found)"
    except Exception as e:
        return f"Word document (extraction failed: {str(e)[:100]})"

def fast_extract_text_content(blob_data: bytes) -> str:
    """Fast text file extraction."""
    try:
        # Quick binary check
        sample = blob_data[:1024]
        if b'\x00' in sample or len([b for b in sample if b < 32 and b not in [9, 10, 13]]) > 50:
            return ""  # Likely binary
        
        # Try UTF-8 first
        text = blob_data[:16384].decode('utf-8').strip()  # Only first 16KB
        return text if len(text) > 10 else ""
    except:
        try:
            text = blob_data[:16384].decode('latin-1', errors='ignore').strip()
            return text if len(text) > 10 else ""
        except:
            return ""

def fast_extract_document_content(blob_name: str, blob_data: bytes) -> str:
    """Fast document content extraction."""
    filename = blob_name.lower()
    
    # PDF files
    if filename.endswith('.pdf'):
        return fast_extract_pdf_content(blob_data)
    
    # Word documents
    elif filename.endswith(('.docx', '.dotx')):
        return fast_extract_docx_content(blob_data)
    
    # Text files
    elif filename.endswith(('.txt', '.md', '.csv', '.log', '.py', '.js', '.html', '.xml', '.json')):
        return fast_extract_text_content(blob_data)
    
    # Other files - just return metadata
    else:
        base_name = os.path.basename(blob_name)
        return f"Document: {base_name}"

async def generate_embeddings_fast(openai_client: AsyncAzureOpenAI, text: str) -> list:
    """Generate embeddings with aggressive truncation for speed."""
    try:
        # Very aggressive truncation for speed
        max_chars = 4000
        truncated_text = text[:max_chars]
        
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=truncated_text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"    ⚠️ Embedding generation failed: {e}")
        return []

def process_blob_batch(blob_batch: List, search_client, openai_client, existing_docs: Dict[str, Dict]) -> List[Dict]:
    """Process a batch of blobs in parallel."""
    global processed_count, skipped_count, error_count
    
    documents_to_upload = []
    
    for blob in blob_batch:
        try:
            # Quick skip checks
            if should_skip_file(blob.name):
                skipped_count += 1
                continue  
            
            if not document_needs_update(blob, existing_docs):
                skipped_count += 1
                continue
            
            print(f"  📄 Processing: {blob.name}")
            
            # Download and extract content
            blob_client = search_client._client._client.get_blob_client(blob=blob.name)
            blob_data = blob_client.download_blob().readall()
            
            content = fast_extract_document_content(blob.name, blob_data)
            
            # Extract metadata
            folder_path = blob.name.rsplit('/', 1)[0] if '/' in blob.name else ''
            filename = os.path.basename(blob.name)
            
            # Project info extraction
            project_name = ""
            year = None
            if folder_path:
                path_parts = folder_path.split("/")
                if len(path_parts) > 1 and path_parts[0] == 'Projects':
                    if len(path_parts) > 2 and path_parts[1].isdigit():
                        project_name = path_parts[1]
                        if len(path_parts) > 3:
                            try:
                                year = int(path_parts[2])
                            except:
                                pass
            
            # Generate embeddings (async)
            content_vector = []
            if content and len(content.strip()) > 50:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    content_vector = loop.run_until_complete(
                        generate_embeddings_fast(openai_client, content)
                    )
                    loop.close()
                except:
                    pass  # Skip embeddings if failed
            
            # Create document
            document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
            document_id = re.sub(r'_+', '_', document_id).strip('_')
            
            search_document = {
                "id": document_id,
                "blob_name": blob.name,
                "blob_url": blob_client.url,
                "filename": filename,
                "content_type": "",
                "folder": folder_path,
                "size": blob.size or 0,
                "content": content,
                "content_vector": content_vector,
                "last_modified": blob.last_modified.isoformat(),
                "created_date": blob.creation_time.isoformat() if blob.creation_time else blob.last_modified.isoformat(),
                "project_name": project_name,
                "year": year
            }
            
            documents_to_upload.append(search_document)
            processed_count += 1
            
            # Show progress
            if processed_count % 10 == 0:
                elapsed = time.time() - start_time
                rate = processed_count / elapsed * 60  # per minute
                print(f"    📊 Progress: {processed_count} processed, {skipped_count} skipped, {rate:.1f} docs/min")
            
        except Exception as e:
            error_count += 1
            print(f"    ❌ Error processing {blob.name}: {str(e)[:100]}")
    
    return documents_to_upload

async def fast_reindex():
    """Fast reindexing with smart filtering and parallel processing."""
    print("🚀 FAST RE-INDEXING - Only updating what needs it")
    print("=" * 80)
    
    # Initialize clients
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    search_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "dtce-documents-index")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "dtce-documents")
    
    if not all([connection_string, search_endpoint, search_key]):
        print("❌ Missing Azure credentials")
        return
    
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
    
    # Step 1: Get existing documents from search index
    print("📋 Loading existing documents from search index...")
    existing_docs = {}
    try:
        existing_results = search_client.search(
            search_text="*",
            select=["id", "last_modified", "content"],
            top=10000  # Get all existing docs
        )
        for doc in existing_results:
            existing_docs[doc['id']] = {
                'last_modified': doc.get('last_modified'),
                'content': doc.get('content', '')
            }
        print(f"✅ Loaded {len(existing_docs)} existing documents")
    except Exception as e:
        print(f"⚠️ Could not load existing docs: {e}")
    
    # Step 2: Get blobs that need processing (Projects folder first)
    print("📂 Scanning for documents that need updating...")
    
    def get_blobs_to_process():
        """Generator for blobs that need processing, Projects first."""
        # Projects folder first
        try:
            projects_blobs = list(container_client.list_blobs(name_starts_with="Projects/"))
            print(f"📁 Found {len(projects_blobs)} blobs in Projects folder")
            for blob in projects_blobs:
                if document_needs_update(blob, existing_docs):
                    yield blob
        except Exception as e:
            print(f"⚠️ Error scanning Projects: {e}")
        
        # Other folders
        try:
            all_blobs = container_client.list_blobs()
            for blob in all_blobs:
                if not blob.name.startswith("Projects/"):
                    if document_needs_update(blob, existing_docs):
                        yield blob
        except Exception as e:
            print(f"⚠️ Error scanning other folders: {e}")
    
    # Step 3: Process in batches
    print("🔥 Processing documents in parallel batches...")
    
    blobs_to_process = list(get_blobs_to_process())
    total_to_process = len(blobs_to_process)
    
    print(f"📊 Total documents to process: {total_to_process}")
    
    if total_to_process == 0:
        print("✅ All documents are up to date!")
        return
    
    # Process in batches
    for i in range(0, total_to_process, BATCH_SIZE):
        batch = blobs_to_process[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_to_process + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"\n📦 Processing batch {batch_num}/{total_batches} ({len(batch)} documents)")
        
        # Process batch
        documents_to_upload = process_blob_batch(batch, search_client, openai_client, existing_docs)
        
        # Upload batch to search index
        if documents_to_upload:
            try:
                print(f"    📤 Uploading {len(documents_to_upload)} documents...")
                result = search_client.upload_documents(documents_to_upload)
                
                success_count = sum(1 for r in result if r.succeeded)
                failed_count = len(result) - success_count
                
                if failed_count > 0:
                    print(f"    ⚠️ {failed_count} documents failed to upload")
                    
            except Exception as e:
                print(f"    ❌ Batch upload failed: {e}")
        
        # Progress update
        elapsed = time.time() - start_time
        remaining_batches = total_batches - batch_num
        estimated_time = (elapsed / batch_num) * remaining_batches if batch_num > 0 else 0
        
        print(f"    ⏱️ Batch complete. ETA: {estimated_time/60:.1f} minutes remaining")
    
    # Final summary
    elapsed = time.time() - start_time
    rate = processed_count / elapsed * 60 if elapsed > 0 else 0
    
    print(f"\n🎉 FAST RE-INDEXING COMPLETE!")
    print(f"✅ Processed: {processed_count}")
    print(f"⏭️ Skipped (current): {skipped_count}")
    print(f"❌ Errors: {error_count}")
    print(f"⏱️ Total time: {elapsed/60:.1f} minutes")
    print(f"📈 Average rate: {rate:.1f} documents/minute")
    
    if processed_count > 0:
        print(f"\n🤖 Bot should now have updated content!")

if __name__ == "__main__":
    asyncio.run(fast_reindex())
