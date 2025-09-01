#!/usr/bin/env python3
"""
Test Client/Contact Recognition and Project Mapping
"""

import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

from dtce_ai_bot.services.smart_query_router import SmartQueryRouter

# Load environment variables
load_dotenv()

async def test_client_recognition():
    """Test how the system handles client/contact queries with company names and people"""
    
    # Setup OpenAI client
    openai_client = AsyncAzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-01", 
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    
    # Initialize router
    router = SmartQueryRouter(openai_client)
    
    print("🏢 TESTING CLIENT/CONTACT RECOGNITION")
    print("=" * 60)
    print("Testing how the system handles queries about people and companies...")
    print()
    
    # Test the specific query you mentioned
    main_query = "is anyone working with aaron from tgcs"
    
    print(f"🎯 MAIN TEST QUERY:")
    print(f"   '{main_query}'")
    print()
    
    try:
        routing = await router.route_query(main_query)
        intent = routing.get('intent', 'unknown')
        folder = routing.get('folder', 'none')
        keywords = routing.get('enhanced_keywords', [])
        normalized = routing.get('normalized_query', main_query)
        
        if intent == 'client':
            icon = "🟣"
        elif intent == 'project':
            icon = "🟠"
        else:
            icon = "🔴"
            
        print(f"   {icon} Intent: {intent}")
        print(f"   📁 Folder: {folder}")
        print(f"   🔍 Keywords: {', '.join(keywords)}")
        print(f"   📝 Normalized: '{normalized}'")
        print()
        
    except Exception as e:
        print(f"   🔴 ERROR: {e}")
        print()
    
    # Test various client/contact recognition patterns
    test_queries = [
        # People + Company patterns
        "is anyone working with Aaron from TGCS?",
        "Who is working with Aaron from The George Construction Solution?", 
        "Are we doing work for TGCS?",
        "What projects do we have with The George Construction Solution?",
        "Contact details for Aaron at TGCS",
        "Email correspondence with TGCS",
        "Job numbers for The George Construction Solution",
        
        # Different company formats
        "Projects with Fletcher Building",
        "Who is our contact at Hawkins Construction?", 
        "Are we working with Fulton Hogan?",
        "What's the status of the NZTA work?",
        "Contact person at Wellington Council",
        "Projects for Auckland Transport",
        
        # Person-focused queries
        "Who is John Smith working with?",
        "What company does Sarah Jones represent?",
        "Contact details for Mike Wilson",
        "Email from David Brown about the project",
        
        # Project-relationship queries
        "Which client is for job number 2024-001?",
        "What company is the Waterfront project for?",
        "Who is the client for the Auckland CBD work?",
        "Contact person for the hospital project",
        
        # Abbreviation challenges
        "Work with AT (Auckland Transport)",
        "Projects for WCC (Wellington City Council)",
        "Contact at NZTA",
        "Are we working with KBC (Kiwi Building Company)?",
    ]
    
    print("🧪 COMPREHENSIVE CLIENT RECOGNITION TEST")
    print("-" * 60)
    
    client_queries = 0
    project_queries = 0
    other_queries = 0
    
    for i, query in enumerate(test_queries, 1):
        try:
            routing = await router.route_query(query)
            intent = routing.get('intent', 'unknown')
            folder = routing.get('folder', 'none')
            
            if intent == 'client':
                icon = "🟣"
                client_queries += 1
            elif intent == 'project':
                icon = "🟠"  
                project_queries += 1
            else:
                icon = "🔴"
                other_queries += 1
            
            print(f"{i:2d}. {icon} '{query}'")
            print(f"     → Intent: {intent} | Folder: {folder}")
            print()
            
        except Exception as e:
            print(f"{i:2d}. 🔴 '{query}' → ERROR: {e}")
            other_queries += 1
            print()
    
    total_queries = len(test_queries)
    print(f"📊 ROUTING ANALYSIS:")
    print(f"   • Total queries: {total_queries}")
    print(f"   • Client routing: {client_queries} ({(client_queries/total_queries)*100:.1f}%)")
    print(f"   • Project routing: {project_queries} ({(project_queries/total_queries)*100:.1f}%)")
    print(f"   • Other routing: {other_queries} ({(other_queries/total_queries)*100:.1f}%)")
    print()
    
    # Analyze what type of queries work best
    print("🔍 ANALYSIS:")
    if client_queries > project_queries:
        print("   ✅ System correctly identifies most queries as CLIENT-related")
    elif project_queries > client_queries:
        print("   ⚠️  System routes many client queries to PROJECT instead")
        print("      (This might actually be correct - depends on document structure)")
    else:
        print("   📊 Mixed routing between CLIENT and PROJECT")
    
    print()
    print("💡 RECOMMENDATIONS:")
    print("   1. CLIENT queries should find contact info and correspondence")
    print("   2. PROJECT queries should find project details and job numbers")
    print("   3. The system needs to recognize company abbreviations:")
    print("      • TGCS = The George Construction Solution")
    print("      • AT = Auckland Transport") 
    print("      • WCC = Wellington City Council")
    print("      • NZTA = New Zealand Transport Agency")
    print()
    print("   4. The system should extract:")
    print("      • Person names (Aaron, John Smith, etc.)")
    print("      • Company names (full and abbreviated)")
    print("      • Project addresses")
    print("      • Job numbers")
    print("      • Email correspondence")

if __name__ == "__main__":
    asyncio.run(test_client_recognition())
