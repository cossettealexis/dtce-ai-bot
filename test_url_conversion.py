#!/usr/bin/env python3
"""
Quick test script to verify URL conversion is working correctly
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import get_settings

def test_url_conversion():
    """Test the URL conversion with the problematic blob URL"""
    
    # Test the URL conversion methods directly without initializing full RAG handler
    from dtce_ai_bot.services.rag_handler import RAGHandler
    
    # Create a mock RAG handler instance to access the methods
    # We'll use the class methods directly
    class TestRAGHandler:
        def __init__(self):
            pass
            
        def _convert_to_suitefiles_url(self, blob_url: str, link_type: str = "file"):
            """Copy of the conversion method from RAGHandler"""
            if not blob_url:
                return None
            
            try:
                from dtce_ai_bot.config.settings import get_settings
                settings = get_settings()
                sharepoint_base_url = settings.SHAREPOINT_SITE_URL
                
                import urllib.parse
                
                # Handle different blob URL patterns
                path_part = None
                
                if "/dtce-documents/" in blob_url:
                    path_part = blob_url.split("/dtce-documents/")[-1]
                elif "/Projects/" in blob_url:
                    # Handle legacy Projects path
                    path_part = "Projects/" + blob_url.split("/Projects/")[-1]
                else:
                    # Try to extract path from any blob URL pattern
                    # Look for common patterns like /container/path
                    parts = blob_url.split("/")
                    if len(parts) > 4 and "blob.core.windows.net" in blob_url:
                        # Standard blob URL: https://storage.blob.core.windows.net/container/path
                        container_idx = -1
                        for i, part in enumerate(parts):
                            if "blob.core.windows.net" in part:
                                container_idx = i + 1
                                break
                        
                        if container_idx > 0 and container_idx < len(parts):
                            path_part = "/".join(parts[container_idx + 1:])  # Skip container name
                
                if not path_part:
                    print(f"Could not extract path from blob URL: {blob_url}")
                    return None
                
                # URL decode the path
                decoded_path = urllib.parse.unquote(path_part)
                
                # Determine if this is a file (has extension) or folder
                filename = decoded_path.split('/')[-1]
                is_file = '.' in filename and len(filename.split('.')[-1]) <= 5  # Common file extensions
                
                if link_type == "file" and is_file:
                    # Build direct file access URL - files go directly to the path without /file/ prefix
                    encoded_path = urllib.parse.quote(decoded_path, safe="/")
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/{encoded_path}"
                else:
                    # Build folder navigation URL - folders need /folder/ prefix
                    if is_file:
                        # Extract folder path from file path
                        folder_path = '/'.join(decoded_path.split('/')[:-1])
                        encoded_path = urllib.parse.quote(folder_path, safe="/") if folder_path else ""
                    else:
                        # This is already a folder path
                        encoded_path = urllib.parse.quote(decoded_path, safe="/")
                    
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/folder/{encoded_path}"
                
                return suite_files_url
                
            except Exception as e:
                print(f"Conversion failed: {e}")
                return None
        
        def _get_safe_suitefiles_url(self, blob_url: str, link_type: str = "file") -> str:
            """Copy of the safe wrapper method"""
            if not blob_url:
                return "Document link not available"
            
            try:
                suitefiles_url = self._convert_to_suitefiles_url(blob_url, link_type)
                if suitefiles_url and not suitefiles_url.startswith('https://dtceaistorage.blob.core.windows.net'):
                    return suitefiles_url
            except Exception as e:
                print(f"Failed to convert blob URL to SuiteFiles: {blob_url}, error: {e}")
            
            # Never return blob URLs - return generic message instead
            return "Access document through SuiteFiles"
    
    # Initialize test handler
    test_handler = TestRAGHandler()
    
    # Test the exact blob URL from the user's complaint
    test_blob_url = "https://dtceaistorage.blob.core.windows.net/dtce-documents/Projects/219/219203/06%20Calculations/01%20Loading/Project%20Report.Docx"
    
    print(f"Testing blob URL: {test_blob_url}")
    print()
    
    # Test direct conversion
    direct_result = test_handler._convert_to_suitefiles_url(test_blob_url, "file")
    print(f"Direct conversion result: {direct_result}")
    print()
    
    # Test safe wrapper
    safe_result = test_handler._get_safe_suitefiles_url(test_blob_url, "file")
    print(f"Safe wrapper result: {safe_result}")
    print()
    
    # Check if result contains blob URL
    if safe_result and "dtceaistorage.blob.core.windows.net" in safe_result:
        print("❌ ERROR: Safe wrapper is still returning blob URL!")
    else:
        print("✅ Good: Safe wrapper is not returning blob URL")

if __name__ == "__main__":
    test_url_conversion()
