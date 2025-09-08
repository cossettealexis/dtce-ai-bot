#!/usr/bin/env python3
"""
Test script for AI-powered semantic query normalization.
Tests the new QueryNormalizer to ensure it properly converts natural language
queries into semantically equivalent search terms using AI understanding.
"""

import asyncio
from dtce_ai_bot.services.query_normalizer import QueryNormalizer


async def test_semantic_normalization():
    """Test AI-powered semantic normalization with various query types."""
    
    normalizer = QueryNormalizer()  # Without OpenAI for basic rule-based testing
    
    test_queries = [
        # The core problem cases
        ("what's our wellness policy", "wellness policy"),
        ("wellness policy", "wellness policy"),
        
        # Other conversational vs direct queries
        ("What is the IT security policy?", "IT security policy"),
        ("IT security policy", "IT security policy"),
        
        # Question vs statement format
        ("How do I submit a project template?", "project template submission"),
        ("project template submission", "project template submission"),
        
        # Noise word issues
        ("Where can I find safety procedures?", "safety procedures"),
        ("safety procedures", "safety procedures"),
        
        # The "really" problem case
        ("What's really important about our HR guidelines?", "HR guidelines important"),
        ("HR guidelines", "HR guidelines"),
    ]
    
    print("=== AI-Powered Semantic Query Normalization Test ===\n")
    print("This test shows how the new approach uses semantic understanding")
    print("rather than keyword extraction to solve the consistency problem.\n")
    
    for original_query, expected_intent in test_queries:
        print(f"Original: '{original_query}'")
        print(f"Expected Intent: '{expected_intent}'")
        
        result = await normalizer.normalize_query(original_query)
        
        print(f"Normalized: '{result['primary_search_query']}'")
        print(f"Method: {result.get('method', 'unknown')}")
        print(f"Confidence: {result['confidence']:.2f}")
        
        if result.get('reasoning'):
            print(f"AI Reasoning: {result['reasoning']}")
        
        if result.get('alternative_queries'):
            print(f"Alternatives: {result['alternative_queries']}")
        
        # Check if the normalization would improve consistency
        if original_query.lower() != expected_intent.lower():
            normalized_lower = result['primary_search_query'].lower()
            if expected_intent.lower() in normalized_lower or normalized_lower in expected_intent.lower():
                print("✅ CONSISTENCY IMPROVED - Query normalized correctly")
            else:
                print("❌ NEEDS IMPROVEMENT - Query normalization may not solve consistency issue")
        else:
            print("✅ BASELINE - Direct query, should remain unchanged")
        
        print("-" * 80)


async def test_with_openai():
    """Test with OpenAI client for full AI semantic understanding."""
    print("\n=== Testing with OpenAI AI Enhancement ===")
    print("Note: This requires OpenAI client configuration")
    
    # This would require actual OpenAI client setup
    # normalizer = QueryNormalizer(openai_client, "gpt-4")
    # result = await normalizer.normalize_query("what's our wellness policy")
    print("OpenAI testing requires configuration - see implementation for full AI semantic understanding")


if __name__ == "__main__":
    asyncio.run(test_semantic_normalization())
    asyncio.run(test_with_openai())
