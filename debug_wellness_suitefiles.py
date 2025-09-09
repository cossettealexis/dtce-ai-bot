#!/usr/bin/env python3
"""Debug SuiteFiles link generation in wellness policy response."""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.config.settings import Settings


async def debug_wellness_policy_response():
    """Debug the wellness policy response to see why SuiteFiles links are missing."""
    print("Debugging wellness policy response for SuiteFiles links...")
    
    settings = Settings()
    qa_service = DocumentQAService(settings)
    
    question = "what's our wellness policy"
    
    try:
        # Get the response using the same method as Teams bot
        response = await qa_service.answer_question(question)
        
        print(f"\nQuestion: {question}")
        print(f"Response: {response}")
        
        # Check if response contains SuiteFiles
        if "SuiteFiles" in response:
            print("\n✅ SuiteFiles link found in response!")
            # Extract and show the link
            lines = response.split('\n')
            for line in lines:
                if "SuiteFiles" in line:
                    print(f"🔗 Found link line: {line.strip()}")
        else:
            print("\n❌ No SuiteFiles link found in response")
            print("Let's check what the RAG handler actually returns...")
            
            # Let's also check the raw RAG handler response
            rag_handler = qa_service.rag_handler
            rag_response = await rag_handler.process_question(question)
            
            print(f"\nRAG Handler response: {rag_response}")
            
            if "SuiteFiles" in rag_response:
                print("✅ SuiteFiles found in RAG handler response!")
            else:
                print("❌ No SuiteFiles in RAG handler response either")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_wellness_policy_response())
