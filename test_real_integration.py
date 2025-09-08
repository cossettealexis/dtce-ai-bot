#!/usr/bin/env python3
"""
Quick real-world test of the universal AI assistant.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_real_bot():
    """Test the bot with real questions to see if it works."""
    
    # Mock the required components for testing
    class MockSearchClient:
        async def search(self, search_text, top=10, search_fields=None):
            # Mock search results
            mock_results = [
                {
                    'content': f'Mock content for: {search_text}',
                    'title': 'Mock Document',
                    '@search.score': 0.85,
                    'metadata': {}
                }
            ]
            
            class MockAsyncIterator:
                def __init__(self, results):
                    self.results = results
                    self.index = 0
                
                def __aiter__(self):
                    return self
                
                async def __anext__(self):
                    if self.index >= len(self.results):
                        raise StopAsyncIteration
                    result = self.results[self.index]
                    self.index += 1
                    return result
            
            return MockAsyncIterator(mock_results)
    
    class MockOpenAIClient:
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        
        class MockChat:
            class MockCompletions:
                async def create(self, model, messages, temperature=0.3, max_tokens=1000):
                    # Mock AI response based on the prompt
                    user_message = messages[-1]['content']
                    print(f"🔍 Mock AI received: {user_message[:100]}...")
                    
                    if 'analyze this question' in user_message.lower() or 'determine what information' in user_message.lower():
                        # Mock routing decision - make it more realistic
                        if 'concrete' in user_message and 'cover' in user_message:
                            response_content = '''{"needs_dtce_documents": true, "folder_type": "standards", "needs_web_search": false, "needs_job_numbers": false, "needs_links": false, "needs_database_search": false, "question_intent": "technical standards query", "response_approach": "document_search", "search_keywords": ["concrete", "cover", "requirements"]}'''
                        elif 'machine learning' in user_message:
                            else:
                            response_content = '''{"needs_dtce_documents": false, "folder_type": "none", "needs_web_search": false, "needs_job_numbers": false, "needs_links": false, "needs_database_search": false, "question_intent": "general question", "response_approach": "general_ai", "search_keywords": []}'''
                    
                    else:
                        # Mock actual answers based on question type
                        if 'concrete' in user_message and 'cover' in user_message:
                            response_content = "According to NZS 3101:2006, the minimum clear cover requirements for concrete are: Beams and columns: 20mm minimum, Slabs: 15mm minimum, Foundations: 40mm minimum. This ensures proper durability and fire resistance."
                        elif 'machine learning' in user_message:
                            response_content = "Machine learning is a subset of artificial intelligence that enables computers to learn and make decisions from data without being explicitly programmed for every task."
                        elif 'past projects' in user_message:
                            response_content = "Based on DTCE project records, here are relevant steel structure projects: Job #12345 - Steel building retrofit, Job #12346 - Structural steel upgrade. Contact the project team for detailed drawings and specifications."
                        else:
                            response_content = "I'm here to help with your engineering questions. Please feel free to ask about technical standards, past projects, or general engineering topics."
                    
                    print(f"💬 Mock AI responding: {response_content[:50]}...")
                        elif 'past projects' in user_message or 'dtce projects' in user_message:
                            response_content = '''{"needs_dtce_documents": true, "folder_type": "projects", "needs_web_search": false, "needs_job_numbers": true, "needs_links": true, "needs_database_search": false, "question_intent": "project reference query", "response_approach": "document_search", "search_keywords": ["steel", "structures"]}'''
                        else:
                            response_content = '''{"needs_dtce_documents": false, "folder_type": "none", "needs_web_search": false, "needs_job_numbers": false, "needs_links": false, "needs_database_search": false, "question_intent": "general question", "response_approach": "general_ai", "search_keywords": []}'''
                    else:
                    else:
                        # Mock actual answers based on question type
                        if 'concrete' in user_message and 'cover' in user_message:
                            response_content = "According to NZS 3101:2006, the minimum clear cover requirements for concrete are: Beams and columns: 20mm minimum, Slabs: 15mm minimum, Foundations: 40mm minimum. This ensures proper durability and fire resistance."
                        elif 'machine learning' in user_message:
                            response_content = "Machine learning is a subset of artificial intelligence that enables computers to learn and make decisions from data without being explicitly programmed for every task."
                        elif 'past projects' in user_message:
                            response_content = "Based on DTCE project records, here are relevant steel structure projects: Job #12345 - Steel building retrofit, Job #12346 - Structural steel upgrade. Contact the project team for detailed drawings and specifications."
                        else:
                            response_content = "I'm here to help with your engineering questions. Please feel free to ask about technical standards, past projects, or general engineering topics."
                    
                    class MockChoice:
                        class MockMessage:
                            def __init__(self, content):
                                self.content = content
                        
                        def __init__(self, content):
                            self.message = self.MockMessage(content)
                    
                    class MockResponse:
                        def __init__(self, content):
                            self.choices = [MockChoice(content)]
                    
                    return MockResponse(response_content)
            
            def __init__(self):
                self.completions = self.MockCompletions()
        
        def __init__(self):
            self.chat = self.MockChat()
    
    try:
        from dtce_ai_bot.services.rag_handler import RAGHandler
        
        # Initialize with mock components
        search_client = MockSearchClient()
        openai_client = MockOpenAIClient()
        model_name = "gpt-4"
        
        rag_handler = RAGHandler(search_client, openai_client, model_name)
        
        # Test questions
        test_questions = [
            "What are the minimum clear cover requirements for concrete as per NZS code?",
            "What is machine learning?",
            "Can you find past DTCE projects about steel structures?"
        ]
        
        print("🤖 Real Bot Integration Test")
        print("=" * 50)
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n📋 Test {i}: {question}")
            print("-" * 40)
            
            try:
                # Test the universal AI assistant
                result = await rag_handler.universal_ai_assistant(question)
                
                print(f"✅ Response Type: {result.get('rag_type', 'unknown')}")
                print(f"📁 Search Method: {result.get('search_method', 'unknown')}")
                print(f"🎯 Confidence: {result.get('confidence', 'unknown')}")
                print(f"📊 Documents Found: {result.get('documents_searched', 0)}")
                print(f"💬 Answer Preview: {result.get('answer', 'No answer')[:100]}...")
                
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                import traceback
                print(f"📍 Details: {traceback.format_exc()[:200]}...")
        
        print("\n" + "=" * 50)
        print("🎉 Integration test completed!")
        
    except Exception as e:
        print(f"❌ Failed to import or initialize: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_bot())
