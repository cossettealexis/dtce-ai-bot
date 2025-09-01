#!/usr/bin/env python3
"""
Test Natural Language Understanding - Router Logic Only
"""

import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

from dtce_ai_bot.services.smart_query_router import SmartQueryRouter

# Load environment variables
load_dotenv()

async def test_router_understanding():
    """Test how the router handles different ways of asking similar questions"""
    
    # Setup OpenAI client (only need this for AI fallback)
    openai_client = AsyncAzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-01", 
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    
    # Initialize router
    router = SmartQueryRouter(openai_client)
    
    # Test queries that mean the same thing but use different words
    test_groups = [
        {
            "category": "🌟 WELLNESS/WELLBEING (Should all route to 'policy')",
            "queries": [
                "What's our wellness policy?",           # Exact keyword match
                "How do we handle employee wellbeing?",  # Synonym variation  
                "What's the company approach to mental health?",  # Related concept
                "Show me policies about work-life balance",  # Different phrasing
                "How do we support staff stress management?",  # Conceptually similar
                "What are the rules for employee wellness?",  # Different structure
                "Tell me about our welnes policy",      # Typo test
                "Employee health and safety guidelines", # Different but related
                "What support do we offer for burnout?", # Related concept
                "How can I improve my mental wellness at work?"  # Natural language
            ]
        },
        
        {
            "category": "📋 LEAVE REQUESTS (Should all route to 'procedure')",
            "queries": [
                "How do I request leave?",               # Standard
                "What's the process for time off?",     # Synonym
                "Steps to apply for vacation",          # Different structure
                "How can I get holiday approval?",      # Different terms
                "What's the procedure for sick leave?", # Specific type
                "How to submit annual leave request",   # Different format
                "Process for taking days off",          # Casual
                "Guide to requesting absence",          # Formal
                "How do I book time away from work?",   # Very casual
                "Steps for submiting vacation clame"    # With typos
            ]
        },
        
        {
            "category": "🏗️ ENGINEERING STANDARDS (Should all route to 'standard')",
            "queries": [
                "What are the NZS standards for concrete?",     # Technical exact
                "New Zealand building codes for steel",         # Different phrasing
                "Structural engineering requirements",           # Conceptual
                "Building compliance standards",                # Related terms
                "What codes do we follow for construction?",    # Question format
                "Engineering specifications and rules",         # Different terms
                "Technical standards for building design",      # Professional
                "Construction regulations and guidelines",      # Regulatory focus
                "What structural codes are required?",          # Question structure
                "NZ standrd for steeel construction"            # With typos
            ]
        }
    ]
    
    print("🧠 TESTING NATURAL LANGUAGE UNDERSTANDING")
    print("=" * 70)
    print("Testing how the smart router handles different ways to ask similar questions...")
    print()
    
    for test_group in test_groups:
        print(test_group['category'])
        print("-" * 60)
        
        routing_results = []
        
        for i, query in enumerate(test_group['queries'], 1):
            try:
                # Test routing
                routing = await router.route_query(query)
                intent = routing.get('intent', 'unknown')
                folder = routing.get('folder', 'none')
                normalized = routing.get('normalized_query', query)
                
                routing_results.append({
                    'query': query,
                    'intent': intent,
                    'folder': folder,
                    'normalized': normalized
                })
                
                # Color coding for results
                if intent == 'policy':
                    icon = "🟢"
                elif intent == 'procedure':
                    icon = "🔵"  
                elif intent == 'standard':
                    icon = "🟡"
                elif intent == 'project':
                    icon = "🟠"
                elif intent == 'client':
                    icon = "🟣"
                else:
                    icon = "🔴"
                
                print(f"{i:2d}. {icon} '{query}'")
                print(f"     → Intent: {intent} | Folder: {folder}")
                if normalized != query.lower().strip():
                    print(f"     → Normalized: '{normalized}'")
                print()
                
            except Exception as e:
                print(f"{i:2d}. 🔴 '{query}' → ERROR: {e}")
                print()
        
        # Analyze consistency
        intents = [r['intent'] for r in routing_results]
        unique_intents = set(intents)
        
        print(f"📊 CONSISTENCY ANALYSIS:")
        print(f"   • Total queries: {len(routing_results)}")
        print(f"   • Unique intents: {len(unique_intents)} → {', '.join(unique_intents)}")
        
        if len(unique_intents) == 1:
            print(f"   ✅ PERFECT CONSISTENCY: All queries → {list(unique_intents)[0]}")
        else:
            print(f"   ⚠️  MIXED ROUTING:")
            for intent in unique_intents:
                count = intents.count(intent)
                percentage = (count / len(intents)) * 100
                print(f"      • {intent}: {count}/{len(intents)} queries ({percentage:.1f}%)")
        
        print("\n" + "="*70 + "\n")
    
    # Test really challenging cases
    print("🎯 EXTREME CHALLENGE TEST CASES")
    print("-" * 60)
    
    challenging_cases = [
        {
            "query": "How can our team members improve their mental wellness at work?", 
            "expected": "policy",
            "reason": "Complex wellness question with natural language"
        },
        {
            "query": "What's the step-by-step guide for getting vacation approved?",
            "expected": "procedure", 
            "reason": "Complex procedure question with natural phrasing"
        },
        {
            "query": "Which New Zealand engineering codes apply to our building work?",
            "expected": "standard",
            "reason": "Complex standards question with natural language"
        },
        {
            "query": "I need info about our wellnes aproach with typos everywher",
            "expected": "policy",
            "reason": "Multiple typos + casual language"
        },
        {
            "query": "Steps for submiting expense clames and reimbursment",
            "expected": "procedure", 
            "reason": "Multiple typos in procedure question"
        },
        {
            "query": "Show me the proceedures for emrgency evacation plans",
            "expected": "procedure",
            "reason": "Emergency procedure with multiple typos"
        },
        {
            "query": "Engineering standrd for steeel construction in nz",
            "expected": "standard",
            "reason": "Technical standards with multiple typos"
        }
    ]
    
    correct_predictions = 0
    
    for i, case in enumerate(challenging_cases, 1):
        try:
            routing = await router.route_query(case['query'])
            predicted_intent = routing.get('intent', 'unknown')
            expected_intent = case['expected']
            
            is_correct = predicted_intent == expected_intent
            if is_correct:
                correct_predictions += 1
                icon = "✅"
            else:
                icon = "❌"
            
            print(f"{i}. {icon} '{case['query']}'")
            print(f"   Expected: {expected_intent} | Predicted: {predicted_intent}")
            print(f"   Reason: {case['reason']}")
            print()
            
        except Exception as e:
            print(f"{i}. 🔴 '{case['query']}' → ERROR: {e}")
            print()
    
    accuracy = (correct_predictions / len(challenging_cases)) * 100
    print(f"🎯 CHALLENGE TEST ACCURACY: {correct_predictions}/{len(challenging_cases)} = {accuracy:.1f}%")
    
    if accuracy >= 80:
        print("✅ EXCELLENT: System handles natural language very well!")
    elif accuracy >= 60:
        print("🟡 GOOD: System handles most natural language cases")
    else:
        print("❌ NEEDS IMPROVEMENT: Natural language understanding needs work")

if __name__ == "__main__":
    asyncio.run(test_router_understanding())
