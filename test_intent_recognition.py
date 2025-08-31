#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

from dtce_ai_bot.services.intent_recognition import IntentRecognitionService, QueryIntent

def test_dtce_intent_recognition():
    """Test the new DTCE-specific intent recognition system."""
    
    intent_service = IntentRecognitionService()
    
    print("🧠 Testing DTCE Intent Recognition System")
    print("=" * 60)
    
    # Test queries for each intent type
    test_queries = [
        # Policy queries
        "what's our wellness policy",
        "wellness policy",
        "h&s policy requirements",
        "employee safety policy",
        "IT policy for remote work",
        
        # Technical procedure queries
        "how to use wind speed spreadsheet",
        "h2h procedure for site analysis",
        "how do i calculate loads",
        "procedure for design check",
        "best practice for structural analysis",
        
        # NZ Standards queries
        "nzs 3404 steel design",
        "building code requirements",
        "nz standard for concrete",
        "seismic design standard",
        
        # Project reference queries
        "past projects with precast panels",
        "similar project to residential building",
        "project example for bridge design",
        "past work on schools",
        
        # Client reference queries
        "client contact details",
        "projects with ABC company",
        "client phone number",
        "past work for ministry of education"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        
        result = intent_service.classify_intent(query)
        strategy = intent_service.get_search_strategy(result)
        
        print(f"   🎯 Intent: {result['intent'].value}")
        print(f"   📊 Confidence: {result['confidence']:.2f}")
        print(f"   🔍 Strategy: {strategy['search_type']}")
        print(f"   📂 Folders: {strategy.get('folder_filters', [])}")
        print(f"   📄 Doc Types: {strategy.get('document_types', [])}")
        print(f"   ℹ️  Description: {strategy['description']}")
        
        # Highlight high-confidence classifications
        if result['confidence'] > 0.8:
            print("   ✅ HIGH CONFIDENCE - Will use targeted search")
        elif result['confidence'] > 0.6:
            print("   ⚠️  MEDIUM CONFIDENCE - Will use light targeting")
        else:
            print("   ❌ LOW CONFIDENCE - Will use general search")

if __name__ == "__main__":
    test_dtce_intent_recognition()
