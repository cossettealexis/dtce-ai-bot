"""
Test conversation history and follow-up questions
Simulates a Teams conversation to verify context is maintained
"""
import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.config.settings import Settings
from dtce_ai_bot.services.azure_rag_service_v2 import AzureRAGService
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

async def test_conversation_flow():
    """Test a realistic conversation flow with follow-up questions"""
    
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
    
    # Initialize RAG service
    rag_service = AzureRAGService(
        search_client=search_client,
        openai_client=openai_client,
        model_name=settings.azure_openai_deployment_name,
        intent_model_name=settings.azure_openai_deployment_name,
        max_retries=3
    )
    
    print("=" * 100)
    print("TESTING TEAMS BOT CONVERSATION FLOW (with conversation history)")
    print("=" * 100)
    
    # Simulate a conversation
    conversation_history = []
    
    # TURN 1: Initial query
    print(f"\n{'='*100}")
    print("👤 USER: show me 2024 projects")
    print(f"{'='*100}")
    
    user_query_1 = "show me 2024 projects"
    response_1 = await rag_service.process_query(user_query_1, conversation_history=conversation_history)
    
    answer_1 = response_1.get('answer', '')
    print(f"\n🤖 BOT RESPONSE:")
    print(f"{answer_1[:400]}...")
    print(f"\n✓ Intent: {response_1.get('intent')}")
    print(f"✓ Documents Found: {response_1.get('total_documents')}")
    
    # Update conversation history (simulating what Teams bot does)
    conversation_history.append({"role": "user", "content": user_query_1})
    conversation_history.append({"role": "assistant", "content": answer_1})
    
    # Extract a project number from the response
    import re
    project_numbers = re.findall(r'\b(224\d{3})\b', answer_1)
    if not project_numbers:
        print("\n❌ No project numbers found in response! Can't continue test.")
        return
    
    test_project = project_numbers[0]
    print(f"\n📋 Will ask follow-up about project: {test_project}")
    
    # TURN 2: Follow-up question (explicit project number)
    print(f"\n{'='*100}")
    print(f"👤 USER: tell me more about project {test_project}")
    print(f"{'='*100}")
    print(f"📚 Conversation History Length: {len(conversation_history)} messages")
    
    user_query_2 = f"tell me more about project {test_project}"
    response_2 = await rag_service.process_query(user_query_2, conversation_history=conversation_history)
    
    answer_2 = response_2.get('answer', '')
    print(f"\n🤖 BOT RESPONSE:")
    print(f"{answer_2[:500]}...")
    print(f"\n✓ Intent: {response_2.get('intent')}")
    print(f"✓ Filter: {response_2.get('search_filter', 'None')[:100]}...")
    print(f"✓ Documents Found: {response_2.get('total_documents')}")
    
    # Update conversation history
    conversation_history.append({"role": "user", "content": user_query_2})
    conversation_history.append({"role": "assistant", "content": answer_2})
    
    # Check if bot found the project
    if test_project in answer_2:
        print(f"\n✅ SUCCESS: Bot found details about project {test_project}")
    else:
        print(f"\n⚠️  WARNING: Project {test_project} not mentioned in response")
    
    # TURN 3: Follow-up with pronoun reference
    print(f"\n{'='*100}")
    print(f"👤 USER: what's the budget for this project?")
    print(f"{'='*100}")
    print(f"📚 Conversation History Length: {len(conversation_history)} messages")
    
    user_query_3 = "what's the budget for this project?"
    response_3 = await rag_service.process_query(user_query_3, conversation_history=conversation_history)
    
    answer_3 = response_3.get('answer', '')
    print(f"\n🤖 BOT RESPONSE:")
    print(f"{answer_3[:500]}...")
    print(f"\n✓ Intent: {response_3.get('intent')}")
    print(f"✓ Documents Found: {response_3.get('total_documents')}")
    
    # Check if bot maintained context
    if test_project in answer_3 or 'budget' in answer_3.lower() or 'cost' in answer_3.lower() or 'fee' in answer_3.lower():
        print(f"\n✅ SUCCESS: Bot maintained context with pronoun 'this project'")
    else:
        print(f"\n❌ FAIL: Bot lost conversation context")
    
    # TURN 4: Another pronoun reference
    print(f"\n{'='*100}")
    print(f"👤 USER: what's the timeline?")
    print(f"{'='*100}")
    print(f"📚 Conversation History Length: {len(conversation_history)} messages")
    
    user_query_4 = "what's the timeline?"
    response_4 = await rag_service.process_query(user_query_4, conversation_history=conversation_history)
    
    answer_4 = response_4.get('answer', '')
    print(f"\n🤖 BOT RESPONSE:")
    print(f"{answer_4[:500]}...")
    print(f"\n✓ Intent: {response_4.get('intent')}")
    print(f"✓ Documents Found: {response_4.get('total_documents')}")
    
    # Check if bot maintained context
    if 'timeline' in answer_4.lower() or 'schedule' in answer_4.lower() or 'weeks' in answer_4.lower() or 'days' in answer_4.lower():
        print(f"\n✅ SUCCESS: Bot answered timeline question using conversation context")
    else:
        print(f"\n⚠️  WARNING: Bot may not have used conversation context properly")
    
    # TURN 5: Change topic completely
    print(f"\n{'='*100}")
    print(f"👤 USER: show me 2023 projects")
    print(f"{'='*100}")
    print(f"📚 Conversation History Length: {len(conversation_history)} messages")
    
    conversation_history.append({"role": "user", "content": user_query_3})
    conversation_history.append({"role": "assistant", "content": answer_3})
    conversation_history.append({"role": "user", "content": user_query_4})
    conversation_history.append({"role": "assistant", "content": answer_4})
    
    user_query_5 = "show me 2023 projects"
    response_5 = await rag_service.process_query(user_query_5, conversation_history=conversation_history)
    
    answer_5 = response_5.get('answer', '')
    print(f"\n🤖 BOT RESPONSE:")
    print(f"{answer_5[:400]}...")
    print(f"\n✓ Intent: {response_5.get('intent')}")
    print(f"✓ Filter: {response_5.get('search_filter', 'None')}")
    print(f"✓ Documents Found: {response_5.get('total_documents')}")
    
    # Check if filter changed to 2023
    if '223/' in str(response_5.get('search_filter', '')):
        print(f"\n✅ SUCCESS: Bot switched context to 2023 projects")
    else:
        print(f"\n⚠️  WARNING: Filter doesn't match 2023")
    
    # Summary
    print(f"\n{'='*100}")
    print(f"📊 CONVERSATION TEST SUMMARY")
    print(f"{'='*100}")
    print(f"✓ Total Turns: 5")
    print(f"✓ Final Conversation History: {len(conversation_history)} messages")
    print(f"✓ Context Switching: Tested")
    print(f"✓ Pronoun Resolution: Tested")
    print(f"✓ Topic Changes: Tested")
    print(f"{'='*100}")
    
    await search_client.close()
    await openai_client.close()

if __name__ == "__main__":
    asyncio.run(test_conversation_flow())
