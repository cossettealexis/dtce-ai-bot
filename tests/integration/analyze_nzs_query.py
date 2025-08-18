#!/usr/bin/env python3
"""
Test script to analyze why the NZ structural code query is being misrouted.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def analyze_nzs_query():
    """Analyze why the NZ structural code query is being misrouted."""
    
    # The problematic query
    query = "tell me what particular nzs structural code to refer with if im designing a composite slab to make it as a floor diaphragm"
    
    print("🔍 Analyzing NZ Structural Code Query Routing")
    print("=" * 60)
    print(f"Query: {query}")
    print("=" * 60)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        # Check routing logic
        is_keyword_query = qa_service._is_project_keyword_query(query)
        is_nz_standards_query = qa_service._is_nz_standards_query(query)
        
        print(f"✅ Detected as keyword project query: {is_keyword_query}")
        print(f"✅ Detected as NZ standards query: {is_nz_standards_query}")
        
        # Extract keywords
        keywords = qa_service._extract_keywords_from_question(query)
        print(f"📋 Extracted keywords: {keywords}")
        
        print("\n🔍 Routing Analysis:")
        if is_nz_standards_query:
            print("   → Should route to NZ Standards handler")
        elif is_keyword_query:
            print("   → Routing to keyword project search (PROBLEM!)")
        else:
            print("   → Should route to general document search")
            
        print("\n🧠 Why is this happening?")
        
        # Let's examine the detection logic more closely
        question_lower = query.lower()
        
        # Check NZ standards detection
        print("\n📊 NZ Standards Detection Analysis:")
        nz_standards_terms = ["nzs", "new zealand standard", "standard", "code", "as/nzs", "building code"]
        found_nz_terms = [term for term in nz_standards_terms if term in question_lower]
        print(f"   NZ/Standards terms found: {found_nz_terms}")
        
        # Check keyword project detection components
        print("\n📊 Keyword Project Detection Analysis:")
        
        # Engineering keywords
        engineering_keywords = [
            "precast", "timber", "concrete", "steel", "retaining wall", "foundation", 
            "structural", "engineering", "slab", "floor", "beam", "column"
        ]
        found_eng_keywords = [kw for kw in engineering_keywords if kw in question_lower]
        print(f"   Engineering keywords found: {found_eng_keywords}")
        
        # Project/work terms
        project_patterns = [
            "project", "job", "work", "contract", "site", "construction",
            "past", "previous", "historical", "archive", "record"
        ]
        found_project_terms = [term for term in project_patterns if term in question_lower]
        print(f"   Project context terms found: {found_project_terms}")
        
        # Intent terms
        intent_patterns = [
            "tell me", "show me", "find", "search", "list", "all",
            "what", "which", "where", "give me", "provide", "display"
        ]
        found_intent_terms = [term for term in intent_patterns if term in question_lower]
        print(f"   Intent terms found: {found_intent_terms}")
        
        # Multiple indicators
        multiple_indicators = ["all", "any", "every", "what", "which"]
        found_multiple_terms = [term for term in multiple_indicators if term in question_lower]
        print(f"   Multiple indicator terms found: {found_multiple_terms}")
        
        print(f"\n🎯 Expected Behavior:")
        print(f"   This query asks for specific NZ structural codes/standards")
        print(f"   It should be routed to NZ Standards handler, not project search")
        print(f"   The user wants technical code references, not past projects")
        
        # Test the actual response
        print(f"\n🤖 Actual AI Response:")
        try:
            result = await qa_service.answer_question(query)
            print(f"   Answer preview: {result['answer'][:200]}...")
            print(f"   Confidence: {result['confidence']}")
            print(f"   Documents searched: {result['documents_searched']}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    except Exception as e:
        print(f"❌ Failed to analyze: {e}")

if __name__ == "__main__":
    asyncio.run(analyze_nzs_query())
