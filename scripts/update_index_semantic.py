#!/usr/bin/env python3
"""
Script to update the existing Azure Search index with semantic search configuration.
This script will add semantic search capabilities to the existing index.
"""

import asyncio
from dtce_ai_bot.integrations.azure_search import create_search_index_if_not_exists
from dtce_ai_bot.config.settings import get_settings

async def update_index_with_semantic():
    """Update the existing index with semantic search configuration."""
    
    print("🔄 Updating Azure Search Index with Semantic Configuration")
    print("=" * 60)
    
    try:
        settings = get_settings()
        print(f"📊 Updating index: {settings.azure_search_index_name}")
        print("🧠 Adding semantic search configuration...")
        
        # This will update the existing index with semantic configuration
        await create_search_index_if_not_exists()
        
        print("✅ Index updated successfully with semantic search!")
        print("\n🔍 Semantic search features now enabled:")
        print("  • Better similarity matching")
        print("  • Context understanding") 
        print("  • Natural language queries")
        print("  • Improved relevance scoring")
        
    except Exception as e:
        print(f"❌ Error updating index: {str(e)}")
        print("\n💡 Troubleshooting tips:")
        print("  • Check Azure Search service is running")
        print("  • Verify admin key is correct")
        print("  • Ensure you have 'Standard' tier or higher for semantic search")
        raise

if __name__ == "__main__":
    print("🧠 Azure Search Semantic Configuration Update")
    print("This will add semantic search capabilities to your existing index.")
    print("Semantic search requires Standard tier or higher.\n")
    
    # Ask for confirmation
    response = input("Continue with index update? (y/N): ")
    if response.lower() != 'y':
        print("Index update cancelled.")
        exit(0)
    
    asyncio.run(update_index_with_semantic())
