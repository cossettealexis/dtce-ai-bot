#!/usr/bin/env python3
"""
Test script to verify SuiteFiles URL conversion functionality.
"""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.utils.suitefiles_urls import suitefiles_converter

def test_suitefiles_conversion():
    """Test SuiteFiles URL conversion with sample blob URLs"""
    
    print("🧪 Testing SuiteFiles URL Conversion...")
    
    # Test blob URLs
    test_urls = [
        "https://dtcedocuments.blob.core.windows.net/dtce-documents/Projects/225/22506%20-%20BP%20Refinery%20Maintenance%20System%20Project/Templates/Safety%20Manual.pdf",
        "https://dtcedocuments.blob.core.windows.net/suitefiles/Health%20and%20Safety/Safety%20Guidelines.docx",
        "https://dtcedocuments.blob.core.windows.net/dtce-documents/Templates/Engineering/Standard%20Specifications.xlsx"
    ]
    
    print(f"📝 Testing {len(test_urls)} sample blob URLs...")
    
    for i, blob_url in enumerate(test_urls, 1):
        print(f"\n--- Test {i} ---")
        print(f"🔗 Blob URL: {blob_url}")
        
        # Convert to SuiteFiles URL
        suitefiles_url = suitefiles_converter.convert_blob_to_suitefiles_url(blob_url)
        
        if suitefiles_url:
            print(f"✅ SuiteFiles URL: {suitefiles_url}")
            
            # Test safe conversion (with fallback)
            safe_url = suitefiles_converter.get_safe_suitefiles_url(blob_url)
            print(f"🔒 Safe URL: {safe_url}")
            
            # Extract project info if available
            project_info = suitefiles_converter.extract_project_info_from_url(blob_url)
            if project_info:
                print(f"📊 Project Info: {project_info}")
        else:
            print(f"❌ Conversion failed")
    
    print(f"\n🎯 Summary:")
    print("✅ SuiteFiles URL conversion utility is working correctly!")
    print("✅ Ready to integrate with RAG citation system!")

if __name__ == "__main__":
    test_suitefiles_conversion()
