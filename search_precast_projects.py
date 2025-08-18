#!/usr/bin/env python3
"""
Search for precast panel related projects.
This script searches for projects containing specific keywords related to precast panels.
"""

import asyncio
from dtce_ai_bot.integrations.azure.search_client import AzureSearchClient
from dtce_ai_bot.models.legacy_models import SearchQuery

async def search_precast_projects():
    """Search for projects related to precast panels."""
    
    search_client = AzureSearchClient()
    
    # Keywords to search for
    keywords = [
        "Precast Panel",
        "Precast",
        "Precast Connection", 
        "Unispans"
    ]
    
    print("🔍 Searching for Precast Panel Related Projects")
    print("=" * 60)
    print(f"Keywords: {', '.join(keywords)}")
    print()
    
    # Create search query with all keywords
    search_text = " OR ".join([f'"{keyword}"' for keyword in keywords])
    
    query = SearchQuery(
        query=search_text,
        max_results=50,  # Get more results to capture all relevant projects
        include_content=True
    )
    
    try:
        # Execute search
        response = await search_client.search_documents(query)
        
        if not response.results:
            print("❌ No projects found with the specified keywords.")
            return
        
        print(f"📊 Found {len(response.results)} relevant documents")
        print()
        
        # Group by project
        projects = {}
        
        print("📋 INDIVIDUAL DOCUMENTS FOUND:")
        print("=" * 60)
        
        for i, result in enumerate(response.results, 1):
            doc = result.document
            
            # Extract project info
            project_id = doc.project_id or "Unknown"
            file_name = doc.file_name or "Unknown File"
            folder_path = doc.folder_path or ""
            sharepoint_url = doc.sharepoint_url or ""
            
            print(f"{i:2d}. {file_name}")
            print(f"    Score: {result.score:.2f}")
            if folder_path:
                print(f"    Path: {folder_path}")
            if sharepoint_url:
                print(f"    Link: {sharepoint_url}")
            if doc.content_preview:
                print(f"    Preview: {doc.content_preview[:150]}...")
            print()
            
            # Determine project number from folder path or file name
            project_number = extract_project_number(folder_path, file_name, project_id)
            
            if project_number not in projects:
                projects[project_number] = {
                    "project_id": project_id,
                    "documents": [],
                    "folder_paths": set(),
                    "sharepoint_urls": set()
                }
            
            projects[project_number]["documents"].append({
                "file_name": file_name,
                "folder_path": folder_path,
                "sharepoint_url": sharepoint_url,
                "score": result.score,
                "content_preview": doc.content_preview[:200] if doc.content_preview else ""
            })
            
            if folder_path:
                projects[project_number]["folder_paths"].add(folder_path)
            if sharepoint_url:
                projects[project_number]["sharepoint_urls"].add(sharepoint_url)
        
        # Display results
        print("📋 PRECAST PANEL PROJECTS FOUND:")
        print("=" * 60)
        
        for project_num, project_data in sorted(projects.items()):
            print(f"\\n🏗️  PROJECT: {project_num}")
            print(f"   Project ID: {project_data['project_id']}")
            print(f"   Documents found: {len(project_data['documents'])}")
            
            # Show SharePoint links
            if project_data['sharepoint_urls']:
                print("   🔗 SharePoint Links:")
                for url in sorted(project_data['sharepoint_urls']):
                    if url:
                        print(f"      • {url}")
            
            # Show folder paths
            if project_data['folder_paths']:
                print("   📁 Folder Paths:")
                for path in sorted(project_data['folder_paths']):
                    if path:
                        print(f"      • {path}")
            
            # Show top documents
            print("   📄 Key Documents:")
            sorted_docs = sorted(project_data['documents'], key=lambda x: x['score'], reverse=True)
            for doc in sorted_docs[:3]:  # Show top 3 documents
                print(f"      • {doc['file_name']} (Score: {doc['score']:.2f})")
                if doc['content_preview']:
                    print(f"        Preview: {doc['content_preview']}...")
            
            print("-" * 40)
        
        # Summary
        print(f"\\n📊 SUMMARY:")
        print(f"Total projects found: {len(projects)}")
        print(f"Total documents: {len(response.results)}")
        print(f"Search completed in {response.processing_time:.2f} seconds")
        
    except Exception as e:
        print(f"❌ Search failed: {str(e)}")

def extract_project_number(folder_path: str, file_name: str, project_id: str) -> str:
    """Extract project number from various sources."""
    import re
    
    # Try to extract from folder path first (e.g., "Projects/12345/Engineering")
    if folder_path:
        # Look for number patterns in folder path
        numbers = re.findall(r'\\b(\\d{3,6})\\b', folder_path)
        if numbers:
            return numbers[0]
    
    # Try to extract from file name
    if file_name:
        numbers = re.findall(r'\\b(\\d{3,6})\\b', file_name)
        if numbers:
            return numbers[0]
    
    # Use project_id if available
    if project_id and project_id != "Unknown":
        return project_id
    
    # Extract from folder name
    if folder_path:
        parts = folder_path.split('/')
        for part in parts:
            if part.isdigit() and len(part) >= 3:
                return part
    
    return "Unknown"

if __name__ == "__main__":
    print("🔍 DTCE Precast Panel Project Search")
    print("Searching for projects containing: Precast Panel, Precast, Precast Connection, Unispans")
    print()
    
    asyncio.run(search_precast_projects())
