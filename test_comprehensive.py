"""
Comprehensive DTCE RAG System Test

Tests all the specified question types and use cases for the DTCE AI bot.
"""

import os
from pathlib import Path
import time

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

def test_dtce_comprehensive():
    """Test all DTCE question types and scenarios"""
    
    load_env_file()
    
    try:
        from dtce_ai_bot.rag.config import RAGConfig
        from dtce_ai_bot.rag.dtce_retriever import DTCERetriever
        
        # Create config and retriever
        config = RAGConfig.from_env()
        retriever = DTCERetriever(config)
        
        print("🧪 DTCE Comprehensive RAG System Test")
        print("=" * 60)
        
        # Test categories with questions
        test_categories = {
            "1. Policy & H&S Queries": [
                "What is our wellness policy?",
                "What's our wellness policy and what does it say?",
                "wellness policy",
                "wellbeing policy",
                "health and safety procedures",
                "H&S policy",
            ],
            
            "2. Technical & Admin Procedures": [
                "how do i use the site wind speed spreadsheet",
                "H2H procedures",
                "technical procedures",
                "admin procedures",
                "how to handbooks",
            ],
            
            "3. NZ Engineering Standards": [
                "minimum clear cover requirements as per NZS code in designing a concrete element",
                "Tell me what particular clause that talks about the detailing requirements in designing a beam",
                "strength reduction factors used when designing a beam or considering seismic actions",
                "what particular NZS structural code to refer with if I'm designing a composite slab to make it as floor diaphragm",
                "NZS 4404",
                "NZS 3910",
            ],
            
            "4. Project Reference": [
                "What is project 225",
                "What is project 221",
                "project 219",
                "project 222",
                "project 223",
                "project 224",
                "project 220",
            ],
            
            "5. Client & Contact Details": [
                "Does anyone work with Aaron from TGCS?",
                "Can you give me sample projects were client don't like",
                "builders that we've worked with before",
                "steel structure retrofit of an old brick building",
            ],
            
            "6. Superseded Folders": [
                "WHAT IS project 221 INCLUDE SUPERSEDED FOLDERS?",
                "I want to see what changed between the draft and the final issued specs for project 223",
                "Were there any older versions of the calculations issued before revision B?",
                "Include the superseded drawing files from 06_Calculations for project 220",
            ],
            
            "7. Engineering Advice & Summarization": [
                "What were the main design considerations mentioned in the final report for project 224?",
                "Summarize what kind of foundations were used across bridge projects completed in 2023",
                "What is the typical approach used for wind loading in these calculations?",
                "Can you advise what standard detail we usually use for timber bridges based on past projects?",
            ],
            
            "8. Client Issues & Warnings": [
                "Show me all emails or meeting notes for project 219 where the client raised concerns",
                "Were there any client complaints or rework requests for project 222?",
                "Flag any documents where there were major scope changes or client feedback for project 225",
                "Is there anything I should be cautious about before reusing specs from project 223?",
            ],
            
            "9. Advisory Recommendations": [
                "Should I reuse the stormwater report from project 225 for our next job?",
                "What should I be aware of when using these older calculation methods?",
                "Which of these foundation designs would be most suitable for soft soil conditions?",
                "Advise me on common pitfalls found in the final design phase based on our previous work",
            ],
            
            "10. Specific Material & Design Queries": [
                "I am designing a precast panel, please tell me all past project that has a scope about precast panel",
                "I am designing a timber retaining wall it's going to be 3m tall; can you provide me example past projects",
                "Please advise me on what DTCE has done in the past for a 2 storey concrete precast panel building",
                "I need timber connection details for joining a timber beam to a column",
                "What are the available sizes of LVL timber on the market?",
            ],
            
            "11. Template & Spreadsheet Access": [
                "Please provide me with the template we generally use for preparing a PS1",
                "Please provide me with the link or the file for the timber beam design spreadsheet that DTCE usually uses",
                "PS3 template",
                "PS1A to PS4 templates",
            ],
            
            "12. Scenario-Based Technical": [
                "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed",
                "What foundation systems have we used for houses on steep slopes in Wellington?",
                "Find projects where we designed concrete shear walls for seismic strengthening",
                "What connection details have we used for balconies on coastal apartment buildings?",
            ],
            
            "13. Problem-Solving & Lessons Learned": [
                "What issues have we run into when using screw piles in soft soils?",
                "Summarise any lessons learned from projects where retaining walls failed during construction",
                "What waterproofing methods have worked best for basement walls in high water table areas?",
                "Were there any lessons learned from project 224?",
            ],
            
            "14. Materials & Methods Comparisons": [
                "When have we chosen precast concrete over in-situ concrete for floor slabs, and why?",
                "What timber treatment levels have we specified for exterior beams in coastal conditions?",
                "Compare different seismic retrofit methods we've used for unreinforced masonry buildings",
            ],
        }
        
        # Run tests for each category
        total_questions = 0
        successful_searches = 0
        
        for category, questions in test_categories.items():
            print(f"\n{category}")
            print("-" * 50)
            
            for question in questions:
                total_questions += 1
                print(f"\n📝 Q{total_questions}: {question}")
                
                try:
                    # Search your index
                    results = retriever.retrieve(question, top_k=3)
                    
                    if results:
                        successful_searches += 1
                        print(f"✅ Found {len(results)} results:")
                        
                        for i, result in enumerate(results[:2], 1):
                            filename = result.metadata.get('filename', 'Unknown')
                            project = result.metadata.get('project_name', 'Unknown')
                            score = result.score
                            
                            print(f"   {i}. {filename} (Project: {project}, Score: {score:.1f})")
                            
                            # Show relevant content snippet
                            content = result.content[:200].replace('\n', ' ')
                            print(f"      📄 {content}...")
                    else:
                        print("❌ No results found")
                        
                except Exception as e:
                    print(f"❌ Search error: {e}")
                
                # Brief pause to avoid overwhelming the system
                time.sleep(0.1)
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Questions Tested: {total_questions}")
        print(f"Successful Searches: {successful_searches}")
        print(f"Success Rate: {successful_searches/total_questions*100:.1f}%")
        print(f"Total Documents in Index: 406,051")
        
        # Test different search strategies
        print(f"\n🔧 Testing Search Strategies:")
        
        # Test project-specific search
        project_results = retriever.search_by_project("219219", "structural")
        print(f"   Project-specific search (219219): {len(project_results)} results")
        
        # Test recent documents
        recent_results = retriever.get_recent_documents(top_k=5)
        print(f"   Recent documents: {len(recent_results)} results")
        
        # Test content type filtering
        doc_results = retriever.search_documents_only("concrete", top_k=5)
        print(f"   Document-only search: {len(doc_results)} results")
        
        print(f"\n✅ DTCE RAG System comprehensive test completed!")
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dtce_comprehensive()
