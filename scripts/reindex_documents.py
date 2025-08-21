#!/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot/.venv/bin/python
"""
Script to safely update only the content field of existing documents.
This preserves all other document metadata and only improves text extraction.
"""

import asyncio
import sys
import os
import argparse
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient
import structlog

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.integrations.azure_search import get_search_client
from dtce_ai_bot.integrations.azure_storage import get_storage_client

settings = get_settings()
logger = structlog.get_logger(__name__)

def should_skip_file(filename):
    """Check if file should be skipped based on extension (media/archive files)."""
    if not filename:
        return False
    
    # Convert to lowercase for comparison
    filename_lower = filename.lower()
    
    # File extensions to skip - files that typically don't contain useful text
    skip_extensions = {
        # Archive files
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2',
        # Audio files
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus',
        # Video files
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp',
        # Image files
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.ico',
        # CAD and design files
        '.dwg', '.dxf', '.step', '.stp', '.iges', '.igs', '.stl', '.obj',
        # Executable and binary files
        '.exe', '.dll', '.bin', '.iso', '.dmg', '.msi', '.deb', '.rpm',
        # Database files
        '.db', '.sqlite', '.mdb', '.accdb',
        # Font files
        '.ttf', '.otf', '.woff', '.woff2', '.eot',
        # Temporary and cache files
        '.tmp', '.temp', '.cache', '.log', '.bak', '.swp',
        # Proprietary binary formats
        '.psd', '.ai', '.sketch', '.fig', '.indd',
        # Encrypted or protected files
        '.p12', '.pfx', '.keystore', '.jks'
    }
    
    # Also skip files with specific patterns that indicate non-text content
    skip_patterns = [
        'thumbs.db',           # Windows thumbnail cache
        '.ds_store',           # macOS folder metadata
        'desktop.ini',         # Windows folder customization
        '.gitkeep',           # Git placeholder files
        '.keep',              # General placeholder files
        '.gitignore',         # Git ignore files (usually short)
        'readme.md',          # Often just basic info, may not need re-extraction
        'license',            # License files are usually static
        'changelog',          # Often just version info
    ]
    
    # Check extensions
    if any(filename_lower.endswith(ext) for ext in skip_extensions):
        return True
    
    # Check specific patterns
    if any(pattern in filename_lower for pattern in skip_patterns):
        return True
    
    return False

def has_good_content(content, filename):
    """Check if document already has good quality content."""
    if not content or not content.strip():
        return False
    
    content = content.strip()
    filename_lower = filename.lower() if filename else ""
    
    # Bad indicators - content that needs reindexing
    bad_indicators = [
        content.startswith("Document:"),  # Filename-only content
        content == filename,             # Just the filename
        len(content) < 50,              # Very short content
        content.count('\n') < 3,        # Very few lines (likely just metadata)
        content.startswith("Error:"),    # Error messages
        content.startswith("Failed:"),   # Failure messages
        "extraction failed" in content.lower(),  # Failed extractions
        "unsupported format" in content.lower(),  # Unsupported formats
    ]
    
    if any(bad_indicators):
        return False
    
    # Good indicators - content that's already well extracted
    good_indicators = [
        len(content) > 200,                    # Substantial content
        content.count(' ') > 50,               # Good word count
        content.count('\n') > 5,               # Multiple lines/paragraphs
        any(word in content.lower() for word in ['the', 'and', 'or', 'but', 'this', 'that']),  # Natural language
        len(content.split()) > 30,             # Good word count
        '.' in content and content.count('.') > 2,  # Multiple sentences
    ]
    
    # Special handling for certain file types that are likely already good
    if filename_lower:
        # Text files are usually already well extracted
        if any(filename_lower.endswith(ext) for ext in ['.txt', '.md', '.csv', '.json', '.xml', '.html']):
            if len(content) > 100:  # If we already have substantial content from text files
                return True
        
        # Code files are usually already well extracted
        if any(filename_lower.endswith(ext) for ext in ['.py', '.js', '.java', '.cpp', '.c', '.h', '.cs', '.php']):
            if len(content) > 100:  # If we already have substantial content from code files
                return True
    
    # Need at least 3 good indicators for content to be considered "good"
    return sum(good_indicators) >= 3

def is_low_value_file(filename, content=""):
    """Check if file is likely to be expensive to process but low value for search."""
    if not filename:
        return False
    
    filename_lower = filename.lower()
    
    # Files that are typically expensive to process but low search value
    low_value_patterns = [
        # Very large files that might be data dumps
        'dump', 'backup', 'export', 'archive',
        # Log files (usually not useful for general search)
        'log', 'trace', 'debug',
        # Configuration files (often technical, not user-searchable)
        'config', 'settings', 'preferences',
        # Version control files
        'git', 'svn', 'cvs',
        # Build artifacts
        'build', 'dist', 'output', 'generated',
        # Temporary files
        'temp', 'tmp', 'cache',
        # System files
        'system', 'windows', 'registry',
        # Very old files that might be obsolete
        'old', 'obsolete', 'deprecated', 'legacy'
    ]
    
    # Check for low-value patterns in filename
    if any(pattern in filename_lower for pattern in low_value_patterns):
        return True
    
    # Files with very repetitive content (like data exports)
    if content and len(content) > 1000:
        lines = content.split('\n')
        if len(lines) > 100:
            # Check if it's mostly repetitive (like CSV data or logs)
            unique_lines = set(lines[:100])  # Check first 100 lines
            if len(unique_lines) < len(lines[:100]) * 0.1:  # Less than 10% unique lines
                return True
    
    return False

def estimate_processing_costs(document_count):
    """Estimate the costs for processing documents."""
    # Rough estimates based on typical cloud service pricing
    # These are approximations - actual costs may vary
    
    # Document Intelligence (Azure Form Recognizer) - rough estimate
    # Typically around $0.001-0.0015 per page, assuming 1 page per document average
    doc_intelligence_cost = document_count * 0.0015
    
    # Blob Storage operations (read operations)
    # Very minimal cost for blob reads
    storage_cost = document_count * 0.0001
    
    # Search service operations (updates)
    # Minimal cost for search index updates
    search_cost = document_count * 0.0001
    
    total_estimated = doc_intelligence_cost + storage_cost + search_cost
    
    return {
        'document_intelligence': doc_intelligence_cost,
        'storage': storage_cost,
        'search': search_cost,
        'total': total_estimated
    }

async def extract_text_from_blob(blob_name: str, storage_client: BlobServiceClient) -> str:
    """Extract text from a blob using our improved extraction pipeline."""
    from dtce_ai_bot.utils.document_extractor import get_document_extractor
    from dtce_ai_bot.utils.openai_document_extractor import get_openai_document_extractor
    
    # Get blob client
    blob_client = storage_client.get_blob_client(
        container=settings.azure_storage_container,
        blob=blob_name
    )
    
    if not blob_client.exists():
        return f"Document: {blob_name}"
    
    # Get blob properties for content type
    blob_properties = blob_client.get_blob_properties()
    content_type = blob_properties.content_settings.content_type
    
    # Try Form Recognizer first
    try:
        extractor = get_document_extractor(
            settings.azure_form_recognizer_endpoint,
            settings.azure_form_recognizer_key
        )
        
        extraction_result = await extractor.extract_text_from_blob(blob_client, content_type)
        
        if extraction_result.get("extraction_success", True):
            extracted_text = extraction_result.get("extracted_text", "")
            if extracted_text and extracted_text.strip():
                logger.info(f"Form Recognizer success: {blob_name}")
                return extracted_text
                
    except Exception as form_error:
        logger.warning(f"Form Recognizer failed for {blob_name}: {form_error}")
    
    # Try OpenAI fallback
    try:
        openai_extractor = get_openai_document_extractor(
            settings.azure_openai_endpoint,
            settings.azure_openai_api_key,
            settings.azure_openai_deployment_name
        )
        
        extraction_result = await openai_extractor.extract_text_from_blob(blob_client, content_type)
        extracted_text = extraction_result.get("extracted_text", "")
        
        if extracted_text and extracted_text.strip():
            logger.info(f"OpenAI extraction success: {blob_name}")
            return extracted_text
            
    except Exception as openai_error:
        logger.warning(f"OpenAI extraction failed for {blob_name}: {openai_error}")
    
    # Try local DocumentProcessor as final fallback
    try:
        from dtce_ai_bot.utils.document_processor import DocumentProcessor
        
        # Download blob content
        blob_data = blob_client.download_blob().readall()
        
        # Determine file extension
        file_extension = "." + blob_name.lower().split(".")[-1] if "." in blob_name else ""
        
        # Create simple metadata object
        class SimpleMetadata:
            def __init__(self, file_type, file_name):
                self.file_type = file_type
                self.file_name = file_name
                self.extracted_text = ""
        
        metadata = SimpleMetadata(file_extension, blob_name)
        
        # Process with local DocumentProcessor
        processor = DocumentProcessor()
        result = await processor.process_document(metadata, blob_data)
        
        if result.extracted_text and result.extracted_text.strip():
            logger.info(f"Local processor success: {blob_name}")
            return result.extracted_text
            
    except Exception as local_error:
        logger.warning(f"Local processor failed for {blob_name}: {local_error}")
    
    # Fallback to filename
    return f"Document: {blob_name}"

async def get_documents_with_filename_only_content():
    """Find documents with 'Document:' prefix content (using pagination for all results)."""
    search_client = get_search_client()
    
    print("🎯 Scanning ALL documents with 'Document:' filename-only content...")
    
    filename_only_docs = []
    skip = 0
    batch_size = 1000
    
    while True:
        try:
            # Search specifically for documents starting with "Document:" with pagination
            results = search_client.search(
                search_text='content:"Document:*"',
                select=["id", "blob_name", "content", "filename"],
                top=batch_size,
                skip=skip
            )
            
            batch_docs = list(results)
            
            if not batch_docs:
                break  # No more documents
            
            # Filter out files we don't want to reindex
            filtered_docs = []
            skipped_media = 0
            skipped_low_value = 0
            
            for doc in batch_docs:
                filename = doc.get('filename', '')
                content = doc.get('content', '')
                
                if should_skip_file(filename):
                    skipped_media += 1
                    continue
                
                if is_low_value_file(filename, content):
                    skipped_low_value += 1
                    continue
                    
                filtered_docs.append(doc)
            
            filename_only_docs.extend(filtered_docs)
            
            skip_info = []
            if skipped_media > 0:
                skip_info.append(f"{skipped_media} media/binary")
            if skipped_low_value > 0:
                skip_info.append(f"{skipped_low_value} low-value")
            
            if skip_info:
                print(f"  📄 Found {len(filtered_docs)} filename-only documents, skipped {', '.join(skip_info)} files in batch {skip//batch_size + 1} (Total so far: {len(filename_only_docs):,})")
            else:
                print(f"  📄 Found {len(filtered_docs)} filename-only documents in batch {skip//batch_size + 1} (Total so far: {len(filename_only_docs):,})")
            
            # Move to next batch
            skip += batch_size
            
            # Safety check - Azure Search has a 100,000 limit for $skip
            if skip > 100000:
                print("⚠️  Reached Azure Search limit ($skip max: 100,000)")
                print("📊 Note: There may be more documents beyond this limit")
                break
                
        except Exception as e:
            logger.warning(f"Error in filename-only search at skip={skip}: {str(e)}")
            break
    
    print(f"🔍 Filename-only scan complete: Found {len(filename_only_docs):,} documents with 'Document:' content")
    return filename_only_docs

async def get_documents_needing_content_update():
    """Find documents that likely have poor content extraction."""
    search_client = get_search_client()
    
    poor_documents = []
    
    # Use pagination to get all documents (Azure Search max is 1000 per request)
    skip = 0
    batch_size = 1000
    total_processed = 0
    
    print(f"📊 Scanning documents in batches of {batch_size}...")
    
    while True:
        try:
            # Get batch of documents
            results = search_client.search(
                search_text="",
                select=["id", "blob_name", "content", "filename"],
                top=batch_size,
                skip=skip
            )
            
            batch_documents = list(results)
            
            if not batch_documents:
                break  # No more documents
            
            batch_poor = []
            skipped_media_count = 0
            skipped_good_content = 0
            skipped_low_value = 0
            
            for result in batch_documents:
                content = result.get("content", "")
                filename = result.get("filename", "")
                
                # Skip media/archive files
                if should_skip_file(filename):
                    skipped_media_count += 1
                    continue
                
                # Skip low-value files that are expensive to process
                if is_low_value_file(filename, content):
                    skipped_low_value += 1
                    continue
                
                # Skip documents that already have good content
                if has_good_content(content, filename):
                    skipped_good_content += 1
                    continue
                
                # This document needs reindexing
                batch_poor.append(result)
            
            poor_documents.extend(batch_poor)
            total_processed += len(batch_documents)
            
            skip_info = []
            if skipped_media_count > 0:
                skip_info.append(f"{skipped_media_count} media/binary files")
            if skipped_low_value > 0:
                skip_info.append(f"{skipped_low_value} low-value files")
            if skipped_good_content > 0:
                skip_info.append(f"{skipped_good_content} with good content")
                
            if skip_info:
                print(f"  📦 Batch {skip//batch_size + 1}: Found {len(batch_poor)} documents needing reindex, skipped {', '.join(skip_info)} out of {len(batch_documents)} (Total processed: {total_processed:,})")
            else:
                print(f"  📦 Batch {skip//batch_size + 1}: Found {len(batch_poor)} documents needing reindex out of {len(batch_documents)} (Total processed: {total_processed:,})")
            
            # Move to next batch
            skip += batch_size
            
            # Safety check - Azure Search has a 100,000 limit for $skip
            if skip > 100000:
                print("⚠️  Reached Azure Search limit ($skip max: 100,000)")
                print("📊 Note: There may be more documents beyond this limit")
                break
                
        except Exception as e:
            logger.error(f"Error scanning batch at skip={skip}: {str(e)}")
            break
    
    print(f"📋 Scan complete: Found {len(poor_documents):,} documents needing content updates out of {total_processed:,} total documents")
    return poor_documents

async def update_document_content_only(document: dict, search_client: SearchClient, storage_client: BlobServiceClient):
    """Update ONLY the content field for a single document."""
    try:
        blob_name = document["blob_name"]
        doc_id = document["id"]
        
        # Extract new content
        new_content = await extract_text_from_blob(blob_name, storage_client)
        
        # Create minimal update document (only content field)
        update_doc = {
            "id": doc_id,
            "content": new_content
        }
        
        # Update only the content field in search index
        result = search_client.merge_documents([update_doc])
        
        # Check if update was successful
        if result[0].succeeded:
            logger.info(f"Content updated successfully: {blob_name}")
            return True, len(new_content)
        else:
            logger.error(f"Failed to update content: {blob_name}")
            return False, 0
            
    except Exception as e:
        logger.error(f"Error updating {document.get('blob_name', 'unknown')}: {str(e)}")
        return False, 0

async def main():
    """Main content update process."""
    print("🔍 Finding documents with poor content extraction...")
    
    # Get Azure clients
    search_client = get_search_client()
    storage_client = get_storage_client()
    
    # First, try quick scan for obvious problems
    quick_scan_docs = await get_documents_with_filename_only_content()
    
    if quick_scan_docs:
        print(f"\n🎯 Quick scan found {len(quick_scan_docs)} documents with obvious content issues")
        print("💡 Recommendation: Start with these for immediate improvement")
        
        response = input(f"\n🤔 Update these {len(quick_scan_docs)} obvious problem documents first? (y/N): ")
        if response.lower() == 'y':
            poor_documents = quick_scan_docs
        else:
            print("🔍 Performing full scan of all documents...")
            poor_documents = await get_documents_needing_content_update()
    else:
        print("🔍 Performing full scan of all documents...")
        poor_documents = await get_documents_needing_content_update()
    
    if not poor_documents:
        print("✅ No documents found that need content updates!")
        return
    
    print(f"📋 Found {len(poor_documents)} documents with poor content:")
    for doc in poor_documents[:10]:  # Show first 10
        content_preview = doc['content'][:50].replace('\n', ' ')
        print(f"  - {doc['filename']}: '{content_preview}...'")
    
    if len(poor_documents) > 10:
        print(f"  ... and {len(poor_documents) - 10} more")
    
    # Show cost estimates
    costs = estimate_processing_costs(len(poor_documents))
    print(f"\n💰 Estimated processing costs:")
    print(f"  📄 Document Intelligence: ~${costs['document_intelligence']:.2f}")
    print(f"  💾 Storage operations: ~${costs['storage']:.3f}")
    print(f"  🔍 Search operations: ~${costs['search']:.3f}")
    print(f"  💸 Total estimated: ~${costs['total']:.2f}")
    print(f"  💡 Note: Actual costs may vary based on document complexity and size")
    
    # Ask for confirmation
    response = input(f"\n🤔 Update content for these {len(poor_documents)} documents? (y/N): ")
    if response.lower() != 'y':
        print("❌ Content update cancelled.")
        return
    
    print("\n🚀 Starting content update process...")
    print("⚠️  This will ONLY update the 'content' field, preserving all other data.")
    
    success_count = 0
    failed_count = 0
    total_chars_extracted = 0
    
    # Process documents one by one
    for i, doc in enumerate(poor_documents, 1):
        print(f"� [{i}/{len(poor_documents)}] Updating: {doc['filename']}")
        
        success, char_count = await update_document_content_only(doc, search_client, storage_client)
        
        if success:
            success_count += 1
            total_chars_extracted += char_count
            print(f"  ✅ Updated ({char_count:,} characters)")
        else:
            failed_count += 1
            print(f"  ❌ Failed")
        
        # Small delay to avoid overwhelming the services
        if i % 5 == 0:
            await asyncio.sleep(1)
    
    print(f"\n📊 Content update complete!")
    print(f"  ✅ Successfully updated: {success_count}")
    print(f"  ❌ Failed to update: {failed_count}")
    print(f"  📈 Success rate: {success_count/(success_count+failed_count)*100:.1f}%")
    print(f"  📝 Total characters extracted: {total_chars_extracted:,}")
    print(f"\n🎉 Your index structure and all metadata preserved!")

if __name__ == "__main__":
    asyncio.run(main())
