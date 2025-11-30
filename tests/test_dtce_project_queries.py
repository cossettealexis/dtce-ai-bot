"""
Comprehensive test for DTCE Project queries
Tests various real-world scenarios employees might ask
"""
import asyncio
import sys
import os
import re

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.config.settings import Settings
from dtce_ai_bot.services.azure_rag_service_v2 import RAGOrchestrator
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

async def test_project_queries():
    """Test various project-related queries"""
    
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
    
    # Comprehensive test scenarios
    test_scenarios = [
        {
            "category": "YEAR-BASED QUERIES",
            "tests": [
                "show me all 2024 projects",
                "what projects did we do in 2023?",
                "list 2022 project numbers",
                "give me projects from 2021",
            ]
        },
        {
            "category": "TIME-RANGE QUERIES",
            "tests": [
                "show me projects from the past 2 years",
                "what projects from the last 3 years?",
                "give me project numbers from the past 4 years",
            ]
        },
        {
            "category": "SPECIFIC PROJECT QUERIES",
            "tests": [
                "tell me about project 224002",
                "what is project 223010?",
                "show me details for job 222039",
            ]
        },
        {
            "category": "PROJECT DOCUMENTS QUERIES",
            "tests": [
                "show me documents for project 224002",
                "what drawings do we have for project 224002?",
                "find the fee proposal for project 224002",
                "show me the structural calculations for project 224002",
            ]
        },
        {
            "category": "DRAWING & FILE QUERIES",
            "tests": [
                "find drawings for project 224002",
                "show me dwg files for 2024 projects",
                "what PDFs do we have for project 224002?",
                "find Excel files for project 224002",
            ]
        },
        {
            "category": "PROJECT SEARCH QUERIES",
            "tests": [
                "find projects in Tawa",
                "show me residential projects",
                "what commercial projects do we have?",
                "find all projects with retaining walls",
            ]
        },
        {
            "category": "GENERAL PROJECT QUERIES",
            "tests": [
                "how many projects do we have?",
                "what are our recent projects?",
                "show me all project numbers",
            ]
        },
    ]
    
    print("=" * 100)
    print("COMPREHENSIVE DTCE PROJECT QUERY TEST")
    print("=" * 100)
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": 0
    }
    
    for scenario in test_scenarios:
        print(f"\n{'='*100}")
        print(f"📁 {scenario['category']}")
        print(f"{'='*100}")
        
        for i, query in enumerate(scenario['tests'], 1):
            results["total"] += 1
            print(f"\n{'-'*100}")
            print(f"Test {i}: \"{query}\"")
            print(f"{'-'*100}")
            
            try:
                result = await orchestrator.process_question(query, session_id=f"test_{scenario['category']}_{i}")
                
                intent = result.get('intent', 'N/A')
                filter_used = result.get('search_filter', 'None')
                total_docs = result.get('total_documents', 0)
                answer = result.get('answer', '')
                
                print(f"✓ Intent: {intent}")
                print(f"✓ Filter: {filter_used[:100]}..." if len(str(filter_used)) > 100 else f"✓ Filter: {filter_used}")
                print(f"✓ Documents Found: {total_docs}")
                
                # Extract project numbers from answer
                project_numbers = re.findall(r'\b(2[12][0-9]\d{3})\b', answer)
                unique_projects = list(set(project_numbers))
                
                # Validation
                is_valid = True
                issues = []
                
                # Check if intent is appropriate
                if 'project' in query.lower() and intent != 'Project':
                    is_valid = False
                    issues.append(f"❌ Expected 'Project' intent but got '{intent}'")
                
                # Check if documents were found for project queries
                if intent == 'Project' and total_docs == 0:
                    is_valid = False
                    issues.append("❌ No documents found for project query")
                
                # Check if answer contains project numbers for listing queries
                if any(keyword in query.lower() for keyword in ['show', 'list', 'give me', 'what projects']):
                    if len(unique_projects) == 0:
                        is_valid = False
                        issues.append("⚠️  No project numbers found in answer")
                    else:
                        print(f"✓ Found {len(unique_projects)} unique project numbers: {unique_projects[:5]}{'...' if len(unique_projects) > 5 else ''}")
                
                # Check if answer is meaningful
                if len(answer) < 50:
                    is_valid = False
                    issues.append("❌ Answer too short")
                
                # Print answer preview
                print(f"\n📄 Answer Preview (first 300 chars):")
                print(f"{answer[:300]}...")
                
                if is_valid:
                    print(f"\n✅ PASSED")
                    results["passed"] += 1
                else:
                    print(f"\n⚠️  PASSED WITH WARNINGS:")
                    for issue in issues:
                        print(f"   {issue}")
                    results["passed"] += 1
                    
            except Exception as e:
                print(f"\n❌ FAILED: {str(e)}")
                results["failed"] += 1
                import traceback
                traceback.print_exc()
    
    # Print summary
    print(f"\n{'='*100}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*100}")
    print(f"Total Tests: {results['total']}")
    print(f"✅ Passed: {results['passed']} ({results['passed']/results['total']*100:.1f}%)")
    print(f"❌ Failed: {results['failed']} ({results['failed']/results['total']*100:.1f}%)")
    print(f"{'='*100}")
    
    await search_client.close()
    await openai_client.close()

if __name__ == "__main__":
    asyncio.run(test_project_queries())
