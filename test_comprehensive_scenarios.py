#!/usr/bin/env python3
"""
Comprehensive test suite for DTCE AI Bot
Tests all the real-world scenarios and FAQ requirements
"""
import asyncio
import sys
import os
import time

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import Settings
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

async def test_comprehensive_scenarios():
    """Test all the real-world DTCE scenarios."""
    print("🧠 COMPREHENSIVE DTCE AI BOT TEST SUITE")
    print("=" * 60)
    
    try:
        settings = Settings()
        
        # Initialize clients
        search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_admin_key)
        )
        
        openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        
        rag = RAGHandler(
            search_client=search_client,
            openai_client=openai_client,
            model_name=settings.azure_openai_deployment_name
        )
        
        # Test scenarios organized by category
        test_groups = {
            "📋 FAQ QUESTIONS": [
                "What is our wellness policy?",
                "What's our wellness policy and what does it say?",
                "Does anyone work with Aaron from TGCS?",
                "What is project 225?",
                "Can you give me sample projects where client don't like"
            ],
            
            "📁 SUPERSEDED DOCUMENTS": [
                "Can you also include any superseded reports for project 221?",
                "I want to see what changed between the draft and the final issued specs for project 223.",
                "Were there any older versions of the calculations issued before revision B?",
                "Include the superseded drawing files from 06_Calculations for project 220."
            ],
            
            "💡 ENGINEERING ADVICE & SUMMARIES": [
                "What were the main design considerations mentioned in the final report for project 224?",
                "Summarize what kind of foundations were used across bridge projects completed in 2023.",
                "What is the typical approach used for wind loading in these calculations?",
                "Can you advise what standard detail we usually use for timber bridges based on past projects?"
            ],
            
            "⚠️ CLIENT WARNINGS & ISSUES": [
                "Show me all emails or meeting notes for project 219 where the client raised concerns.",
                "Were there any client complaints or rework requests for project 222?",
                "Flag any documents where there were major scope changes or client feedback for project 225.",
                "Is there anything I should be cautious about before reusing specs from project 223?"
            ],
            
            "🎯 ADVISORY RECOMMENDATIONS": [
                "Should I reuse the stormwater report from project 225 for our next job?",
                "What should I be aware of when using these older calculation methods?",
                "Which of these foundation designs would be most suitable for soft soil conditions?",
                "Advise me on common pitfalls found in the final design phase based on our previous work."
            ],
            
            "📖 NZ STANDARDS & CODES": [
                "Please tell me that minimum clear cover requirements as per NZS code in designing a concrete element",
                "Tell me what particular clause that talks about the detailing requirements in designing a beam",
                "Tell me the strength reduction factors used when I'm designing a beam or when considering seismic actions",
                "Tell me what particular NZS structural code to refer with if I'm designing a composite slab to make it as floor diaphragm?"
            ],
            
            "🔍 PROJECT REFERENCE SEARCHES": [
                "I am designing a precast panel, please tell me all past project that has a scope about precast panel, precast, precast connection, unispans",
                "I am designing a timber retaining wall it's going to be 3m tall; can you provide me example past projects and help me draft a design philosophy?",
                "Please advise me on what DTCE has done in the past for a 2 storey concrete precast panel building maybe with a timber framed structure on top?"
            ],
            
            "🛠️ PRODUCT SPECIFICATIONS": [
                "I need timber connection details for joining a timber beam to a column. Please provide specifications for the proprietary products DTCE usually refers to",
                "What are the available sizes of LVL timber on the market? Please list all links containing the sizes and price per length",
                "I'm looking for a specific proprietary product that's suitable to provide a waterproofing layer to a concrete block wall that DTCE has used in the past"
            ],
            
            "👥 CLIENT & CONTRACTOR REFERENCES": [
                "My client is asking about builders that we've worked with before. Can you find any companies and contact details that constructed a design for us in the past 3 years?",
                "Can you find me past DTCE projects that had similar scope to a double cantilever corner window for residential renovation?"
            ],
            
            "📋 TEMPLATES & FORMS": [
                "Please provide me with the template we generally use for preparing a PS1. Also, please provide me with the direct link to access it on SuiteFiles",
                "I wasn't able to find a PS3 template in SuiteFiles. Please provide me with a legitimate link to a general PS3 template",
                "Please provide me with the link or the file for the timber beam design spreadsheet that DTCE usually uses"
            ]
        }
        
        total_tests = sum(len(questions) for questions in test_groups.values())
        current_test = 0
        
        for group_name, questions in test_groups.items():
            print(f"\n{group_name}")
            print("-" * 50)
            
            for question in questions:
                current_test += 1
                print(f"\n{current_test}/{total_tests}. Testing: '{question[:80]}{'...' if len(question) > 80 else ''}'")
                
                try:
                    start_time = time.time()
                    result = await rag.universal_ai_assistant(question)
                    end_time = time.time()
                    
                    category = result.get('prompt_category', 'Unknown')
                    docs_found = result.get('documents_searched', 0)
                    response = result.get('answer', 'No response')
                    
                    print(f"   📂 Category: {category}")
                    print(f"   📊 Documents: {docs_found}")
                    print(f"   ⏱️ Time: {end_time - start_time:.1f}s")
                    print(f"   💬 Response: {response[:150]}{'...' if len(response) > 150 else ''}")
                    
                    # Evaluate response quality
                    if docs_found > 0 and len(response) > 50:
                        print("   ✅ GOOD: Found documents and provided substantial response")
                    elif category != 'Unknown' and len(response) > 50:
                        print("   ✅ GOOD: Proper categorization and response")
                    else:
                        print("   ⚠️ CHECK: Limited response or categorization")
                        
                except Exception as e:
                    print(f"   ❌ ERROR: {e}")
                    
                # Small delay to avoid overwhelming the API
                await asyncio.sleep(0.5)
        
        print(f"\n🎯 COMPREHENSIVE TEST COMPLETED")
        print(f"Total tests run: {total_tests}")
        print("=" * 60)
        
        await search_client.close()
        await openai_client.close()
        
    except Exception as e:
        print(f"❌ Setup Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_comprehensive_scenarios())
