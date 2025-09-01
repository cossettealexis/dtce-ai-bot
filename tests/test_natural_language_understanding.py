#!/usr/bin/env python3
"""
Test Natural Language Understanding - Different ways to ask similar questions
"""

import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

from dtce_ai_bot.services.smart_query_router import SmartQueryRouter
from dtce_ai_bot.services.semantic_search_new import SemanticSearchService
from dtce_ai_bot.services.smart_rag_handler import SmartRAGHandler

# Load environment variables
load_dotenv()

async def test_natural_language_variations():
    """Test how the system handles different ways of asking similar questions"""
    
    # Setup clients
    openai_client = AsyncAzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-01",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    
    search_client = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
    )
    
    # Initialize services
    router = SmartQueryRouter(openai_client)
    search_service = SemanticSearchService(search_client, openai_client)
    rag_handler = SmartRAGHandler(search_client, openai_client, "gpt-4")
    
    # Test queries that mean the same thing but use different words
    test_queries = [
        # WELLNESS/POLICY variations
        {
            "category": "Wellness Policy (Different Phrasings)",
            "queries": [
                "What's our wellness policy?",           # Original exact match
                "How do we handle employee wellbeing?",  # Synonym variation
                "What's the company approach to mental health?",  # Different terms
                "Show me policies about work-life balance",  # Related concept
                "How do we support staff stress management?",  # Conceptually similar
                "What are the rules for employee wellness?",  # Different structure
                "Tell me about our wellnes policy",      # Typo test
                "Employee health and safety guidelines", # Different phrasing
                "What support do we offer for burnout?"  # Related but different words
            ]
        },
        
        # PROCEDURE variations  
        {
            "category": "Leave Request (Different Phrasings)",
            "queries": [
                "How do I request leave?",               # Standard phrasing
                "What's the process for time off?",     # Synonym
                "Steps to apply for vacation",          # Different structure
                "How can I get holiday approval?",      # Different terms
                "What's the procedure for sick leave?", # Specific type
                "How to submit annual leave request",   # Different format
                "Process for taking days off",          # Casual phrasing
                "Guide to requesting absence",          # Formal phrasing
                "How do I book time away from work?"    # Very casual
            ]
        },
        
        # ENGINEERING STANDARDS variations
        {
            "category": "Engineering Standards (Different Phrasings)", 
            "queries": [
                "What are the NZS standards for concrete?",  # Exact technical
                "New Zealand building codes for steel",      # Different phrasing
                "Structural engineering requirements",        # Conceptual
                "Building compliance standards",             # Related terms
                "What codes do we follow for construction?", # Question format
                "Engineering specifications and rules",      # Different terms
                "Technical standards for building design",   # Professional phrasing
                "Construction regulations and guidelines",   # Regulatory focus
                "What structural codes are required?"        # Question structure
            ]
        },
        
        # PROJECT variations
        {
            "category": "Project Information (Different Phrasings)",
            "queries": [
                "Tell me about the Auckland waterfront project",  # Specific location
                "What work have we done at the harbour?",        # Different location term
                "Show me marina development projects",            # Related concept
                "Auckland CBD construction work",                # Different phrasing
                "Waterfront building projects in Auckland",      # Restructured
                "What projects near Auckland harbour?",          # Question format
                "Commercial developments on the waterfront",     # Specific type
                "Infrastructure work at Auckland marina",        # Different focus
                "Tell me about coastal projects in Auckland"     # Conceptually related
            ]
        }
    ]
    
    print("🧠 TESTING NATURAL LANGUAGE UNDERSTANDING")
    print("=" * 60)
    print("Testing how the system handles different ways to ask similar questions...")
    print()
    
    for test_group in test_queries:
        print(f"📝 {test_group['category']}")
        print("-" * 50)
        
        routing_results = []
        
        for i, query in enumerate(test_group['queries'], 1):
            try:
                # Test routing
                routing = await router.route_query(query)
                intent = routing.get('intent', 'unknown')
                folder = routing.get('folder', 'none')
                keywords = routing.get('enhanced_keywords', [])
                
                routing_results.append({
                    'query': query,
                    'intent': intent,
                    'folder': folder,
                    'keywords': keywords[:5]  # Show first 5 keywords
                })
                
                print(f"{i:2d}. '{query}'")
                print(f"    → Intent: {intent} | Folder: {folder}")
                print(f"    → Keywords: {', '.join(keywords[:5])}")
                print()
                
            except Exception as e:
                print(f"{i:2d}. '{query}' → ERROR: {e}")
                print()
        
        # Analyze consistency
        intents = [r['intent'] for r in routing_results]
        unique_intents = set(intents)
        
        print(f"🎯 CONSISTENCY ANALYSIS:")
        print(f"   • Unique intents detected: {len(unique_intents)}")
        print(f"   • Intents: {', '.join(unique_intents)}")
        
        if len(unique_intents) == 1:
            print(f"   ✅ PERFECT: All queries routed to same intent ({list(unique_intents)[0]})")
        else:
            print(f"   ⚠️  MIXED: Queries routed to different intents")
            for intent in unique_intents:
                count = intents.count(intent)
                percentage = (count / len(intents)) * 100
                print(f"      - {intent}: {count}/{len(intents)} queries ({percentage:.1f}%)")
        
        print("\n" + "="*60 + "\n")
    
    # Test with some really challenging variations
    print("🎯 CHALLENGING TEST CASES")
    print("-" * 50)
    
    challenging_queries = [
        "How can our team members improve their mental wellness at work?",  # Should → policy
        "What's the step-by-step guide for getting vacation approved?",     # Should → procedure  
        "Which New Zealand engineering codes apply to our building work?",  # Should → standard
        "What infrastructure projects have we completed in the capital?",   # Should → project
        "I need info about our wellnes aproach",                          # Typos + casual
        "Steps for submiting expense clames",                              # Multiple typos
        "Show me the proceedures for emrgency evacation",                 # Multiple typos
        "Engineering standrd for steeel construction"                      # Technical + typos
    ]
    
    for i, query in enumerate(challenging_queries, 1):
        try:
            routing = await router.route_query(query)
            intent = routing.get('intent', 'unknown')
            folder = routing.get('folder', 'none')
            
            print(f"{i}. '{query}'")
            print(f"   → Intent: {intent} | Folder: {folder}")
            print()
            
        except Exception as e:
            print(f"{i}. '{query}' → ERROR: {e}")
            print()

if __name__ == "__main__":
    asyncio.run(test_natural_language_variations())
