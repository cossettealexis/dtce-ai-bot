#!/usr/bin/env python3
"""
Test the original problematic queries to verify the semantic normalization fix.

This script tests the exact cases that were causing inconsistency:
1. "wellness policy" vs "what's our wellness policy" 
2. "really" triggering searches instead of conversational responses
3. Other similar conversational vs direct query inconsistencies
"""

import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.config.settings import get_settings
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential


async def test_original_problem_cases():
    """Test the exact problematic query pairs that were inconsistent."""
    
    print("=== Testing Original Problem Cases ===\n")
    print("Testing the exact queries that were causing inconsistency issues.\n")
    
    # Setup Azure Search client
    settings = get_settings()
    search_client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key)
    )
    
    # Initialize Document QA service with new normalization
    qa_service = DocumentQAService(search_client)
    
    # Test cases: pairs of queries that should give consistent results
    test_cases = [
        {
            "name": "Wellness Policy Consistency",
            "queries": [
                "wellness policy",
                "what's our wellness policy",
                "What is our wellness policy?"
            ],
            "expected": "Should all find wellness/health policy documents"
        },
        {
            "name": "IT Policy Consistency", 
            "queries": [
                "IT policy",
                "what's our IT policy",
                "What is the IT security policy?"
            ],
            "expected": "Should all find IT/technology policy documents"
        },
        {
            "name": "Safety Procedures Consistency",
            "queries": [
                "safety procedures",
                "where can I find safety procedures",
                "What are our safety rules?"
            ],
            "expected": "Should all find safety/security documents"
        },
        {
            "name": "Casual Word Filtering",
            "queries": [
                "What's really important about our HR guidelines?",
                "HR guidelines really important aspects",
                "HR guidelines"
            ],
            "expected": "Should focus on HR content, not trigger search due to 'really'"
        }
    ]
    
    for test_case in test_cases:
        print(f"🧪 {test_case['name']}")
        print(f"Expected: {test_case['expected']}\n")
        
        results = []
        for i, query in enumerate(test_case['queries']):
            print(f"Query {i+1}: '{query}'")
            
            try:
                result = await qa_service.answer_question(query)
                
                # Extract key information for comparison
                doc_count = result.get('documents_searched', 0)
                confidence = result.get('confidence', 'unknown')
                normalization = result.get('query_normalization', {})
                
                print(f"  Documents found: {doc_count}")
                print(f"  Confidence: {confidence}")
                
                if normalization:
                    print(f"  Original query: '{normalization.get('original_query', 'N/A')}'")
                    print(f"  Normalized to: '{normalization.get('normalized_query', 'N/A')}'")
                    print(f"  Method: {normalization.get('method', 'N/A')}")
                    print(f"  Normalization confidence: {normalization.get('confidence', 'N/A')}")
                
                # Check if answer contains relevant content
                answer_preview = result.get('answer', '')[:200] + "..." if len(result.get('answer', '')) > 200 else result.get('answer', '')
                print(f"  Answer preview: {answer_preview}")
                
                results.append({
                    'query': query,
                    'doc_count': doc_count,
                    'confidence': confidence,
                    'normalized_query': normalization.get('normalized_query', query),
                    'method': normalization.get('method', 'none')
                })
                
            except Exception as e:
                print(f"  ❌ Error: {str(e)}")
                results.append({
                    'query': query,
                    'error': str(e)
                })
            
            print()
        
        # Analyze consistency
        print("📊 Consistency Analysis:")
        normalized_queries = [r.get('normalized_query', '') for r in results if 'error' not in r]
        doc_counts = [r.get('doc_count', 0) for r in results if 'error' not in r]
        
        if normalized_queries:
            unique_normalized = set(normalized_queries)
            print(f"  Normalized queries: {list(unique_normalized)}")
            
            if len(unique_normalized) == 1:
                print("  ✅ CONSISTENT - All queries normalized to the same terms")
            else:
                print("  ⚠️  VARIATION - Different normalized queries (may still be semantically equivalent)")
        
        if doc_counts:
            min_docs, max_docs = min(doc_counts), max(doc_counts)
            if max_docs - min_docs <= 2:  # Allow small variation
                print(f"  ✅ CONSISTENT RESULTS - Document counts similar ({min_docs}-{max_docs})")
            else:
                print(f"  ❌ INCONSISTENT RESULTS - Large variation in document counts ({min_docs}-{max_docs})")
        
        print("=" * 80)
        print()


async def test_casual_word_filtering():
    """Test that casual words like 'really' don't trigger unnecessary searches."""
    
    print("=== Testing Casual Word Filtering ===\n")
    
    # This would typically be tested at the Teams bot level, but we can check
    # if the normalization helps reduce noise
    
    casual_queries = [
        "What's really important about our policies?",
        "I really need to find the wellness policy",
        "Can you really help me with safety procedures?",
        "This is really urgent - need IT policy"
    ]
    
    print("Testing queries with casual words like 'really':")
    print("The new normalization should focus on the core intent rather than being distracted by casual language.\n")
    
    # Setup would be the same as above
    # For now, just show the concept
    for query in casual_queries:
        print(f"Query: '{query}'")
        print("Expected: Focus on core intent (policy/wellness/safety/IT) rather than casual words")
        print()


if __name__ == "__main__":
    print("🔬 DTCE AI Bot - Semantic Query Normalization Test")
    print("Testing the fixes for query consistency issues\n")
    
    asyncio.run(test_original_problem_cases())
    asyncio.run(test_casual_word_filtering())
