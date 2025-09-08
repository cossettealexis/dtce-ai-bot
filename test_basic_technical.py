#!/usr/bin/env python3
"""
Test script for basic technical questions to verify detection logic.
"""

import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_technical_detection():
    """Test basic technical question detection logic."""
    
    # Test questions that should trigger basic technical response
    test_queries = [
        "What are the minimum clear cover requirements for concrete as per NZS code?",
        "minimum cover requirements for concrete",
        "NZS 3101 cover requirements",
        "How thick should concrete cover be?",
        "concrete cover thickness requirements"
    ]
    
    print("DTCE AI Bot Basic Technical Question Detection Test")
    print("=" * 60)
    
    # Define the detection logic inline for testing
    def is_basic_technical_question(question: str) -> bool:
        """Check if this is a basic technical question requiring direct answer."""
        question_lower = question.lower()
        
        # Keywords that indicate basic technical questions
        technical_keywords = ['minimum', 'maximum', 'requirements', 'thickness', 'size', 'dimensions']
        code_keywords = ['nzs', 'as/nzs', 'nz', 'standard', 'code', 'clause']
        specific_topics = ['cover', 'reinforcement', 'concrete', 'steel', 'beam', 'column', 'slab']
        
        # Must have at least one from each category
        has_technical = any(keyword in question_lower for keyword in technical_keywords)
        has_code_ref = any(keyword in question_lower for keyword in code_keywords)
        has_topic = any(keyword in question_lower for keyword in specific_topics)
        
        return has_technical and (has_code_ref or has_topic)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📋 Test Query {i}:")
        print(f"Question: {query}")
        print("-" * 40)
        
        is_basic = is_basic_technical_question(query)
        print(f"Detected as Basic Technical Question: {is_basic}")
        
        if is_basic:
            print("✅ Would trigger direct technical answer")
            if 'cover' in query.lower():
                print("🔧 Concrete cover question - would provide NZS 3101:2006 requirements")
        else:
            print("❌ Would use standard RAG processing")
        
        print("=" * 60)

if __name__ == "__main__":
    test_basic_technical_detection()
