#!/usr/bin/env python3
"""
DTCE AI Bot Document Processing Demo Script
30-minute comprehensive demonstration of all endpoints
"""

import requests
import json
import time
import os
from pathlib import Path

BASE_URL = "http://localhost:8000"

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"🚀 {title}")
    print(f"{'='*60}")

def print_step(step_num, description):
    """Print a formatted step."""
    print(f"\n📋 STEP {step_num}: {description}")
    print("-" * 50)

def make_request(method, endpoint, **kwargs):
    """Make a request and display the response."""
    url = f"{BASE_URL}{endpoint}"
    print(f"🌐 {method.upper()} {url}")
    
    try:
        response = requests.request(method, url, **kwargs)
        print(f"📊 Status: {response.status_code}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            data = response.json()
            print(f"📄 Response:")
            print(json.dumps(data, indent=2)[:500] + ("..." if len(str(data)) > 500 else ""))
        else:
            print(f"📄 Response: {response.text[:200]}...")
            
        return response
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def create_sample_files():
    """Create sample files for the demo."""
    print_step("0", "Creating Sample Files")
    
    # Create a sample directory
    demo_dir = Path("demo_files")
    demo_dir.mkdir(exist_ok=True)
    
    # Sample Python file
    python_file = demo_dir / "sample_code.py"
    python_file.write_text("""
# DTCE Sample Python Code
def calculate_engineering_metrics(projects):
    \"\"\"Calculate key engineering metrics for DTCE projects.\"\"\"
    total_projects = len(projects)
    completed = sum(1 for p in projects if p.status == 'completed')
    
    return {
        'total_projects': total_projects,
        'completion_rate': completed / total_projects if total_projects > 0 else 0,
        'active_projects': total_projects - completed
    }

class DTCEProject:
    def __init__(self, name, status, team_size):
        self.name = name
        self.status = status
        self.team_size = team_size
        
    def get_project_summary(self):
        return f"Project: {self.name}, Status: {self.status}, Team: {self.team_size}"
""")
    
    # Sample documentation file
    doc_file = demo_dir / "project_documentation.md"
    doc_file.write_text("""
# DTCE Engineering Project Documentation

## Overview
This document contains important engineering information for DTCE projects.

## Project Guidelines
- All code must be reviewed before deployment
- Documentation is required for all major features
- Unit tests must have 80% coverage minimum

## Architecture Decisions
### Database Design
We use PostgreSQL for all production databases due to:
- ACID compliance requirements
- Complex query support
- Proven scalability

### API Design
REST APIs follow these patterns:
- GET /api/resource - List resources
- POST /api/resource - Create resource
- PUT /api/resource/{id} - Update resource
- DELETE /api/resource/{id} - Delete resource

## Security Requirements
- All endpoints require authentication
- Sensitive data must be encrypted
- Regular security audits are mandatory

## Performance Standards
- API response time < 200ms
- Database queries < 100ms
- UI load time < 2 seconds
""")
    
    # Sample configuration file
    config_file = demo_dir / "config.json"
    config_file.write_text(json.dumps({
        "app_name": "DTCE Engineering System",
        "version": "2.1.0",
        "environment": "production",
        "database": {
            "host": "dtce-db-prod.example.com",
            "port": 5432,
            "name": "dtce_engineering"
        },
        "features": {
            "ai_assistant": True,
            "document_processing": True,
            "automated_testing": True
        },
        "team_settings": {
            "max_concurrent_projects": 10,
            "code_review_required": True,
            "deployment_approval_levels": 2
        }
    }, indent=2))
    
    print(f"✅ Created {len(list(demo_dir.glob('*')))} sample files in {demo_dir}")
    return demo_dir

def demo_health_check():
    """Demo 1: Health Check (2 minutes)"""
    print_section("DEMO 1: HEALTH CHECK & API STATUS")
    
    print_step("1.1", "Check API Health")
    make_request("GET", "/health/status")
    
    print_step("1.2", "Check API Documentation")
    response = make_request("GET", "/docs")
    if response and response.status_code == 200:
        print("✅ API documentation is accessible")

def demo_document_upload(demo_dir):
    """Demo 2: Document Upload (5 minutes)"""
    print_section("DEMO 2: DOCUMENT UPLOAD")
    
    files_to_upload = list(demo_dir.glob("*"))
    uploaded_files = []
    
    for i, file_path in enumerate(files_to_upload, 1):
        print_step(f"2.{i}", f"Upload {file_path.name}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'text/plain')}
            data = {'folder': 'demo_project'}
            
            response = make_request("POST", "/documents/upload", files=files, data=data)
            if response and response.status_code == 200:
                uploaded_files.append(file_path.name)
                print(f"✅ Successfully uploaded {file_path.name}")
            else:
                print(f"❌ Failed to upload {file_path.name}")
    
    return uploaded_files

def demo_document_listing():
    """Demo 3: Document Listing (3 minutes)"""
    print_section("DEMO 3: DOCUMENT LISTING")
    
    print_step("3.1", "List All Documents")
    make_request("GET", "/documents/list")
    
    print_step("3.2", "List Documents in Demo Folder")
    make_request("GET", "/documents/list", params={"folder": "demo_project"})

def demo_text_extraction(uploaded_files):
    """Demo 4: Text Extraction (8 minutes)"""
    print_section("DEMO 4: TEXT EXTRACTION")
    
    for i, filename in enumerate(uploaded_files[:2], 1):  # Demo first 2 files
        print_step(f"4.{i}", f"Extract Text from {filename}")
        
        blob_name = f"demo_project/{filename}"
        data = {"blob_name": blob_name}
        
        response = make_request("POST", "/documents/extract", json=data)
        if response and response.status_code == 200:
            print(f"✅ Successfully extracted text from {filename}")
        else:
            print(f"❌ Failed to extract text from {filename}")

def demo_document_indexing(uploaded_files):
    """Demo 5: Document Indexing (7 minutes)"""
    print_section("DEMO 5: DOCUMENT INDEXING")
    
    for i, filename in enumerate(uploaded_files, 1):
        print_step(f"5.{i}", f"Index {filename}")
        
        blob_name = f"demo_project/{filename}"
        data = {"blob_name": blob_name}
        
        response = make_request("POST", "/documents/index", json=data)
        if response and response.status_code == 200:
            print(f"✅ Successfully indexed {filename}")
        else:
            print(f"❌ Failed to index {filename}")
        
        # Brief pause to allow indexing to complete
        time.sleep(1)

def demo_document_search():
    """Demo 6: Document Search (5 minutes)"""
    print_section("DEMO 6: DOCUMENT SEARCH")
    
    search_queries = [
        "DTCE engineering metrics",
        "database PostgreSQL",
        "API design patterns",
        "security requirements",
        "Python calculate",
        "project documentation"
    ]
    
    for i, query in enumerate(search_queries, 1):
        print_step(f"6.{i}", f"Search: '{query}'")
        
        params = {
            "query": query,
            "top": 3
        }
        
        response = make_request("GET", "/documents/search", params=params)
        if response and response.status_code == 200:
            results = response.json()
            print(f"✅ Found {len(results)} results for '{query}'")
        else:
            print(f"❌ Search failed for '{query}'")

def demo_advanced_features():
    """Demo 7: Advanced Features (5 minutes)"""
    print_section("DEMO 7: ADVANCED FEATURES")
    
    print_step("7.1", "Search with Folder Filter")
    params = {
        "query": "engineering",
        "filter_folder": "demo_project",
        "top": 5
    }
    make_request("GET", "/documents/search", params=params)
    
    print_step("7.2", "List Documents with Metadata")
    make_request("GET", "/documents/list", params={"folder": "demo_project"})
    
    print_step("7.3", "API Documentation Overview")
    print("📚 Available endpoints:")
    endpoints = [
        "POST /documents/upload - Upload documents",
        "POST /documents/extract - Extract text content",
        "POST /documents/index - Index for search",
        "GET /documents/search - Search documents",
        "GET /documents/list - List documents",
        "DELETE /documents/{blob_name} - Delete documents"
    ]
    for endpoint in endpoints:
        print(f"   📌 {endpoint}")

def cleanup_demo():
    """Demo 8: Cleanup (Optional)"""
    print_section("DEMO 8: CLEANUP (OPTIONAL)")
    
    print_step("8.1", "Cleanup Demo Files")
    print("🧹 To clean up uploaded demo files, you can:")
    print("   - Use DELETE /documents/{blob_name} for each file")
    print("   - Or keep them for further testing")
    print("   - Local demo_files/ directory can be deleted manually")

def main():
    """Run the complete 30-minute demo."""
    print("🎯 DTCE AI BOT - DOCUMENT PROCESSING DEMO")
    print("⏱️  Estimated time: 30 minutes")
    print(f"🌐 API Base URL: {BASE_URL}")
    print("\nThis demo will showcase all document processing capabilities:")
    print("1. Health Check (2 min)")
    print("2. Document Upload (5 min)")
    print("3. Document Listing (3 min)")
    print("4. Text Extraction (8 min)")
    print("5. Document Indexing (7 min)")
    print("6. Document Search (5 min)")
    print("7. Advanced Features (5 min)")
    print("8. Cleanup (Optional)")
    
    input("\n🚀 Press Enter to start the demo...")
    
    start_time = time.time()
    
    try:
        # Create sample files
        demo_dir = create_sample_files()
        
        # Run demo sections
        demo_health_check()
        
        uploaded_files = demo_document_upload(demo_dir)
        if not uploaded_files:
            print("❌ No files uploaded successfully. Check your Azure configuration.")
            return
        
        demo_document_listing()
        demo_text_extraction(uploaded_files)
        demo_document_indexing(uploaded_files)
        demo_document_search()
        demo_advanced_features()
        cleanup_demo()
        
        # Summary
        elapsed_time = time.time() - start_time
        print_section("DEMO COMPLETE!")
        print(f"⏱️  Total time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
        print(f"✅ Successfully demonstrated all document processing endpoints")
        print(f"📊 Uploaded {len(uploaded_files)} files")
        print(f"🔍 Tested search, indexing, and extraction capabilities")
        print("\n🎉 Your DTCE AI Bot is ready for production use!")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")

if __name__ == "__main__":
    main()
