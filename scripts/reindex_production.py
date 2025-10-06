#!/usr/bin/env python3
"""
PRODUCTION Re-indexing - Index ALL real documents from Azure Storage directly
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
from datetime import datetime
import time
import PyPDF2
import docx
from openai import AsyncAzureOpenAI
from azure.core.exceptions import ServiceResponseError

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def extract_pdf_content(blob_data: bytes) -> str:
    """Extract text content from PDF blob data."""
    try:
        pdf_stream = io.BytesIO(blob_data)
        pdf_reader = PyPDF2.PdfReader(pdf_stream)
        
        text_content = ""
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                if page_text.strip():
                    text_content += f"\n--- Page {page_num + 1} ---\n{page_text}"
            except Exception as e:
                print(f"  Warning: Could not extract page {page_num + 1}: {e}")
                continue
        
        return text_content.strip()
    except Exception as e:
        print(f"  Error extracting PDF: {e}")
        return ""


def extract_docx_content(blob_data: bytes) -> str:
    """Extract text content from DOCX blob data."""
    try:
        docx_stream = io.BytesIO(blob_data)
        doc = docx.Document(docx_stream)
        
        text_content = ""
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content += paragraph.text + "\n"
        
        return text_content.strip()
    except Exception as e:
        print(f"  Error extracting DOCX: {e}")
        return ""


def extract_text_content(blob_data: bytes) -> str:
    """Extract text content from plain text files."""
    try:
        # Try UTF-8 first
        return blob_data.decode('utf-8').strip()
    except UnicodeDecodeError:
        try:
            # Fallback to latin-1
            return blob_data.decode('latin-1').strip()
        except Exception as e:
            print(f"  Error extracting text: {e}")
            return ""


def extract_document_content(blob_name: str, blob_data: bytes) -> str:
    """Extract content from document based on file extension."""
    filename = blob_name.lower()
    
    if filename.endswith('.pdf'):
        return extract_pdf_content(blob_data)
    elif filename.endswith(('.docx', '.doc')):
        return extract_docx_content(blob_data)
    elif filename.endswith(('.txt', '.md', '.readme')):
        return extract_text_content(blob_data)
    else:
        # For other file types, return metadata description
        return f"File: {os.path.basename(blob_name)} (content extraction not supported for this file type)"


async def generate_embeddings(openai_client: AsyncAzureOpenAI, text: str) -> list:
    """Generate embeddings for the text content."""
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000]  # Limit to avoid token limits
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"  Warning: Could not generate embeddings: {e}")
        return []


# Load environment variables from .env file
load_dotenv()

async def production_reindex():
    """Re-index ALL production documents directly from Azure Storage."""
    print("🚨 PRODUCTION RE-INDEXING - Processing ALL real documents")
    print("=" * 80)
    
    # Get settings from environment variables (same as production)
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    
    # Correctly parse the search service name from the endpoint
    search_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
    search_service_name = ""
    if search_endpoint:
        match = re.search(r"https://(.*?)\.search\.windows\.net", search_endpoint)
        if match:
            search_service_name = match.group(1)

    search_key = os.getenv("AZURE_SEARCH_ADMIN_KEY") or os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "dtce-documents-index")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "dtce-documents")
    
    if not connection_string or not search_key or not search_service_name:
        print("❌ Missing Azure credentials in environment variables")
        print("Set AZURE_STORAGE_CONNECTION_STRING, AZURE_SEARCH_SERVICE_ENDPOINT, and AZURE_SEARCH_ADMIN_KEY")
        return
    
    # Initialize clients
    storage_client = BlobServiceClient.from_connection_string(connection_string)
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(search_key)
    )
    
    # Initialize OpenAI client for embeddings
    openai_client = AsyncAzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-15-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    
    container_client = storage_client.get_container_client(container_name)
    
    # Get an iterator for blobs from production storage
    print(f"📋 Getting blob iterator from container '{container_name}'...")
    try:
        blob_iterator = container_client.list_blobs()
    except Exception as e:
        print(f"❌ Failed to get blob iterator: {e}")
        return

    # Index ALL documents
    print(f"🔥 Indexing production documents...")
    success_count = 0
    error_count = 0
    skipped_count = 0
    total_count = 0
    
    for blob in blob_iterator:
        total_count += 1
        try:
            print(f"[{total_count}] {blob.name}")
            
            # Get blob metadata with retry
            blob_client = storage_client.get_blob_client(container=container_name, blob=blob.name)
            
            metadata = {}
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    blob_properties = blob_client.get_blob_properties()
                    metadata = blob_properties.metadata or {}
                    break
                except (ServiceResponseError, ConnectionResetError) as e:
                    if attempt < max_retries - 1:
                        print(f"  ... network error getting metadata, retrying in 5s ({e})")
                        time.sleep(5)
                    else:
                        raise e

            # Check if document already exists in search index with correct content
            document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
            document_id = re.sub(r'_+', '_', document_id).strip('_')
            
            try:
                existing_doc = search_client.get_document(key=document_id)
                existing_content = existing_doc.get('content', '')
                
                # Check if content is already good - if so, skip this document entirely
                if (existing_content and 
                    len(existing_content) > 100 and
                    not existing_content.startswith('Document:') and
                    not existing_content.startswith('File:') and
                    'Document:' not in existing_content[:200]):  # Check first 200 chars for placeholder patterns
                    print(f"  ✅ Skipping - already has good content ({len(existing_content)} chars)")
                    skipped_count += 1
                    continue
                else:
                    # Content is bad placeholder content - needs reprocessing
                    if existing_content.startswith('Document:') or existing_content.startswith('File:'):
                        print(f"  🔄 Reprocessing - has placeholder content")
                    elif len(existing_content) <= 100:
                        print(f"  🔄 Reprocessing - content too short ({len(existing_content)} chars)")
                    else:
                        print(f"  🔄 Reprocessing - suspicious content pattern")
                        
            except Exception:
                # Document doesn't exist or error retrieving it - proceed with indexing
                print(f"  ➕ New document - indexing for first time")

            # Extract project info from the blob path itself as a fallback
            folder_path = blob.name.rsplit('/', 1)[0] if '/' in blob.name else ''
            project_name = ""
            year = None
            
            if folder_path:
                path_parts = folder_path.split("/")
                # Logic to find project name and year from path
                if len(path_parts) > 1 and path_parts[0] == 'Projects':
                    if len(path_parts) > 2 and path_parts[1].isdigit(): # e.g. Projects/220/
                        project_name = path_parts[1]
                        if len(path_parts) > 3 and path_parts[2].isdigit() and len(path_parts[2]) == 4:
                            year = int(path_parts[2])
                    elif len(path_parts) > 2: # e.g. Projects/Some Project/
                        project_name = path_parts[1]

            # Download and extract REAL content from the document
            print(f"  📄 Downloading and extracting content...")
            try:
                blob_data = blob_client.download_blob().readall()
                content = extract_document_content(blob.name, blob_data)
                
                if not content or len(content.strip()) < 50:
                    print(f"  ⚠️  Minimal content extracted ({len(content)} chars)")
                    # Fallback to metadata if content extraction fails
                    filename = os.path.basename(blob.name)
                    content = f"Document: {filename}"
                    if folder_path:
                        content += f" | Path: {folder_path}"
                    if project_name:
                        content += f" | Project: {project_name}"
                else:
                    print(f"  ✅ Extracted {len(content)} characters of content")
                    # Show preview of the extracted content
                    preview = content[:300].replace('\n', ' ').strip()
                    if len(content) > 300:
                        preview += "..."
                    print(f"  👁️  Preview: {preview}")
                
            except Exception as e:
                print(f"  ❌ Failed to download/extract content: {e}")
                # Fallback to metadata
                filename = os.path.basename(blob.name)
                content = f"Document: {filename} | Path: {folder_path} | Project: {project_name}"

            # Generate embeddings for the content
            content_vector = await generate_embeddings(openai_client, content)

            # Create search document
            document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
            document_id = re.sub(r'_+', '_', document_id).strip('_')
            
            filename = os.path.basename(blob.name)
            
            search_document = {
                "id": document_id,
                "blob_name": blob.name,
                "blob_url": blob_client.url,
                "filename": filename,
                "content_type": metadata.get("content_type", blob.content_settings.content_type or ""),
                "folder": folder_path,
                "size": blob.size or 0,
                "content": content,
                "content_vector": content_vector,  # Add the embeddings
                "last_modified": blob.last_modified.isoformat(),
                "created_date": blob.creation_time.isoformat() if blob.creation_time else blob.last_modified.isoformat(),
                "project_name": project_name,
                "year": year
            }
            
            # Upload to search index with retry
            for attempt in range(max_retries):
                try:
                    result = search_client.upload_documents([search_document])
                    if result[0].succeeded:
                        success_count += 1
                        if total_count % 100 == 0:  # Progress every 100 docs
                            print(f"  ✅ Progress: {success_count} indexed, {skipped_count} skipped, {total_count} total")
                        break  # Break on success
                    else:
                        if attempt < max_retries - 1:
                            print(f"  ... upload failed, retrying in 5s. Reason: {result[0].error_message}")
                            time.sleep(5)
                        else:
                            error_count += 1
                            print(f"  ❌ Failed to index after retries. Reason: {result[0].error_message}")
                except (ServiceResponseError, ConnectionResetError) as e:
                    if attempt < max_retries - 1:
                        print(f"  ... network error during upload, retrying in 5s ({e})")
                        time.sleep(5)
                    else:
                        raise e
                
        except Exception as e:
            error_count += 1
            print(f"  ❌ Error processing {blob.name}: {str(e)[:150]}")
    
    print(f"\n🎉 PRODUCTION RE-INDEXING COMPLETE!")
    print(f"✅ Successfully indexed: {success_count}")
    print(f"⏭️  Skipped (already current): {skipped_count}")
    print(f"❌ Errors: {error_count}")
    print(f"📊 Total documents processed: {total_count}")
    if total_count > 0:
        print(f"📈 Processing rate: {((success_count + skipped_count)/total_count*100):.1f}%")
        print(f"🔥 Actually processed: {success_count} new/updated documents")
    
    if success_count > 0:
        print(f"\n🤖 Your production bot should now find documents!")
    else:
        print(f"\n💥 No documents were indexed - check credentials and permissions")

if __name__ == "__main__":
    asyncio.run(production_reindex())
