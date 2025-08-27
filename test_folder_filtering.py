#!/usr/bin/env python3
"""Test folder filtering logic for safety rules query."""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from dtce_ai_bot.services.folder_structure_service import FolderStructureService

def test_safety_rules_filtering():
    """Test that 'show me our safety rules' gets proper folder filtering."""
    
    folder_service = FolderStructureService()
    
    # Test the query that's causing issues
    question = "show me our safety rules"
    
    print(f"Testing question: '{question}'")
    print("="*50)
    
    # Get folder context
    folder_context = folder_service.interpret_user_query(question)
    
    print("Folder Context Analysis:")
    print(f"  Query Type: {folder_context['query_type']}")
    print(f"  Suggested Folders: {folder_context['suggested_folders']}")
    print(f"  Enhanced Search Terms: {folder_context['enhanced_search_terms']}")
    print(f"  Folder Context: {folder_context['folder_context']}")
    
    # Get the folder filter
    folder_filter = folder_service.get_folder_filter_query(folder_context)
    
    print(f"\nGenerated Folder Filter:")
    print(f"  {folder_filter}")
    
    # Test that this should exclude Projects folders
    if folder_filter and "not search.ismatch('Projects/', 'blob_name')" in folder_filter:
        print("\n✅ SUCCESS: Filter correctly excludes Projects folders")
    else:
        print("\n❌ FAILURE: Filter does not exclude Projects folders")
        
    print("\nExpected behavior:")
    print("  - Should detect query_type='policy'")
    print("  - Should search only in Health & Safety folder")
    print("  - Should exclude ALL Projects folders")
    print("  - Should NOT return documents from /Projects/219/219232/...")

if __name__ == "__main__":
    test_safety_rules_filtering()
