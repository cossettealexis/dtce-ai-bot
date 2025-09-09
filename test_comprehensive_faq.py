#!/usr/bin/env python3
"""
COMPREHENSIVE TEST: ALL FAQ Questions for DTCE AI Bot
Testing production system with increased content limits (15K chars)
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_all_faq_questions():
    try:
        from dtce_ai_bot.services.rag_handler import RAGHandler
        from dtce_ai_bot.config.settings import Settings
        from azure.search.documents.aio import SearchClient
        from azure.core.credentials import AzureKeyCredential
        from openai import AsyncAzureOpenAI
        
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
        
        # ALL CRITICAL FAQ QUESTIONS ORGANIZED BY CATEGORY
        test_questions = {
            "1. POLICY QUESTIONS": [
                "What is our wellness policy?",
                "What's our wellness policy and what does it say?",
                "wellness policy",
                "wellbeing policy"
            ],
            
            "2. PROJECT REFERENCE QUESTIONS": [
                "Does anyone work with Aaron from TGCS?",
                "What is project 225?",
                "Can you give me sample projects where clients don't like?",
                "Can you find me past DTCE projects that had similar scope to this? It looks like a double cantilever corner window for posts and beams supporting roof above a new sliding door corner unit at first floor level, supported by concrete wall structure and concrete beam below."
            ],
            
            "3. NZ STANDARDS QUESTIONS": [
                "Tell me the minimum clear cover requirements as per NZS code in designing a concrete element",
                "Tell me what particular clause that talks about the detailing requirements in designing a beam",
                "Tell me the strength reduction factors used when I'm designing a beam or when considering seismic actions",
                "Tell me what particular NZS structural code to refer with if I'm designing a composite slab to make it as floor diaphragm?"
            ],
            
            "4. TECHNICAL PROCEDURES QUESTIONS": [
                "How do I use the site wind speed spreadsheet?",
                "Please provide me with the template we generally use for preparing a PS1. Also, please provide me with the direct link to access it on SuiteFiles.",
                "Please provide me with the link or file for the timber beam design spreadsheet that DTCE usually uses or has used."
            ],
            
            "5. PRECAST/STRUCTURAL DESIGN QUESTIONS": [
                "I am designing a precast panel, please tell me all past projects that have scope about: Precast Panel, Precast, Precast Connection, Unispans",
                "I am designing a timber retaining wall 3m tall; can you provide example past projects and help me draft a design philosophy?",
                "Please advise me on what DTCE has done in the past for a 2 storey concrete precast panel building maybe with a timber framed structure on top?"
            ],
            
            "6. SUPERSEDED/VERSION CONTROL QUESTIONS": [
                "Can you also include any superseded reports for project 221?",
                "I want to see what changed between the draft and the final issued specs for project 223.",
                "Were there any older versions of the calculations issued before revision B?",
                "Include the superseded drawing files from 06_Calculations for project 220."
            ],
            
            "7. ENGINEERING ADVICE QUESTIONS": [
                "What were the main design considerations mentioned in the final report for project 224?",
                "Summarize what kind of foundations were used across bridge projects completed in 2023.",
                "What is the typical approach used for wind loading in these calculations?",
                "Can you advise what standard detail we usually use for timber bridges based on past projects?"
            ],
            
            "8. CLIENT ISSUE DETECTION QUESTIONS": [
                "Show me all emails or meeting notes for project 219 where the client raised concerns.",
                "Were there any client complaints or rework requests for project 222?",
                "Flag any documents where there were major scope changes or client feedback for project 225.",
                "Is there anything I should be cautious about before reusing specs from project 223?"
            ],
            
            "9. ADVISORY RECOMMENDATION QUESTIONS": [
                "Should I reuse the stormwater report from project 225 for our next job?",
                "What should I be aware of when using these older calculation methods?",
                "Which of these foundation designs would be most suitable for soft soil conditions?",
                "Advise me on common pitfalls found in the final design phase based on our previous work."
            ],
            
            "10. COMBINED KNOWLEDGE QUESTIONS": [
                "What stormwater management approach was used in project 223 and is it compliant with NZS 4404?",
                "Based on project 220 specs, which clauses in NZS 3910 should we refer to when issuing to the client?",
                "What do our past issued specs say about timber treatment, and how does that align with NZ standards?",
                "Summarize typical QA procedures used in past projects and cross-check with SuiteFiles templates."
            ],
            
            "11. LESSONS LEARNED QUESTIONS": [
                "Were there any lessons learned from project 224?",
                "Summarize mistakes made during internal review stages across past projects.",
                "What are common issues during the 'Issued' phase we should avoid?",
                "If I'm writing a new report for a bridge project, what should I not do based on past documents?"
            ],
            
            "12. BUILDER/CLIENT CONTACT QUESTIONS": [
                "Can you find any companies and contact details that constructed a design for us in the past 3 years and didn't seem to have too many issues during construction? The design job I'm dealing with now is a steel structure retrofit of an old brick building."
            ],
            
            "13. PRODUCT SPECIFICATION QUESTIONS": [
                "I need timber connection details for joining a timber beam to a column. Please provide specifications for the proprietary products DTCE usually refers to, as well as other options to consider.",
                "What are the available sizes of LVL timber on the market? Please list all links containing the sizes and price per length. Also, confirm if the suppliers are located near Wellington."
            ]
        }
        
        print("🚀 COMPREHENSIVE FAQ TEST - ALL CATEGORIES")
        print("=" * 80)
        print(f"Testing {sum(len(questions) for questions in test_questions.values())} total questions")
        print("=" * 80)
        
        total_questions = 0
        successful_responses = 0
        comprehensive_responses = 0
        
        for category, questions in test_questions.items():
            print(f"\n📁 {category}")
            print("=" * 60)
            
            for i, question in enumerate(questions, 1):
                total_questions += 1
                print(f"\n🔍 Q{i}: {question}")
                print("-" * 50)
                
                try:
                    result = await rag.process_question(question)
                    answer = result.get('answer', 'No answer')
                    
                    print(f"✅ RESPONSE ({len(answer)} chars):")
                    print(answer[:300] + ("..." if len(answer) > 300 else ""))
                    
                    if answer and "I don't have information" not in answer and "I cannot find" not in answer:
                        successful_responses += 1
                        if len(answer) > 500:
                            comprehensive_responses += 1
                            print("🎯 EXCELLENT: Comprehensive response!")
                        else:
                            print("✅ GOOD: Response provided")
                    else:
                        print("⚠️  WARNING: No information found")
                        
                except Exception as e:
                    print(f"❌ ERROR: {str(e)}")
                
                print("-" * 50)
            
            print(f"\n📊 {category} Complete")
        
        print("\n" + "=" * 80)
        print("🎯 FINAL RESULTS SUMMARY")
        print("=" * 80)
        print(f"Total Questions Tested: {total_questions}")
        print(f"Successful Responses: {successful_responses} ({successful_responses/total_questions*100:.1f}%)")
        print(f"Comprehensive Responses (>500 chars): {comprehensive_responses} ({comprehensive_responses/total_questions*100:.1f}%)")
        
        if comprehensive_responses > total_questions * 0.7:
            print("🚀 EXCELLENT: AI providing comprehensive responses!")
        elif successful_responses > total_questions * 0.8:
            print("✅ GOOD: AI responding well to most questions")
        else:
            print("⚠️  NEEDS IMPROVEMENT: Many questions not getting good responses")
        
        print("=" * 80)
        print("🎯 FAQ TEST COMPLETE - Ready for 12pm deadline!")
        
    except Exception as e:
        print(f"❌ SETUP ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_all_faq_questions())
