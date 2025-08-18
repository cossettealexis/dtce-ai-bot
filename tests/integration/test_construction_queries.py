#!/usr/bin/env python3
"""
Test script to validate how the DTCE AI bot handles construction-specific queries.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_construction_queries():
    """Test the specific construction queries provided by the user."""
    
    # Test queries from the user
    test_queries = [
        "I'm looking for a specific proprietary product that's suitable to provide a waterproofing layer to a concrete block wall that DTCE has used in the past",
        "What are the timber connection details that you've used for 220mm LVL timber beams?",
        "LVL timber in the New Zealand market"
    ]
    
    expected_output = "relevant product specifications, prioritizing documents from SuiteFiles, along with alternative products found online"
    
    print("DTCE AI Bot Construction Query Test")
    print("=" * 50)
    print(f"Expected Output Format: {expected_output}")
    print("=" * 50)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n📋 Test Query {i}:")
            print(f"Question: {query}")
            print("-" * 40)
            
            # First, let's check if it's detected as a keyword project query
            is_keyword_query = qa_service._is_project_keyword_query(query)
            print(f"Detected as keyword project query: {is_keyword_query}")
            
            # Extract keywords
            keywords = qa_service._extract_keywords_from_question(query)
            print(f"Extracted keywords: {keywords}")
            
            # Get the answer
            try:
                result = await qa_service.answer_question(query)
                
                print(f"\n🤖 AI Response:")
                print(f"Answer: {result['answer']}")
                print(f"Confidence: {result['confidence']}")
                print(f"Documents searched: {result['documents_searched']}")
                print(f"Sources found: {len(result['sources'])}")
                
                if result['sources']:
                    print("\n📄 Sources:")
                    for j, source in enumerate(result['sources'][:3], 1):
                        print(f"  {j}. {source.get('filename', 'Unknown file')}")
                        if 'project_id' in source:
                            print(f"     Project: {source['project_id']}")
                        if 'blob_url' in source:
                            print(f"     URL: {source['blob_url']}")
                        print(f"     Relevance: {source.get('relevance_score', 'N/A')}")
                
            except Exception as e:
                print(f"❌ Error processing query: {e}")
            
            print("\n" + "=" * 50)
    
    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        print("This might be due to missing Azure configuration or credentials.")

if __name__ == "__main__":
    asyncio.run(test_construction_queries())
