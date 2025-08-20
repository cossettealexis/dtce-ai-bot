#!/usr/bin/env python3
"""
Test script to simulate what gets sent to GPT in the context
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_context_generation():
    """Test what context is being generated for GPT"""
    
    # Simulate a document that might come from the search
    mock_doc = {
        'content': 'This is a sample project report for project 219...',
        'filename': 'Project Report.Docx',
        'blob_url': 'https://dtceaistorage.blob.core.windows.net/dtce-documents/Projects/219/219203/06%20Calculations/01%20Loading/Project%20Report.Docx'
    }
    
    # Simulate the URL conversion
    from dtce_ai_bot.config.settings import get_settings
    import urllib.parse
    
    def convert_url(blob_url, link_type="file"):
        if not blob_url:
            return None
        
        try:
            settings = get_settings()
            sharepoint_base_url = settings.SHAREPOINT_SITE_URL
            
            path_part = None
            if "/dtce-documents/" in blob_url:
                path_part = blob_url.split("/dtce-documents/")[-1]
            elif "/Projects/" in blob_url:
                path_part = "Projects/" + blob_url.split("/Projects/")[-1]
            
            if not path_part:
                return None
                
            decoded_path = urllib.parse.unquote(path_part)
            filename = decoded_path.split('/')[-1]
            is_file = '.' in filename and len(filename.split('.')[-1]) <= 5
            
            if link_type == "file" and is_file:
                encoded_path = urllib.parse.quote(decoded_path, safe="/")
                return f"{sharepoint_base_url}/AppPages/documents.aspx#/{encoded_path}"
            else:
                if is_file:
                    folder_path = '/'.join(decoded_path.split('/')[:-1])
                    encoded_path = urllib.parse.quote(folder_path, safe="/") if folder_path else ""
                else:
                    encoded_path = urllib.parse.quote(decoded_path, safe="/")
                return f"{sharepoint_base_url}/AppPages/documents.aspx#/folder/{encoded_path}"
                
        except Exception as e:
            print(f"Conversion failed: {e}")
            return None
    
    def get_safe_url(blob_url, link_type="file"):
        if not blob_url:
            return "Document link not available"
        
        try:
            suitefiles_url = convert_url(blob_url, link_type)
            if suitefiles_url and not suitefiles_url.startswith('https://dtceaistorage.blob.core.windows.net'):
                return suitefiles_url
        except Exception as e:
            print(f"Failed to convert: {e}")
        
        return "Access document through SuiteFiles"
    
    # Test the context generation like in _generate_natural_answer
    print("=== Testing Context Generation ===")
    print()
    
    documents = [mock_doc]
    context_parts = []
    
    for doc in documents[:10]:
        content = doc.get('content', '')
        filename = doc.get('filename', 'Unknown')
        blob_url = doc.get('blob_url', '')
        
        print(f"Processing document: {filename}")
        print(f"Original blob_url: {blob_url}")
        
        if content:
            context_part = f"**Document: {filename}**\n{content[:1000]}..."
            if blob_url:
                # Generate file link for direct document access using safe URL method
                suitefiles_url = get_safe_url(blob_url, "file")
                print(f"Converted to: {suitefiles_url}")
                
                if "Document available in SuiteFiles" not in suitefiles_url:
                    context_part += f"\nSuiteFiles URL: {suitefiles_url}"
                    context_part += f"\nTo include in response format as: [{filename}]({suitefiles_url})"
                else:
                    context_part += f"\nDocument available in SuiteFiles (URL conversion failed)"
            context_parts.append(context_part)
    
    if context_parts:
        context = "\n\n".join(context_parts)
        print()
        print("=== Context that would be sent to GPT ===")
        print(context)
        print()
        
        # Check if blob URL appears anywhere in the context
        if "dtceaistorage.blob.core.windows.net" in context:
            print("❌ ERROR: Blob URL found in GPT context!")
        else:
            print("✅ Good: No blob URLs in GPT context")

if __name__ == "__main__":
    test_context_generation()
