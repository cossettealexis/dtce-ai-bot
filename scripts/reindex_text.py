#!/usr/bin/env python3
"""
Text and other files (.txt, .csv, .log, .json, .xml, etc.) reindexing script
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
from openai import AsyncAzureOpenAI

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

def fast_extract_text_content(blob_data: bytes, filename: str) -> str:
    """Fast text file extraction."""
    try:
        size_mb = len(blob_data) / (1024 * 1024)
        print(f"    📄 Extracting text content ({size_mb:.1f}MB)...")
        
        # Quick binary check - skip if looks like binary data
        sample_size = min(1024, len(blob_data))
        sample = blob_data[:sample_size]
        
        # Count null bytes and control characters
        null_count = sample.count(b'\\x00')
        control_count = sum(1 for b in sample if b < 32 and b not in [9, 10, 13])  # Allow tab, LF, CR
        
        if null_count > sample_size * 0.01 or control_count > sample_size * 0.05:
            return f"Binary file: {os.path.basename(filename)} (content not extracted)"
        
        # Try UTF-8 first
        try:
            # Limit size for speed - only read first 50KB for large files
            text_data = blob_data[:50*1024] if len(blob_data) > 50*1024 else blob_data
            text = text_data.decode('utf-8').strip()
            
            # Quality check
            if len(text) > 10:
                printable_chars = sum(1 for c in text if c.isprintable() or c.isspace())
                if printable_chars / len(text) >= 0.7:  # At least 70% printable
                    print(f"    ✅ Text (UTF-8): {len(text)} chars")
                    return text
            
        except UnicodeDecodeError:
            pass
        
        # Fallback to latin-1
        try:
            text_data = blob_data[:50*1024] if len(blob_data) > 50*1024 else blob_data
            text = text_data.decode('latin-1', errors='ignore').strip()
            
            if len(text) > 10:
                printable_chars = sum(1 for c in text if c.isprintable() or c.isspace())
                if printable_chars / len(text) >= 0.7:
                    print(f"    ✅ Text (latin-1): {len(text)} chars")
                    return text
                    
        except Exception:
            pass
        
        return f"Text file: {os.path.basename(filename)} (content extraction failed)"
        
    except Exception as e:
        return f"Text file: {os.path.basename(filename)} (error: {str(e)[:100]})"

def fast_extract_csv_content(blob_data: bytes, filename: str) -> str:
    """Fast CSV extraction with structure preservation."""
    try:
        size_mb = len(blob_data) / (1024 * 1024)
        print(f"    📊 Extracting CSV content ({size_mb:.1f}MB)...")
        
        # Read as text first
        try:
            # Limit to first 20KB for large CSVs
            text_data = blob_data[:20*1024] if len(blob_data) > 20*1024 else blob_data
            text = text_data.decode('utf-8', errors='ignore')
        except:
            text = blob_data[:20*1024].decode('latin-1', errors='ignore')
        
        lines = text.split('\\n')
        
        # Process header and some data rows
        processed_lines = []
        for i, line in enumerate(lines[:100]):  # First 100 lines max
            if line.strip():
                processed_lines.append(line.strip())
                
        if len(processed_lines) > 1:
            result = '\\n'.join(processed_lines)
            print(f"    ✅ CSV: {len(processed_lines)} rows, {len(result)} chars")
            return result
        else:
            return f"CSV file: {os.path.basename(filename)} (empty or unreadable)"
            
    except Exception as e:
        return f"CSV file: {os.path.basename(filename)} (extraction failed: {str(e)[:100]})"

def fast_extract_json_content(blob_data: bytes, filename: str) -> str:
    """Fast JSON extraction with formatting."""
    try:
        size_mb = len(blob_data) / (1024 * 1024)
        print(f"    🔧 Extracting JSON content ({size_mb:.1f}MB)...")
        
        # Read as text
        try:
            # Limit size for large JSON files
            text_data = blob_data[:30*1024] if len(blob_data) > 30*1024 else blob_data
            text = text_data.decode('utf-8')
        except:
            text = blob_data[:30*1024].decode('latin-1', errors='ignore')
        
        # Try to parse and format JSON
        try:
            import json
            json_obj = json.loads(text)
            
            # Create a readable summary for large JSON
            if isinstance(json_obj, dict):
                keys = list(json_obj.keys())[:20]  # First 20 keys
                summary = f"JSON Object with keys: {', '.join(str(k) for k in keys)}"
                if len(json_obj) > 20:
                    summary += f" (and {len(json_obj) - 20} more)"
                
                # Add some sample values
                sample_data = {}
                for key in keys[:5]:
                    value = json_obj[key]
                    if isinstance(value, (str, int, float, bool)):
                        sample_data[key] = value
                    elif isinstance(value, (list, dict)):
                        sample_data[key] = f"<{type(value).__name__} with {len(value)} items>"
                
                if sample_data:
                    summary += f"\\n\\nSample data: {json.dumps(sample_data, indent=2)}"
                
                result = summary
            elif isinstance(json_obj, list):
                result = f"JSON Array with {len(json_obj)} items\\n\\nFirst few items: {json.dumps(json_obj[:3], indent=2)}"
            else:
                result = f"JSON Value: {json.dumps(json_obj, indent=2)}"
            
            print(f"    ✅ JSON: parsed and formatted, {len(result)} chars")
            return result
            
        except json.JSONDecodeError:
            # If not valid JSON, treat as text
            result = text.strip()
            print(f"    ✅ JSON (as text): {len(result)} chars")
            return result
            
    except Exception as e:
        return f"JSON file: {os.path.basename(filename)} (extraction failed: {str(e)[:100]})"

def document_needs_update(blob, existing_docs: dict) -> bool:
    """Check if text file needs updating."""
    document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
    document_id = re.sub(r'_+', '_', document_id).strip('_')
    
    if document_id not in existing_docs:
        return True
    
    existing_doc = existing_docs[document_id]
    existing_content = existing_doc.get('content', '')
    
    # Update if content is bad
    if (not existing_content or 
        len(existing_content) < 20 or
        'content extraction failed' in existing_content.lower() or
        'content not extracted' in existing_content.lower()):
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
        truncated_text = text[:4000]
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=truncated_text
        )
        return response.data[0].embedding
    except:
        return []

async def process_text_files():
    """Process text and other files."""
    print("📄 TEXT FILES REINDEXING SCRIPT")
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
    print("📋 Loading existing text files from search index...")
    existing_docs = {}
    try:
        results = search_client.search("*", select=["id", "last_modified", "content"], top=100000)
        for doc in results:
            if doc.get('id'):
                existing_docs[doc['id']] = {
                    'last_modified': doc.get('last_modified'),
                    'content': doc.get('content', '')
                }
        print(f"✅ Loaded {len(existing_docs)} existing documents")
    except Exception as e:
        print(f"⚠️ Could not load existing docs: {e}")
    
    # Find text files that need updating
    print("🔍 Scanning for text files...")
    text_blobs = []
    text_extensions = [
        '.txt', '.md', '.readme', '.csv', '.tsv', '.log', '.ini', '.cfg', '.conf',
        '.json', '.xml', '.html', '.htm', '.css', '.js', '.py', '.sql', '.yml', '.yaml'
    ]
    
    # Projects text files first
    try:
        for blob in container_client.list_blobs(name_starts_with="Projects/"):
            if any(blob.name.lower().endswith(ext) for ext in text_extensions):
                if document_needs_update(blob, existing_docs):
                    text_blobs.append(blob)
    except Exception as e:
        print(f"⚠️ Error scanning Projects text files: {e}")
    
    # Other text files
    try:
        for blob in container_client.list_blobs():
            if (any(blob.name.lower().endswith(ext) for ext in text_extensions) and 
                not blob.name.startswith("Projects/")):
                if document_needs_update(blob, existing_docs):
                    text_blobs.append(blob)
    except Exception as e:
        print(f"⚠️ Error scanning other text files: {e}")
    
    total_files = len(text_blobs)
    print(f"📊 Found {total_files} text files to process")
    
    if total_files == 0:
        print("✅ All text files are up to date!")
        return
    
    # Process text files
    processed = 0
    errors = 0
    start_time = time.time()
    
    for i, blob in enumerate(text_blobs, 1):
        try:
            print(f"\\n[{i}/{total_files}] Processing: {blob.name}")
            
            # Download blob
            blob_client = storage_client.get_blob_client(container=container_name, blob=blob.name)
            blob_data = blob_client.download_blob().readall()
            
            # Extract content based on file type
            filename_lower = blob.name.lower()
            if filename_lower.endswith('.csv') or filename_lower.endswith('.tsv'):
                content = fast_extract_csv_content(blob_data, blob.name)
            elif filename_lower.endswith('.json'):
                content = fast_extract_json_content(blob_data, blob.name)
            else:
                content = fast_extract_text_content(blob_data, blob.name)
            
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
            
            # Determine content type
            content_type = "text/plain"
            if filename_lower.endswith('.csv'):
                content_type = "text/csv"
            elif filename_lower.endswith('.json'):
                content_type = "application/json"
            elif filename_lower.endswith('.xml'):
                content_type = "application/xml"
            elif filename_lower.endswith('.html') or filename_lower.endswith('.htm'):
                content_type = "text/html"
            
            search_document = {
                "id": document_id,
                "blob_name": blob.name,
                "blob_url": blob_client.url,
                "filename": filename,
                "content_type": content_type,
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
                remaining = total_files - i
                eta = remaining / rate if rate > 0 else 0
                print(f"    📊 Progress: {processed}/{total_files}, {rate:.1f} files/min, ETA: {eta:.1f}min")
                
        except Exception as e:
            errors += 1
            print(f"    ❌ Error: {str(e)[:100]}")
    
    # Summary
    elapsed = time.time() - start_time
    rate = processed / elapsed * 60 if elapsed > 0 else 0
    
    print(f"\\n🎉 TEXT FILES PROCESSING COMPLETE!")
    print(f"✅ Processed: {processed}")
    print(f"❌ Errors: {errors}")
    print(f"⏱️ Time: {elapsed/60:.1f} minutes")
    print(f"📈 Rate: {rate:.1f} files/minute")

if __name__ == "__main__":
    asyncio.run(process_text_files())
