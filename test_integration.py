#!/usr/bin/env python3
"""
Test the integrated universal AI assistant in the bot.
"""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_integrated_universal_ai():
    """Test that the universal AI assistant is properly integrated."""
    
    # Mock the Azure search client
    mock_search_client = MagicMock()
    mock_search_results = AsyncMock()
    mock_search_results.__aiter__ = AsyncMock(return_value=iter([
        {
            'content': 'Sample NZS 3101:2006 concrete cover requirements...',
            'title': 'NZ Standards - Concrete Structures',
            '@search.score': 0.95,
            'metadata': {'folder': 'standards'}
        }
    ]))
    mock_search_client.search = AsyncMock(return_value=mock_search_results)
    
    # Mock the OpenAI client
    mock_openai_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '''{"needs_dtce_documents": true, "folder_type": "standards", "question_intent": "NZ standards inquiry", "response_approach": "document_search"}'''
    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    # Test questions
    test_questions = [
        "What is machine learning?",  # General AI question
        "What are the minimum clear cover requirements for concrete?",  # DTCE standards question
        "How do I use the site wind speed spreadsheet?",  # DTCE procedures question
    ]
    
    print("Testing Integrated Universal AI Assistant")
    print("=" * 50)
    
    try:
        # Import the RAG handler
        from dtce_ai_bot.services.rag_handler import RAGHandler
        
        # Initialize with mocks
        rag_handler = RAGHandler(mock_search_client, mock_openai_client, "gpt-4")
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n🧪 Test {i}: {question}")
            print("-" * 40)
            
            try:
                # This should now use the universal AI assistant
                result = await rag_handler.process_question(question)
                
                print(f"✅ Status: Success")
                print(f"📋 Response type: {result.get('rag_type', 'unknown')}")
                print(f"📁 Folder searched: {result.get('folder_searched', 'none')}")
                print(f"📄 Documents found: {result.get('documents_searched', 0)}")
                print(f"💬 Has answer: {'Yes' if result.get('answer') else 'No'}")
                
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                
            print("=" * 50)
    
    except ImportError as e:
        print(f"❌ Import Error: {str(e)}")
        print("This suggests there might be missing dependencies or module issues.")
    except Exception as e:
        print(f"❌ Test Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_integrated_universal_ai())
