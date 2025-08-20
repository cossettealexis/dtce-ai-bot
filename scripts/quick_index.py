#!/usr/bin/env python3
"""
Immediate document indexing - just run this to index documents NOW
"""

import requests
import json

def test_direct_indexing():
    """Test indexing with a few common blob names without listing first."""
    base_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    
    print("🚀 Testing direct document indexing (bypassing blob listing)")
    
    # Test with common document patterns - these are likely to exist
    test_blobs = [
        "Projects/219/219201/Engineering.pdf",
        "Projects/219/219264/report.pdf", 
        "Projects/225/225121/design.pdf",
        "Projects/219/219201/calculations.pdf",
        "Projects/220/220001/plans.pdf"
    ]
    
    success_count = 0
    
    for i, blob_name in enumerate(test_blobs, 1):
        print(f"[{i}/{len(test_blobs)}] Testing index of: {blob_name}")
        
        try:
            # Try to index this blob directly
            index_response = requests.post(
                f"{base_url}/documents/index",
                params={"blob_name": blob_name},
                timeout=15
            )
            
            print(f"  Status: {index_response.status_code}")
            
            if index_response.status_code == 200:
                result = index_response.json()
                print(f"  ✅ Success: {result.get('status', 'unknown')}")
                success_count += 1
            elif index_response.status_code == 404:
                print(f"  ⚠️  Blob not found (expected for test names)")
            else:
                print(f"  ❌ Failed: {index_response.text[:100]}")
                
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
    
    print(f"\n📊 Results:")
    print(f"✅ Successfully indexed: {success_count}")
    print(f"⚠️  Expected failures (test names): {len(test_blobs) - success_count}")
    
    if success_count > 0:
        print("🎉 Indexing is working! Now try with real blob names.")
    else:
        print("❌ Indexing failed - API might be down or credentials invalid")
    
    # Now try the health endpoint
    print(f"\n🏥 Testing health endpoint...")
    try:
        health_response = requests.get(f"{base_url}/health", timeout=10)
        print(f"Health status: {health_response.status_code}")
        if health_response.status_code == 200:
            print("✅ API is responding")
        else:
            print("❌ API health check failed")
    except Exception as e:
        print(f"❌ Health check error: {e}")

if __name__ == "__main__":
    test_direct_indexing()
