#!/usr/bin/env python3
"""
Search for precast panel related projects using the actual index schema.
This script searches for projects containing specific keywords related to precast panels.
"""

import asyncio
import re
from dtce_ai_bot.integrations.azure_search import get_search_client

async def search_precast_projects():
    """Search for projects related to precast panels."""
    
    search_client = get_search_client()
    
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
    
    try:
        # Execute search with the actual search client
        results = search_client.search(search_text, top=100)  # Get more results
        
        all_results = list(results)
        
        if not all_results:
            print("❌ No projects found with the specified keywords.")
            return
        
        print(f"📊 Found {len(all_results)} relevant documents")
        print()
        
        # Group by project
        projects = {}
        
        print("📋 PRECAST PANEL RELATED DOCUMENTS:")
        print("=" * 60)
        
        for i, result in enumerate(all_results, 1):
            # Extract document info using actual field names
            filename = result.get('filename') or 'Unknown File'
            blob_name = result.get('blob_name') or ''
            blob_url = result.get('blob_url') or ''
            content = result.get('content', '')[:300] + '...' if result.get('content') else ''
            score = result.get('@search.score', 0)
            
            print(f"{i:2d}. {filename}")
            print(f"    Score: {score:.2f}")
            if blob_name:
                print(f"    Path: {blob_name}")
            if blob_url:
                print(f"    Link: {blob_url}")
            if content.strip():
                print(f"    Content: {content}")
            
            # Extract project number from blob_name path
            project_number = extract_project_number_from_path(blob_name, filename)
            
            if project_number not in projects:
                projects[project_number] = {
                    "documents": [],
                    "paths": set(),
                    "urls": set()
                }
            
            projects[project_number]["documents"].append({
                "filename": filename,
                "blob_name": blob_name,
                "blob_url": blob_url,
                "score": score,
                "content_preview": content[:200]
            })
            
            if blob_name:
                projects[project_number]["paths"].add(blob_name)
            if blob_url:
                projects[project_number]["urls"].add(blob_url)
            
            print("-" * 40)
        
        # Display project summary
        print(f"\\n📊 PROJECT SUMMARY:")
        print("=" * 60)
        
        for project_num, project_data in sorted(projects.items()):
            if project_num == "Unknown":
                continue
                
            print(f"\\n🏗️  PROJECT {project_num}:")
            print(f"   Documents found: {len(project_data['documents'])}")
            
            # Show SuiteFiles SharePoint links
            print("   🔗 SuiteFiles Links:")
            unique_folders = set()
            
            # Extract project folders from paths
            for path in project_data['paths']:
                if path and project_num in path:
                    folder = extract_project_folder(path, project_num)
                    if folder:
                        unique_folders.add(folder)
            
            # If no specific folder found, use the project number
            if not unique_folders and project_num != "Unknown":
                # Extract main project number (3-digit) for SuiteFiles URL
                main_project = extract_main_project_folder(project_num)
                if main_project:
                    unique_folders.add(main_project)
            
            # Generate SuiteFiles SharePoint URLs
            for folder in sorted(unique_folders):
                suitefiles_url = f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{folder}"
                print(f"      • {suitefiles_url}")
            
            # Show folder paths for reference
            if project_data['paths']:
                print("   📁 Folder Paths (for reference):")
                unique_path_folders = set()
                for path in project_data['paths']:
                    if path and project_num in path:
                        folder = extract_project_folder(path, project_num)
                        if folder:
                            unique_path_folders.add(folder)
                
                for folder in sorted(unique_path_folders):
                    print(f"      • Projects/{folder}")
            
            # Show top documents by relevance
            print("   📄 Most Relevant Documents:")
            sorted_docs = sorted(project_data['documents'], key=lambda x: x['score'], reverse=True)
            for doc in sorted_docs[:3]:  # Show top 3 documents
                print(f"      • {doc['filename']} (Score: {doc['score']:.2f})")
        
        # Handle unknown projects
        if "Unknown" in projects:
            unknown_docs = projects["Unknown"]["documents"]
            print(f"\\n❓ DOCUMENTS WITHOUT CLEAR PROJECT NUMBERS ({len(unknown_docs)} docs):")
            for doc in sorted(unknown_docs, key=lambda x: x['score'], reverse=True)[:5]:
                print(f"   • {doc['filename']} (Score: {doc['score']:.2f})")
                if doc['blob_name']:
                    print(f"     Path: {doc['blob_name']}")
        
        # Final summary
        known_projects = [p for p in projects.keys() if p != "Unknown"]
        print(f"\\n✅ FINAL SUMMARY:")
        print(f"📋 Total projects identified: {len(known_projects)}")
        print(f"📄 Total relevant documents: {len(all_results)}")
        if known_projects:
            print(f"🏗️  Project numbers: {', '.join(sorted(known_projects))}")
        
    except Exception as e:
        print(f"❌ Search failed: {str(e)}")

def extract_project_number_from_path(blob_name: str, filename: str) -> str:
    """Extract project number from blob path or filename."""
    # Try blob_name first (e.g., "Projects/220/220294/filename.ext")
    if blob_name:
        # Look for Projects/XXX/XXXXXX pattern
        match = re.search(r'Projects/(\d+)/(\d+)', blob_name, re.IGNORECASE)
        if match:
            return match.group(2)  # Return the longer project number
        
        # Look for any 4-6 digit number in the path
        numbers = re.findall(r'\\b(\\d{4,6})\\b', blob_name)
        if numbers:
            return numbers[-1]  # Return the last (usually most specific) number
    
    # Try filename
    if filename:
        numbers = re.findall(r'\\b(\\d{4,6})\\b', filename)
        if numbers:
            return numbers[0]
    
    return "Unknown"

def extract_base_project_url(url: str, project_num: str) -> str:
    """Extract base project folder URL for navigation."""
    if not url or not project_num:
        return ""
    
    # Try to extract up to the project folder level
    try:
        parts = url.split('/')
        for i, part in enumerate(parts):
            if project_num in part:
                # Return URL up to this project folder
                return '/'.join(parts[:i+1])
    except:
        pass
    
    return url

def extract_project_folder(path: str, project_num: str) -> str:
    """Extract project folder path for SuiteFiles navigation."""
    if not path or not project_num:
        return ""
    
    # Look for pattern like "Projects/220/220294" and return "220/220294"
    match = re.search(rf'Projects/(\d+/\d*{re.escape(project_num)}\d*)', path, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Look for pattern like "Projects/222/222079" 
    match = re.search(r'Projects/(\d+)/(\d+)', path, re.IGNORECASE)
    if match:
        main_folder = match.group(1)
        sub_folder = match.group(2)
        return f"{main_folder}/{sub_folder}"
    
    # Look for any project folder pattern
    match = re.search(r'Projects/(\d+)', path, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Fallback: just return the project number
    return project_num

def extract_main_project_folder(project_num: str) -> str:
    """Extract main project folder (3-digit) from project number."""
    if not project_num or project_num == "Unknown":
        return ""
    
    # If it's already 3 digits, return as is
    if len(project_num) == 3 and project_num.isdigit():
        return project_num
    
    # If it's longer (like 220294), extract first 3 digits
    if len(project_num) >= 3 and project_num.isdigit():
        return project_num[:3]
    
    # Look for 3-digit pattern in the string
    match = re.search(r'(\d{3})', project_num)
    if match:
        return match.group(1)
    
    return project_num

if __name__ == "__main__":
    print("🔍 DTCE Precast Panel Project Search")
    print("Searching for projects containing: Precast Panel, Precast, Precast Connection, Unispans")
    print()
    
    asyncio.run(search_precast_projects())
