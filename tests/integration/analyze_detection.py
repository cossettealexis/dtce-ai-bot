#!/usr/bin/env python3
"""
Analyze how query detection works and test different phrasings.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def analyze_query_detection():
    """Show how different phrasings trigger different handlers."""
    
    # Same question asked in different ways
    test_queries = [
        # NZ Standards questions
        "What NZS code should I use for composite slabs?",
        "Tell me about NZ structural standards for slabs",
        "nzs structural code for composite design",
        "I need the building code requirements",
        
        # Project search questions  
        "Show me past projects with timber",
        "What timber projects has DTCE done?",
        "Find all steel projects",
        "timber construction work",
        
        # Web search questions
        "Look for online discussions about timber design",
        "Find forum threads about steel connections", 
        "Search for external resources on concrete",
        "I want public references for design",
        
        # General questions (should be normal search)
        "How do I design a timber beam?",
        "What is the load capacity of this beam?",
        "Explain composite beam design",
        "Structural analysis procedures"
    ]
    
    print("🔍 Query Detection Analysis")
    print("=" * 80)
    print("This shows how different phrasings trigger different response types")
    print("=" * 80)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n📋 Query {i}: {query}")
            print("-" * 50)
            
            # Check all detection methods
            is_web_search = qa_service._is_web_search_query(query)
            is_nz_standards = qa_service._is_nz_standards_query(query)
            is_keyword_project = qa_service._is_project_keyword_query(query)
            
            print(f"🌐 Web Search Query: {is_web_search}")
            print(f"📜 NZ Standards Query: {is_nz_standards}")
            print(f"📁 Keyword Project Query: {is_keyword_project}")
            
            # Show which handler would be used
            if is_web_search:
                handler = "🌐 Web Search Handler"
            elif is_nz_standards:
                handler = "📜 NZ Standards Handler" 
            elif is_keyword_project:
                handler = "📁 Project Search Handler"
            else:
                handler = "📄 General Document Search"
                
            print(f"🎯 Route: {handler}")
            
            # Show why it was detected this way
            keywords = qa_service._extract_keywords_from_question(query)
            print(f"🔑 Keywords: {keywords}")
            
        print(f"\n" + "=" * 80)
        print(f"🤔 THE PROBLEM:")
        print(f"   Users need to use very specific words to trigger the right handler")
        print(f"   This is confusing and not user-friendly!")
        print(f"\n💡 BETTER APPROACH:")
        print(f"   Use AI to intelligently classify the user's intent")
        print(f"   Then route to the appropriate handler")
        print(f"   This way users can ask naturally!")
    
    except Exception as e:
        print(f"❌ Failed to analyze: {e}")

if __name__ == "__main__":
    asyncio.run(analyze_query_detection())
