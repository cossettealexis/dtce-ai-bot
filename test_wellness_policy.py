"""
Test wellness policy question with deployed Azure fix
"""
import asyncio
import structlog
from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

logger = structlog.get_logger()

async def test_wellness():
    """Test wellness policy question"""
    print("🏥 TESTING WELLNESS POLICY QUESTION")
    print("=" * 60)
    
    search_client = get_search_client()
    qa_service = DocumentQAService(search_client=search_client)
    
    question = "What is the company wellness policy?"
    print(f"\n🔍 Question: '{question}'")
    print("-" * 50)
    
    result = await qa_service.answer_question(
        question=question,
        project_filter=None
    )
    
    print(f"📝 Answer: {result['answer'][:200]}...")
    print(f"🎯 RAG Type: {result.get('type', 'unknown')}")
    print(f"💪 Confidence: {result.get('confidence', 'unknown')}")
    print(f"📚 Sources: {len(result.get('sources', []))}")
    print(f"🔍 Docs Searched: {result.get('metadata', {}).get('total_searched', 0)}")
    
    if result.get('type') == 'azure_hybrid_rag':
        print("✅ Using Azure RAG system")
    
    # Check if answer is detailed enough
    if len(result['answer']) > 300:
        print("✅ Good detailed response")
    else:
        print("⚠️ Response might be too short - check if policy content is in index")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test_wellness())
