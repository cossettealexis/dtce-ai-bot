#!/usr/bin/env python3
"""
Test the RAG implementation with sample questions from RAG.TXT
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.integrations.azure.search_client import AzureSearchClient
from dtce_ai_bot.services.document_qa import DocumentQAService

async def test_rag_patterns():
    """Test RAG patterns with sample questions."""
    
    print("🚀 Testing RAG Implementation...")
    
    # Initialize services
    settings = get_settings()
    search_client = AzureSearchClient()
    qa_service = DocumentQAService(search_client.search_client)
    
    # Test questions from RAG.TXT
    test_questions = [
        # NZS Code Lookup
        "Please tell me that minimum clear cover requirements as per NZS code in designing a concrete element",
        "Tell me what particular clause that talks about the detailing requirements in designing a beam",
        
        # Project Reference  
        "I am designing a precast panel, please tell me all past project that has a scope about the following keywords: Precast Panel, Precast Connection",
        "I am designing a timber retaining wall it's going to be 3m tall; can you provide me example past projects?",
        
        # Product Lookup
        "I need timber connection details for joining a timber beam to a column. Please provide specifications for the proprietary products DTCE usually refers to",
        
        # Template Request
        "Please provide me with the template we generally use for preparing a PS1. Also, please provide me with the direct link to access it on SuiteFiles",
        
        # Scenario Technical
        "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed",
        
        # General test
        "help"
    ]
    
    print(f"\n🔍 Testing {len(test_questions)} questions...\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"📝 Question {i}: {question}")
        print("-" * 80)
        
        try:
            response = await qa_service.answer_question(question)
            
            print(f"✅ RAG Type: {response.get('rag_type', response.get('search_type', 'Unknown'))}")
            print(f"🎯 Confidence: {response.get('confidence', 'Unknown')}")
            print(f"📚 Documents: {response.get('documents_searched', 0)}")
            print(f"💬 Answer: {response.get('answer', 'No answer')[:200]}...")
            
            if response.get('sources'):
                print(f"🔗 Sources: {len(response['sources'])} found")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print("\n" + "="*80 + "\n")
    
    print("✅ RAG Testing Complete!")

if __name__ == "__main__":
    asyncio.run(test_rag_patterns())
