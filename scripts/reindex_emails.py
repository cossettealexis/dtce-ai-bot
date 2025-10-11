#!/usr/bin/env python3
"""
Email files (.msg, .eml) reindexing script
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
import email
from email.parser import BytesParser

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import extract-msg for .msg files
try:
    import extract_msg
    EXTRACT_MSG_AVAILABLE = True
except ImportError:
    EXTRACT_MSG_AVAILABLE = False

# Load environment variables
load_dotenv()

def fast_extract_eml_content(blob_data: bytes, filename: str) -> str:
    """Fast EML extraction."""
    try:
        size_mb = len(blob_data) / (1024 * 1024)
        print(f"    📧 Extracting EML content ({size_mb:.1f}MB)...")
        
        parser = BytesParser()
        msg = parser.parsebytes(blob_data)
        
        # Extract headers
        subject = msg.get('Subject', 'No Subject')
        sender = msg.get('From', 'Unknown Sender')
        recipient = msg.get('To', 'Unknown Recipient')
        date = msg.get('Date', 'Unknown Date')
        
        # Extract body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        body_content = part.get_content()
                        if isinstance(body_content, str):
                            body += body_content[:5000]  # Limit for speed
                        break  # Take first text/plain part
                    except:
                        continue
                elif content_type == "text/html" and not body:
                    try:
                        html_content = part.get_content()
                        if isinstance(html_content, str):
                            # Basic HTML to text conversion
                            import re
                            body = re.sub(r'<[^>]+>', '', html_content)[:5000]
                    except:
                        continue
        else:
            try:
                body = str(msg.get_content())[:5000]
            except:
                body = "Email body extraction failed"
        
        # Combine into readable format
        email_content = f"""Subject: {subject}
From: {sender}
To: {recipient}
Date: {date}

{body}"""
        
        print(f"    ✅ EML: Subject='{subject[:50]}...', {len(email_content)} chars")
        return email_content.strip()
        
    except Exception as e:
        return f"EML email file (extraction failed: {str(e)[:100]})"

def fast_extract_msg_content(blob_data: bytes, filename: str) -> str:
    """Fast MSG extraction."""
    try:
        size_mb = len(blob_data) / (1024 * 1024)
        print(f"    📧 Extracting MSG content ({size_mb:.1f}MB)...")
        
        if EXTRACT_MSG_AVAILABLE:
            try:
                # Use extract-msg library if available
                msg_stream = io.BytesIO(blob_data)
                msg = extract_msg.Message(msg_stream)
                
                subject = getattr(msg, 'subject', 'No Subject') or 'No Subject'
                sender = getattr(msg, 'sender', 'Unknown Sender') or 'Unknown Sender'
                recipients = getattr(msg, 'to', 'Unknown Recipients') or 'Unknown Recipients'
                date = getattr(msg, 'date', 'Unknown Date') or 'Unknown Date'
                body = getattr(msg, 'body', '') or ''
                
                # Limit body size for speed
                if len(body) > 5000:
                    body = body[:5000] + "... [truncated]"
                
                email_content = f"""Subject: {subject}
From: {sender}
To: {recipients}
Date: {date}

{body}"""
                
                print(f"    ✅ MSG (extract-msg): Subject='{subject[:50]}...', {len(email_content)} chars")
                return email_content.strip()
                
            except Exception as e:
                print(f"    ⚠️ extract-msg failed: {str(e)[:50]}, trying fallback...")
        
        # Fallback: Basic text extraction from MSG binary data
        text = blob_data.decode('utf-8', errors='ignore')
        
        # Clean up and extract readable parts
        import re
        
        # Look for common email patterns
        email_parts = []
        
        # Try to find subject
        subject_match = re.search(r'Subject:?\\s*([^\\n\\r]+)', text, re.IGNORECASE)
        if subject_match:
            email_parts.append(f"Subject: {subject_match.group(1).strip()}")
        
        # Try to find sender
        from_match = re.search(r'From:?\\s*([^\\n\\r]+)', text, re.IGNORECASE)
        if from_match:
            email_parts.append(f"From: {from_match.group(1).strip()}")
        
        # Try to find recipients
        to_match = re.search(r'To:?\\s*([^\\n\\r]+)', text, re.IGNORECASE)
        if to_match:
            email_parts.append(f"To: {to_match.group(1).strip()}")
        
        # Extract readable text content (filter out binary junk)
        readable_text = re.sub(r'[^\\x20-\\x7E\\n\\r\\t]', '', text)
        readable_text = re.sub(r'\\s+', ' ', readable_text)
        
        # Get a reasonable chunk of readable text
        if len(readable_text) > 100:
            email_parts.append(f"Content: {readable_text[:3000]}")
        
        if email_parts:
            result = "\\n".join(email_parts)
            print(f"    ✅ MSG (fallback): {len(email_parts)} parts, {len(result)} chars")
            return result
        else:
            return "Outlook message file (basic extraction only)"
            
    except Exception as e:
        return f"MSG email file (extraction failed: {str(e)[:100]})"

def document_needs_update(blob, existing_docs: dict) -> bool:
    """Check if email needs updating."""
    document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
    document_id = re.sub(r'_+', '_', document_id).strip('_')
    
    if document_id not in existing_docs:
        return True
    
    existing_doc = existing_docs[document_id]
    existing_content = existing_doc.get('content', '')
    
    # Update if content is bad
    if (not existing_content or 
        len(existing_content) < 50 or
        'extraction failed' in existing_content.lower() or
        'basic extraction only' in existing_content.lower()):
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

async def process_emails():
    """Process only email files."""
    print("📧 EMAIL FILES REINDEXING SCRIPT")
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
    print("📋 Loading existing email files from search index...")
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
    
    # Find email files that need updating
    print("🔍 Scanning for email files...")
    email_blobs = []
    email_extensions = ['.msg', '.eml']
    
    # Projects emails first
    try:
        for blob in container_client.list_blobs(name_starts_with="Projects/"):
            if any(blob.name.lower().endswith(ext) for ext in email_extensions):
                if document_needs_update(blob, existing_docs):
                    email_blobs.append(blob)
    except Exception as e:
        print(f"⚠️ Error scanning Projects emails: {e}")
    
    # Other emails
    try:
        for blob in container_client.list_blobs():
            if (any(blob.name.lower().endswith(ext) for ext in email_extensions) and 
                not blob.name.startswith("Projects/")):
                if document_needs_update(blob, existing_docs):
                    email_blobs.append(blob)
    except Exception as e:
        print(f"⚠️ Error scanning other emails: {e}")
    
    total_emails = len(email_blobs)
    print(f"📊 Found {total_emails} email files to process")
    
    if total_emails == 0:
        print("✅ All email files are up to date!")
        return
    
    # Process email files
    processed = 0
    errors = 0
    start_time = time.time()
    
    for i, blob in enumerate(email_blobs, 1):
        try:
            print(f"\\n[{i}/{total_emails}] Processing: {blob.name}")
            
            # Download blob
            blob_client = storage_client.get_blob_client(container=container_name, blob=blob.name)
            blob_data = blob_client.download_blob().readall()
            
            # Extract content based on file type
            filename_lower = blob.name.lower()
            if filename_lower.endswith('.eml'):
                content = fast_extract_eml_content(blob_data, blob.name)
            else:  # .msg
                content = fast_extract_msg_content(blob_data, blob.name)
            
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
            
            content_type = "application/vnd.ms-outlook" if filename_lower.endswith('.msg') else "message/rfc822"
            
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
            if i % 5 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed * 60
                remaining = total_emails - i
                eta = remaining / rate if rate > 0 else 0
                print(f"    📊 Progress: {processed}/{total_emails}, {rate:.1f} emails/min, ETA: {eta:.1f}min")
                
        except Exception as e:
            errors += 1
            print(f"    ❌ Error: {str(e)[:100]}")
    
    # Summary
    elapsed = time.time() - start_time
    rate = processed / elapsed * 60 if elapsed > 0 else 0
    
    print(f"\\n🎉 EMAIL PROCESSING COMPLETE!")
    print(f"✅ Processed: {processed}")
    print(f"❌ Errors: {errors}")
    print(f"⏱️ Time: {elapsed/60:.1f} minutes")
    print(f"📈 Rate: {rate:.1f} emails/minute")

if __name__ == "__main__":
    asyncio.run(process_emails())
