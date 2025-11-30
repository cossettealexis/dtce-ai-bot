"""
Quick test script to verify the deployed bot is working correctly
"""
import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.config.settings import Settings
from dtce_ai_bot.services.azure_rag_service_v2 import RAGOrchestrator
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

async def test_queries():
    """Test the bot with various queries"""
    
    # Load settings
    settings = Settings()
    
    # Initialize clients
    search_client = SearchClient(
        endpoint=settings.azure_search_service_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key)
    )
    
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version="2024-08-01-preview",
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    # Initialize orchestrator
    orchestrator = RAGOrchestrator(
        search_client=search_client,
        openai_client=openai_client,
        model_name=settings.azure_openai_deployment_name,
        max_retries=3
    )
    
    # Test queries
    test_cases = [
        "show me 2024 projects",
        "give me project numbers from 2024",
        "show me project numbers from the past 4 years"
    ]
    
    print("=" * 80)
    print("TESTING DEPLOYED BOT - BASIC QUERIES")
    print("=" * 80)
    
    for i, query in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}: {query}")
        print(f"{'='*80}")
        
        try:
            result = await orchestrator.process_question(query, session_id="test")
            
            print(f"\n✓ Intent: {result.get('intent', 'N/A')}")
            print(f"✓ Filter: {result.get('search_filter', 'N/A')}")
            print(f"✓ Total Documents: {result.get('total_documents', 0)}")
            print(f"\n✓ Answer Preview (first 500 chars):")
            print("-" * 80)
            answer = result.get('answer', '')
            print(answer[:500] + "..." if len(answer) > 500 else answer)
            
            # Check if it found projects
            if 'project' in answer.lower() and any(char.isdigit() for char in answer):
                print(f"\n✓ SUCCESS: Found project numbers in response")
            else:
                print(f"\n✗ WARNING: No project numbers detected in response")
                
        except Exception as e:
            print(f"\n✗ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Test follow-up conversation (conversation history)
    print("\n" + "=" * 80)
    print("TESTING FOLLOW-UP QUESTIONS (CONVERSATION HISTORY)")
    print("=" * 80)
    
    # Start a new conversation session
    session_id = "follow_up_test"
    
    # First question
    print(f"\n{'='*80}")
    print("CONVERSATION TEST - Question 1: show me 2024 projects")
    print(f"{'='*80}")
    
    try:
        result1 = await orchestrator.process_question("show me 2024 projects", session_id=session_id)
        answer1 = result1.get('answer', '')
        print(f"\n✓ Answer Preview (first 300 chars):")
        print("-" * 80)
        print(answer1[:300] + "...")
        
        # Extract first project number from the answer
        import re
        project_numbers = re.findall(r'\b(224\d{3})\b', answer1)
        if project_numbers:
            first_project = project_numbers[0]
            print(f"\n✓ Found project numbers, will ask about: {first_project}")
            
            # Follow-up question WITHOUT mentioning the project number
            print(f"\n{'='*80}")
            print(f"CONVERSATION TEST - Question 2: tell me more about {first_project}")
            print(f"{'='*80}")
            
            result2 = await orchestrator.process_question(f"tell me more about {first_project}", session_id=session_id)
            answer2 = result2.get('answer', '')
            print(f"\n✓ Intent: {result2.get('intent', 'N/A')}")
            print(f"✓ Filter: {result2.get('search_filter', 'N/A')}")
            print(f"\n✓ Answer Preview (first 500 chars):")
            print("-" * 80)
            print(answer2[:500] + "..." if len(answer2) > 500 else answer2)
            
            if first_project in answer2:
                print(f"\n✅ SUCCESS: Bot remembered context and found details about {first_project}!")
            else:
                print(f"\n⚠️ WARNING: Bot may not have used conversation context properly")
                
            # Third follow-up with pronoun reference
            print(f"\n{'='*80}")
            print("CONVERSATION TEST - Question 3: what's the timeline for this project?")
            print(f"{'='*80}")
            
            result3 = await orchestrator.process_question("what's the timeline for this project?", session_id=session_id)
            answer3 = result3.get('answer', '')
            print(f"\n✓ Answer Preview (first 500 chars):")
            print("-" * 80)
            print(answer3[:500] + "..." if len(answer3) > 500 else answer3)
            
            if first_project in answer3 or 'timeline' in answer3.lower() or 'schedule' in answer3.lower():
                print(f"\n✅ SUCCESS: Bot used pronoun reference 'this project' correctly!")
            else:
                print(f"\n❌ FAIL: Bot lost conversation context with pronoun reference")
        else:
            print(f"\n✗ No project numbers found in first answer, skipping follow-up tests")
            
    except Exception as e:
        print(f"\n✗ ERROR in follow-up test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    await search_client.close()
    await openai_client.close()

if __name__ == "__main__":
    asyncio.run(test_queries())
