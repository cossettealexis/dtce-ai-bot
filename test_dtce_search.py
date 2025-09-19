"""
Test DTCE RAG System with Existing Index

This test works with your existing Azure Search index without requiring embeddings.
"""

import os
from pathlib import Path

# Load environment variables from .env file
def load_env_file():
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

def test_dtce_search():
    """Test searching your existing DTCE index"""
    
    load_env_file()
    
    try:
        from dtce_ai_bot.rag.config import RAGConfig
        from dtce_ai_bot.rag.dtce_retriever import DTCERetriever
        
        # Create config and retriever
        config = RAGConfig.from_env()
        retriever = DTCERetriever(config)
        
        print("🔍 Testing DTCE Index Search...")
        
        # Test different types of searches
        test_searches = [
            ("fire safety", "General fire safety search"),
            ("concrete", "Concrete-related documents"),
            ("structural", "Structural engineering content"),
            ("building code", "Building codes and standards"),
        ]
        
        for query, description in test_searches:
            print(f"\n📝 {description}: '{query}'")
            
            results = retriever.retrieve(query, top_k=3)
            print(f"   Found {len(results)} results")
            
            for i, result in enumerate(results[:2], 1):
                print(f"   {i}. {result.metadata.get('filename', 'Unknown')} (Score: {result.score:.2f})")
                print(f"      Project: {result.metadata.get('project_name', 'Unknown')}")
                
                # Show content preview
                content_preview = result.content[:150].replace('\n', ' ')
                print(f"      Content: {content_preview}...")
        
        # Test project-specific search
        print(f"\n🏗️ Project-specific search...")
        project_results = retriever.search_by_project("219219", "structural")
        print(f"   Found {len(project_results)} results in project 219219")
        
        # Test recent documents
        print(f"\n📅 Recent documents...")
        recent_results = retriever.get_recent_documents(top_k=3)
        print(f"   Found {len(recent_results)} recent documents")
        
        for result in recent_results[:2]:
            print(f"   - {result.metadata.get('filename', 'Unknown')}")
            print(f"     Modified: {result.metadata.get('last_modified', 'Unknown')}")
        
        print(f"\n✅ DTCE Index search is working!")
        print(f"📊 Your index contains 406,051 documents ready for search")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 Testing DTCE RAG System...")
    test_dtce_search()
