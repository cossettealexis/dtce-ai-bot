#!/usr/bin/env python3
"""
Test synonym detection and semantic expansion in the smart routing system.
Tests that the system can handle synonyms and related terms, not just exact keywords.
"""
import asyncio
import sys
import os
from typing import Dict, List
from dotenv import load_dotenv

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.integrations.azure_search import get_search_client
from dtce_ai_bot.services.smart_rag_handler import SmartRAGHandler
from openai import AsyncAzureOpenAI

# Load environment variables
load_dotenv()


async def test_synonym_detection():
    """Test that the system can handle synonyms and related terms."""
    
    # Initialize the smart RAG handler
    settings = get_settings()
    search_client = get_search_client()
    
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    smart_rag = SmartRAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
    
    # Test synonym queries that should be detected correctly
    synonym_test_cases = {
        "policy": [
            # Wellness synonyms
            ("What are our wellbeing guidelines?", "policy"),  # wellbeing vs wellness
            ("Show me employee health rules", "policy"),        # rules vs policy
            ("Company mental health regulations", "policy"),    # regulations vs policy
            ("What's our workplace conduct code?", "policy"),   # conduct code vs policy
            
            # Safety synonyms  
            ("Occupational safety guidelines", "policy"),       # occupational vs workplace
            ("Health and safety rules", "policy"),             # rules vs policy
            ("Safe work practices", "policy"),                 # practices vs policy
            
            # Privacy synonyms
            ("Data protection guidelines", "policy"),          # guidelines vs policy
            ("Personal information rules", "policy"),          # personal info vs privacy
            ("Confidentiality regulations", "policy")          # confidentiality vs privacy
        ],
        
        "procedure": [
            # Leave synonyms
            ("How to request time off?", "procedure"),          # time off vs leave
            ("Steps to apply for vacation", "procedure"),       # vacation vs leave
            ("Holiday request process", "procedure"),           # holiday vs leave
            ("Sick day application method", "procedure"),       # method vs procedure
            
            # Expense synonyms
            ("Reimbursement claim steps", "procedure"),         # reimbursement vs expense
            ("Cost recovery process", "procedure"),             # cost recovery vs expense
            ("How to get money back?", "procedure"),            # money back vs expense claim
            
            # Hiring synonyms
            ("Recruitment process", "procedure"),               # recruitment vs hiring
            ("How to employ new staff?", "procedure"),          # employ vs hire
            ("Staff onboarding steps", "procedure"),            # onboarding vs hiring
            
            # Incident synonyms
            ("Accident reporting guide", "procedure"),          # accident vs incident
            ("How to report problems?", "procedure"),           # problems vs incidents
            ("Emergency response steps", "procedure")           # emergency vs incident
        ],
        
        "standard": [
            # Quality synonyms
            ("QA requirements", "standard"),                    # QA vs quality standard
            ("Quality control specs", "standard"),              # specs vs standards
            ("Excellence criteria", "standard"),                # excellence vs quality
            
            # Building synonyms
            ("Construction codes", "standard"),                 # construction vs building
            ("Structural requirements", "standard"),            # structural vs building
            ("Engineering specifications", "standard"),         # specifications vs standards
            
            # Compliance synonyms
            ("Regulatory requirements", "standard"),            # regulatory vs compliance
            ("What codes must we follow?", "standard"),         # codes vs standards
            ("Certification criteria", "standard")              # certification vs standards
        ],
        
        "project": [
            # Location synonyms
            ("Auckland city center development", "project"),    # city center vs CBD
            ("Harbour construction work", "project"),           # harbour vs waterfront
            ("Capital city projects", "project"),               # capital vs Wellington
            
            # Building synonyms
            ("Medical facility construction", "project"),       # medical facility vs hospital
            ("Educational building work", "project"),           # educational vs school
            ("Apartment development", "project"),               # apartment vs residential
            
            # Infrastructure synonyms
            ("Road construction projects", "project"),          # road vs roadway
            ("Transport infrastructure", "project"),            # transport vs infrastructure
            ("Utilities development", "project")                # utilities vs infrastructure
        ],
        
        "client": [
            # Client synonyms
            ("Customer contact details", "client"),             # customer vs client
            ("Stakeholder information", "client"),              # stakeholder vs client
            ("Partner organization", "client"),                 # partner vs client
            
            # Contact synonyms
            ("Representative details", "client"),               # representative vs contact
            ("Liaison information", "client"),                  # liaison vs contact
            ("Point of contact", "client"),                     # point of contact vs contact
            
            # Government synonyms
            ("Council correspondence", "client"),               # council vs government
            ("Public sector clients", "client"),                # public sector vs government
            ("Ministry contact", "client")                      # ministry vs government
        ]
    }
    
    print("🔍 SYNONYM DETECTION TEST")
    print("=" * 80)
    print("Testing that the system detects synonyms and related terms correctly...")
    print("=" * 80)
    
    total_tests = 0
    correct_detections = 0
    
    for expected_intent, test_queries in synonym_test_cases.items():
        print(f"\n📋 Testing {expected_intent.upper()} synonyms:")
        print("-" * 50)
        
        for query, expected in test_queries:
            total_tests += 1
            
            try:
                # Test intent detection
                routing_info = await smart_rag.query_router.route_query(query)
                detected_intent = routing_info["intent"]
                
                if detected_intent == expected:
                    correct_detections += 1
                    status = "✅"
                else:
                    status = "❌"
                
                print(f"  {status} '{query}'")
                print(f"     Expected: {expected} | Detected: {detected_intent}")
                
                # Show enhanced keywords to see synonym expansion
                keywords = routing_info.get("enhanced_keywords", [])
                if keywords:
                    print(f"     Keywords: {', '.join(keywords[:5])}")
                
            except Exception as e:
                print(f"  ❌ '{query}' → ERROR: {e}")
        
    # Calculate accuracy
    accuracy = (correct_detections / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"\n" + "="*80)
    print(f"📊 SYNONYM DETECTION RESULTS:")
    print(f"Total Tests: {total_tests}")
    print(f"Correct Detections: {correct_detections}")
    print(f"Accuracy: {accuracy:.1f}%")
    
    if accuracy >= 90:
        print("✅ EXCELLENT: Synonym detection is working great!")
    elif accuracy >= 75:
        print("✅ GOOD: Synonym detection is working well")
    elif accuracy >= 60:
        print("⚠️  FAIR: Synonym detection needs improvement")
    else:
        print("❌ POOR: Synonym detection needs major work")
    
    print("="*80)
    
    # Test a few actual searches to see if synonyms improve results
    print("\n🔍 TESTING SYNONYM-ENHANCED SEARCH RESULTS:")
    print("-" * 50)
    
    search_test_queries = [
        "wellbeing guidelines",  # should find wellness policy
        "time off request",      # should find leave procedure  
        "QA requirements",       # should find quality standards
        "harbour project",       # should find waterfront project
        "customer contact"       # should find client information
    ]
    
    for query in search_test_queries:
        try:
            response = await smart_rag.get_answer(query)
            answer = response.get("answer", "No answer") if isinstance(response, dict) else str(response)
            intent = response.get("intent", "unknown") if isinstance(response, dict) else "unknown"
            sources = response.get("sources", []) if isinstance(response, dict) else []
            
            print(f"\n📄 Query: '{query}'")
            print(f"   Intent: {intent}")
            print(f"   Sources found: {len(sources)}")
            print(f"   Answer preview: {answer[:100]}...")
            
        except Exception as e:
            print(f"\n❌ Query: '{query}' → ERROR: {e}")


async def main():
    """Run synonym detection tests."""
    await test_synonym_detection()


if __name__ == "__main__":
    asyncio.run(main())
