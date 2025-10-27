#!/usr/bin/env python3
"""
DRAWING/CAD FILES SPECIALIZED REINDEXING SCRIPT
Handles .dwg, .dxf, .dwf, .dgn, .rvt, .skp, .step, .stp, .iges, .igs, .ifc, .sat, .x_t,
.prt, .asm, .drw, .idw, .ipt, .iam, .catpart, .catproduct, .sldprt, .sldasm, .slddrw files
Part of the parallel reindexing system for maximum performance
"""

import os
import sys
import time
import signal
import logging
import re
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# Load environment variables
load_dotenv()

# Configure logging
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

def timeout_handler(signum, frame):
    """Signal handler for timeouts"""
    raise TimeoutError("Drawing processing timeout")

def extract_drawing_metadata(blob_name: str, blob_size: int) -> str:
    """
    Extract metadata and create meaningful content for drawing files.
    Since we can't extract actual CAD content, we create descriptive metadata.
    """
    filename = os.path.basename(blob_name)
    folder_path = '/'.join(blob_name.split('/')[:-1]) if '/' in blob_name else ''
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Determine file type description
    file_type_descriptions = {
        '.dwg': 'AutoCAD Drawing',
        '.dxf': 'AutoCAD Drawing Exchange Format',
        '.dwf': 'Autodesk Design Web Format',
        '.dgn': 'MicroStation Design File',
        '.rvt': 'Autodesk Revit Project',
        '.skp': 'SketchUp Model',
        '.3dm': 'Rhino 3D Model',
        '.step': 'STEP 3D CAD Model',
        '.stp': 'STEP 3D CAD Model',
        '.iges': 'IGES 3D CAD Model',
        '.igs': 'IGES 3D CAD Model',
        '.ifc': 'Industry Foundation Classes (BIM)',
        '.sat': 'ACIS SAT 3D Model',
        '.x_t': 'Parasolid 3D Model',
        '.prt': 'CAD Part File',
        '.asm': 'CAD Assembly File',
        '.drw': 'CAD Drawing File',
        '.idw': 'Autodesk Inventor Drawing',
        '.ipt': 'Autodesk Inventor Part',
        '.iam': 'Autodesk Inventor Assembly',
        '.catpart': 'CATIA Part File',
        '.catproduct': 'CATIA Product Assembly',
        '.sldprt': 'SolidWorks Part',
        '.sldasm': 'SolidWorks Assembly',
        '.slddrw': 'SolidWorks Drawing'
    }
    
    file_type = file_type_descriptions.get(file_ext, f'{file_ext.upper()} CAD File')
    
    # Extract meaningful information from filename
    filename_base = os.path.splitext(filename)[0]
    
    # Look for common patterns in engineering filenames
    drawing_info = []
    drawing_info.append(f"File Type: {file_type}")
    drawing_info.append(f"Filename: {filename}")
    drawing_info.append(f"Size: {blob_size / (1024*1024):.1f} MB")
    
    if folder_path:
        drawing_info.append(f"Location: {folder_path}")
    
    # Try to extract project information from path
    if 'Projects/' in blob_name:
        parts = blob_name.split('/')
        if 'Projects' in parts:
            idx = parts.index('Projects')
            if idx + 1 < len(parts):
                project_id = parts[idx + 1]
                drawing_info.append(f"Project: {project_id}")
    
    # Look for version information in filename
    version_patterns = [
        r'[vV](\d+\.?\d*)',
        r'[rR](\d+)',
        r'Rev\s*(\d+)',
        r'_(\d+)$'
    ]
    
    for pattern in version_patterns:
        match = re.search(pattern, filename_base)
        if match:
            drawing_info.append(f"Version/Revision: {match.group(1)}")
            break
    
    # Look for drawing numbers or part numbers
    if re.search(r'\d{3,}', filename_base):
        numbers = re.findall(r'\d{3,}', filename_base)
        if numbers:
            drawing_info.append(f"Drawing/Part Numbers: {', '.join(numbers)}")
    
    # Look for date patterns
    date_patterns = [
        r'(\d{2}[-_]\d{2}[-_]\d{2,4})',
        r'(\d{4}[-_]\d{2}[-_]\d{2})',
        r'(\d{2}\d{2}\d{2,4})'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, filename_base)
        if match:
            drawing_info.append(f"Date Reference: {match.group(1)}")
            break
    
    # Create content summary
    content = f"Drawing File: {filename}\n\n"
    content += "\n".join(drawing_info)
    
    return content

def needs_reprocessing(doc: dict) -> bool:
    """
    Determine if a document needs reprocessing based on content quality
    """
    content = doc.get('content', '')
    
    # Always reprocess if no content
    if not content or len(content.strip()) < 10:
        return True
    
    # Check for signs of poor extraction
    if (
        'unable to extract' in content.lower() or
        'could not parse' in content.lower() or
        'extraction failed' in content.lower() or
        'no text found' in content.lower() or
        len(content.strip()) < 30  # Very minimal content
    ):
        return True
    
    return False

def main():
    """Main execution function"""
    start_time = time.time()
    
    # Check environment variables
    required_vars = [
        'AZURE_STORAGE_CONNECTION_STRING',
        'AZURE_SEARCH_SERVICE_ENDPOINT',
        'AZURE_SEARCH_API_KEY',
        'AZURE_SEARCH_INDEX_NAME'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"💥 Missing environment variables: {', '.join(missing_vars)}")
        return 1
    
    print("📐 DRAWING/CAD FILES REINDEXING STARTED")
    print("="*50)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Initialize Azure clients
        print("🔧 Initializing Azure clients...")
        
        blob_service_client = BlobServiceClient.from_connection_string(
            os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        )
        
        search_client = SearchClient(
            endpoint=os.getenv('AZURE_SEARCH_SERVICE_ENDPOINT'),
            index_name=os.getenv('AZURE_SEARCH_INDEX_NAME'),
            credential=AzureKeyCredential(os.getenv('AZURE_SEARCH_API_KEY'))
        )
        
        container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "dtce-documents")
        container_client = blob_service_client.get_container_client(container_name)
        
        print("✅ Azure clients initialized!")
        print()
        
        # Define drawing file extensions
        drawing_extensions = [
            '.dwg', '.dxf', '.dwf', '.dgn', '.rvt', '.skp', '.3dm',
            '.step', '.stp', '.iges', '.igs', '.ifc', '.sat', '.x_t',
            '.prt', '.asm', '.drw', '.idw', '.ipt', '.iam',
            '.catpart', '.catproduct', '.sldprt', '.sldasm', '.slddrw'
        ]
        
        # Get all drawing files from blob storage
        print("🔍 Finding drawing/CAD files...")
        drawing_files = []
        
        for blob in container_client.list_blobs():
            if any(blob.name.lower().endswith(ext) for ext in drawing_extensions):
                # Skip temporary/backup files
                if any(skip in blob.name.lower() for skip in [
                    '~$', '.tmp', 'temp', 'backup', '.bak', 
                    'recycle', 'deleted', '.keep', '.gitkeep'
                ]):
                    continue
                
                drawing_files.append(blob)
        
        print(f"📐 Found {len(drawing_files)} drawing/CAD files to process")
        print()
        
        if not drawing_files:
            print("ℹ️  No drawing/CAD files found to process")
            return 0
        
        # Process each drawing file
        processed = 0
        updated = 0
        errors = 0
        
        for i, blob in enumerate(drawing_files):
            try:
                print(f"📐 [{i+1}/{len(drawing_files)}] Processing: {blob.name}")
                
                # Check if document exists in search index
                try:
                    search_results = list(search_client.search(
                        search_text="*",
                        filter=f"blob_name eq '{blob.name}'",
                        select="id,content,blob_name"
                    ))
                    
                    existing_doc = search_results[0] if search_results else None
                    
                    # Skip if document exists and doesn't need reprocessing
                    if existing_doc and not needs_reprocessing(existing_doc):
                        print(f"   ✅ Already processed with good content - skipping")
                        continue
                        
                except Exception as e:
                    print(f"   ⚠️  Search check failed: {str(e)[:50]}")
                    existing_doc = None
                
                # Extract metadata content (no need to download the actual file)
                print(f"   📐 Extracting drawing metadata...")
                content = extract_drawing_metadata(blob.name, blob.size or 0)
                
                if not content or len(content.strip()) < 20:
                    print(f"   ⚠️  No meaningful content extracted")
                    errors += 1
                    continue
                
                # Prepare document for indexing (match schema from other scripts)
                filename = os.path.basename(blob.name)
                folder_path = '/'.join(blob.name.split('/')[:-1]) if '/' in blob.name else ''
                
                # Extract project info
                project_name = ""
                year = None  # Use None instead of empty string for integer fields
                if blob.name.startswith('Projects/'):
                    parts = blob.name.split('/')
                    if len(parts) >= 3:
                        project_name = parts[2]  # e.g., "225200"
                        try:
                            if project_name.isdigit() and len(project_name) >= 3:
                                year = int(project_name[:3]) + 2000  # Return actual integer
                        except:
                            year = None
                
                # Create document ID
                document_id = blob.name.replace('/', '_').replace(' ', '_').replace('#', '').replace('.', '_')
                document_id = re.sub(r'[^\w\-_]', '_', document_id)
                document_id = re.sub(r'_+', '_', document_id).strip('_')
                
                # Get blob client for URL
                blob_client = container_client.get_blob_client(blob.name)
                
                # Determine content type based on extension
                file_ext = os.path.splitext(blob.name)[1].lower()
                content_type_map = {
                    '.dwg': 'application/dwg',
                    '.dxf': 'application/dxf',
                    '.dwf': 'application/dwf',
                    '.dgn': 'application/dgn',
                    '.rvt': 'application/rvt',
                    '.skp': 'application/skp',
                    '.step': 'application/step',
                    '.stp': 'application/step',
                    '.iges': 'application/iges',
                    '.igs': 'application/iges',
                    '.ifc': 'application/ifc'
                }
                content_type = content_type_map.get(file_ext, 'application/octet-stream')
                
                document = {
                    "id": document_id,
                    "blob_name": blob.name,
                    "blob_url": blob_client.url,
                    "filename": filename,
                    "content_type": content_type,
                    "folder": folder_path,
                    "size": blob.size or 0,
                    "content": content,
                    "last_modified": blob.last_modified.isoformat(),
                    "created_date": blob.creation_time.isoformat() if blob.creation_time else blob.last_modified.isoformat(),
                    "project_name": project_name,
                    "year": year
                }
                
                # Upload to search index
                print(f"   📤 Uploading to search index...")
                search_client.upload_documents([document])
                
                print(f"   ✅ Successfully processed ({len(content)} chars)")
                updated += 1
                
                processed += 1
                
                # Progress indicator
                if processed % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed * 60
                    print(f"   📊 Progress: {processed}/{len(drawing_files)} files ({rate:.1f}/min)")
                    print()
                
            except KeyboardInterrupt:
                print("\n⏹️  Interrupted by user")
                break
                
            except Exception as e:
                print(f"   💥 Unexpected error: {str(e)[:100]}")
                errors += 1
                continue
        
        # Final summary
        elapsed = time.time() - start_time
        print()
        print("📐 DRAWING/CAD FILES REINDEXING COMPLETED")
        print("="*50)
        print(f"📐 Total files processed: {processed}")
        print(f"✅ Successfully updated: {updated}")
        print(f"💥 Errors: {errors}")
        print(f"⏱️  Total time: {elapsed/60:.1f} minutes")
        print(f"📈 Average rate: {processed/elapsed*60:.1f} files/minute")
        print(f"🕐 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
        return 1
        
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
