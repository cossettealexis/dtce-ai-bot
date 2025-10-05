"""
Direct test of wellness policy retrieval to see what content is actually being found
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dtce_ai_bot.services.azure_rag_service import RAGOrchestrator

async def test_wellness():
    print("\n" + "="*80)
    print("TESTING WELLNESS POLICY RETRIEVAL")
    print("="*80)
    
    orchestrator = RAGOrchestrator()
    
    question = "What does the wellbeing policy say about mental health support?"
    print(f"\nQuestion: {question}")
    print("-"*80)
    
    # Get the answer
    result = await orchestrator.process_question(question, session_id="test-session")
    
    print("\n📊 RESULT DETAILS:")
    print(f"Answer Type: {result.get('answer_type', 'unknown')}")
    print(f"Confidence: {result.get('confidence', 'unknown')}")
    print(f"Sources Count: {len(result.get('sources', []))}")
    
    print("\n📄 SOURCES RETRIEVED:")
    for i, source in enumerate(result.get('sources', []), 1):
        print(f"\nSource {i}:")
        print(f"  File: {source.get('filename', 'unknown')}")
        print(f"  Score: {source.get('score', 'unknown')}")
        print(f"  Content Length: {len(source.get('content', ''))}")
        content_preview = source.get('content', '')[:200]
        print(f"  Content Preview: {content_preview}...")
    
    print("\n💬 ANSWER:")
    print(result.get('answer', 'No answer'))
    
    print("\n" + "="*80)
    
    # Check if we're getting the filename-only problem
    has_real_content = False
    for source in result.get('sources', []):
        content = source.get('content', '')
        if len(content) > 100 and not content.startswith('Document:'):
            has_real_content = True
            break
    
    if not has_real_content:
        print("\n⚠️  WARNING: All sources have minimal content!")
        print("This means the documents in the index only have filenames, not actual text.")
        print("You need to reindex these documents with proper content extraction.")
    else:
        print("\n✅ Sources contain actual document content")

if __name__ == "__main__":
    asyncio.run(test_wellness())
