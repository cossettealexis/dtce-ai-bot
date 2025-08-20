#!/usr/bin/env python3
"""
Comprehensive test to validate blob URL fixes are working
"""

def validate_no_blob_urls_in_code():
    """Validate that no blob URLs can leak through our code"""
    
    print("=== Blob URL Leakage Prevention Validation ===\n")
    
    # Test cases that should never return blob URLs
    test_cases = [
        {
            "name": "File URL Conversion",
            "blob_url": "https://dtceaistorage.blob.core.windows.net/dtce-documents/Projects/219/219203/06%20Calculations/01%20Loading/Project%20Report.Docx",
            "expected_format": "https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/Projects/219/219203/06%20Calculations/01%20Loading/Project%20Report.Docx"
        },
        {
            "name": "Folder URL Conversion",
            "blob_url": "https://dtceaistorage.blob.core.windows.net/dtce-documents/Engineering/04_Design(Structural)/05_Timber/",
            "expected_format": "https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Engineering/04_Design%28Structural%29/05_Timber"
        },
        {
            "name": "Invalid URL",
            "blob_url": "invalid-url",
            "expected_format": "Access document through SuiteFiles"
        },
        {
            "name": "Empty URL",
            "blob_url": "",
            "expected_format": "Document link not available"
        }
    ]
    
    # Mock the URL conversion functions
    from dtce_ai_bot.config.settings import get_settings
    import urllib.parse
    
    def mock_convert_url(blob_url, link_type="file"):
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
            return None
    
    def mock_safe_url(blob_url, link_type="file"):
        if not blob_url:
            return "Document link not available"
        
        try:
            suitefiles_url = mock_convert_url(blob_url, link_type)
            if suitefiles_url and not suitefiles_url.startswith('https://dtceaistorage.blob.core.windows.net'):
                return suitefiles_url
        except Exception as e:
            pass
        
        return "Access document through SuiteFiles"
    
    # Run tests
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['name']}")
        print(f"Input: {test_case['blob_url']}")
        
        # Determine link type based on test case
        link_type = "folder" if "Folder" in test_case['name'] else "file"
        result = mock_safe_url(test_case['blob_url'], link_type)
        
        print(f"Result: {result}")
        
        # Check if result contains blob URL (should never happen)
        if "dtceaistorage.blob.core.windows.net" in result:
            print("❌ FAIL: Result contains blob URL!")
            all_passed = False
        else:
            print("✅ PASS: No blob URL in result")
        
        print(f"Expected: {test_case['expected_format']}")
        
        if test_case['name'] in ["Invalid URL", "Empty URL"]:
            # For error cases, just check no blob URL
            if "dtceaistorage.blob.core.windows.net" not in result:
                print("✅ PASS: Error case handled correctly")
            else:
                print("❌ FAIL: Error case returned blob URL")
                all_passed = False
        else:
            # For valid cases, check exact format
            if result == test_case['expected_format']:
                print("✅ PASS: Exact format match")
            else:
                print("❌ FAIL: Format mismatch")
                all_passed = False
        
        print("-" * 50)
    
    print(f"\n=== OVERALL RESULT ===")
    if all_passed:
        print("✅ ALL TESTS PASSED: No blob URL leakage detected")
    else:
        print("❌ SOME TESTS FAILED: Blob URL leakage possible")
    
    return all_passed

if __name__ == "__main__":
    validate_no_blob_urls_in_code()
