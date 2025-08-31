#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('.')

from dtce_ai_bot.services.folder_structure_service import FolderStructureService

def test_query_enhancement():
    """Test that query enhancement doesn't dilute wellness policy searches."""
    
    folder_service = FolderStructureService()
    
    print("🔍 Testing Query Enhancement Fix")
    print("=" * 50)
    
    # Test the problematic queries
    queries = [
        "wellness policy",
        "what's our wellness policy", 
        "whats our wellness policy and what does it say"
    ]
    
    for query in queries:
        print(f"\n📝 Original Query: '{query}'")
        
        # Get folder context
        context = folder_service.interpret_user_query(query)
        
        # Get enhanced query
        enhanced = folder_service.enhance_search_query(query, context)
        
        print(f"   Enhanced Query: '{enhanced}'")
        print(f"   Query Type: {context['query_type']}")
        print(f"   Enhanced Terms: {context.get('enhanced_search_terms', [])}")
        
        # Check if enhancement is too aggressive
        original_words = len(query.split())
        enhanced_words = len(enhanced.split())
        ratio = enhanced_words / original_words
        
        if ratio > 2.0:
            print(f"   ⚠️  WARNING: Query expanded by {ratio:.1f}x - may dilute results")
        else:
            print(f"   ✅ Good: Query expansion ratio is {ratio:.1f}x")

if __name__ == "__main__":
    test_query_enhancement()
