#!/usr/bin/env python3
"""
Comprehensive test of ALL critical DTCE AI questions for deadline.
"""
import asyncio
from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import Settings
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

async def test_all_questions():
    """Test all critical questions with improved content limits."""
    
    # Initialize properly
    settings = Settings()
    search_client = SearchClient(
        endpoint=f'https://{settings.azure_search_service_name}.search.windows.net',
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    rag = RAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
    
    # Critical questions from user's list
    questions = [
        # Basic Policy Questions
        "What is our wellness policy?",
        "What's our wellness policy and what does it say?",
        
        # Project Questions
        "Does anyone work with Aaron from TGCS?",
        "What is project 225?",
        "Can you give me sample projects where clients don't like?",
        
        # NZ Standards Questions
        "Tell me the minimum clear cover requirements as per NZS code in designing a concrete element",
        "Tell me the strength reduction factors used when designing a beam or when considering seismic actions",
        
        # Project Reference Questions
        "I am designing a precast panel, please tell me all past projects that have scope about: Precast Panel, Precast, Precast Connection, Unispans",
        "I am designing a timber retaining wall 3m tall; can you provide example past projects and help me draft a design philosophy?",
        
        # Client/Builder Questions
        "Can you find any companies and contact details that constructed a design for us in the past 3 years and didn't have too many issues during construction? The design job I'm dealing with now is a steel structure retrofit of an old brick building.",
        
        # Template Questions
        "Please provide me with the template we generally use for preparing a PS1. Also, please provide me with the direct link to access it on SuiteFiles.",
        "Please provide me with the link or file for the timber beam design spreadsheet that DTCE usually uses.",
        
        # Cantilever Window Project
        "Can you find me past DTCE projects that had similar scope to this? It looks like a double cantilever corner window for posts and beams supporting roof above a new sliding door corner unit at first floor level, supported by concrete wall structure and concrete beam below.",
        
        # Engineering Advice Questions
        "What were the main design considerations mentioned in the final report for project 224?",
        "What is the typical approach used for wind loading in these calculations?",
        "Should I reuse the stormwater report from project 225 for our next job?",
        
        # Superseded/Version Control
        "Can you also include any superseded reports for project 221?",
        "Were there any older versions of the calculations issued before revision B?",
        
        # Client Issues Detection
        "Show me all emails or meeting notes for project 219 where the client raised concerns.",
        "Were there any client complaints or rework requests for project 222?",
        
        # Lessons Learned
        "Were there any lessons learned from project 224?",
        "What are common issues during the 'Issued' phase we should avoid?"
    ]
    
    print(f"🚀 Testing {len(questions)} critical questions with improved content limits...")
    print("=" * 80)
    
    for i, question in enumerate(questions, 1):
        print(f"\n🔍 QUESTION {i}/{len(questions)}: {question}")
        print("-" * 60)
        
        try:
            response = await rag.get_response(question)
            print(f"✅ RESPONSE ({len(response)} chars):")
            print(response[:500] + ("..." if len(response) > 500 else ""))
            
            # Quick quality check
            if len(response) < 100:
                print("⚠️  WARNING: Short response - may need investigation")
            elif "I don't have information" in response or "I cannot find" in response:
                print("⚠️  WARNING: No information found")
            else:
                print("✅ GOOD: Comprehensive response generated")
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
        
        print("=" * 80)
    
    print("\n🎯 ALL QUESTIONS TESTED - Check responses above for quality")

if __name__ == "__main__":
    asyncio.run(test_all_questions())
