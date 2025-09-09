#!/usr/bin/env python3
"""
Test the 5 DTCE prompt categories
"""
import asyncio
import sys
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.config import get_config

async def test_5_prompt_categories():
    """Test each of the 5 DTCE prompt categories"""
    config = get_config()
    rag_handler = RAGHandler(config)
    
    # Test questions for each category
    test_cases = [
        ("Policy Prompt", "What is DTCE's health and safety policy?"),
        ("Procedures Prompt", "How do I use the wind speed spreadsheet?"),
        ("NZ Standards Prompt", "What are the NZS 3101 requirements for concrete design?"),
        ("Project Reference", "Show me past precast concrete projects DTCE has done"),
        ("Client Reference", "What projects has DTCE done for ABC Construction?"),
        ("General Engineering", "How do you design a reinforced concrete beam?")
    ]
    
    print("=== Testing 5 DTCE Prompt Categories ===\n")
    
    for category, question in test_cases:
        print(f"🏷️  CATEGORY: {category}")
        print(f"❓ QUESTION: {question}")
        print("-" * 60)
        
        try:
            # Test just the routing logic first
            strategy = await rag_handler._determine_search_strategy(question)
            
            print(f"🎯 DETECTED CATEGORY: {strategy.get('prompt_category')}")
            print(f"🔍 NEEDS DTCE SEARCH: {strategy.get('needs_dtce_search')}")
            print(f"📁 SEARCH FOLDERS: {strategy.get('search_folders', [])}")
            print(f"💭 REASONING: {strategy.get('reasoning')}")
            print(f"🎯 CONFIDENCE: {strategy.get('confidence')}")
            
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
        
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_5_prompt_categories())
