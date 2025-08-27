#!/usr/bin/env python3
"""Test the actual Azure Search filter that's being generated."""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from dtce_ai_bot.services.folder_structure_service import FolderStructureService

def test_azure_filter_syntax():
    """Test the Azure Search filter syntax."""
    
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
    
    # Get the folder filter
    folder_filter = folder_service.get_folder_filter_query(folder_context)
    
    print(f"\nGenerated Folder Filter:")
    print(f"  {folder_filter}")
    
    print(f"\nFilter Length: {len(folder_filter) if folder_filter else 0} characters")
    
    # Check if the filter looks suspicious
    if folder_filter:
        if len(folder_filter) > 2000:
            print("⚠️  WARNING: Filter is very long - might cause Azure Search issues")
        
        # Check for potential syntax issues
        and_count = folder_filter.count(' and ')
        or_count = folder_filter.count(' or ')
        paren_open = folder_filter.count('(')
        paren_close = folder_filter.count(')')
        
        print(f"\nFilter Analysis:")
        print(f"  AND clauses: {and_count}")
        print(f"  OR clauses: {or_count}")
        print(f"  Open parens: {paren_open}")
        print(f"  Close parens: {paren_close}")
        
        if paren_open != paren_close:
            print("❌ ERROR: Unbalanced parentheses!")
        
        # Check for specific folder matches
        policy_folders = ['Health & Safety', 'IT Policy', 'Employment', 'Quality', 'Operations']
        print(f"\nPolicy folder matching:")
        for folder in policy_folders:
            if folder in folder_filter:
                print(f"  ✅ {folder} - FOUND in filter")
            else:
                print(f"  ❌ {folder} - NOT FOUND in filter")

if __name__ == "__main__":
    test_azure_filter_syntax()
