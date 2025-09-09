#!/usr/bin/env python3
"""URGENT: Test top 5 critical questions for 12pm deadline"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def quick_test():
    try:
        from dtce_ai_bot.main import app
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
        
        # TOP 5 CRITICAL QUESTIONS FOR DEADLINE
        critical_questions = [
            "What is our wellness policy?",
            "What is project 225?", 
            "Tell me the minimum clear cover requirements as per NZS code in designing a concrete element",
            "I am designing a precast panel, please tell me all past projects that have scope about: Precast Panel, Precast, Precast Connection",
            "Can you find me past DTCE projects with double cantilever corner window for posts and beams supporting roof above sliding door?"
        ]
        
        print("🚨 URGENT TEST - 5 Critical Questions for 12pm Deadline")
        print("=" * 60)
        
        for i, q in enumerate(critical_questions, 1):
            print(f"\n🔥 Q{i}: {q}")
            print("-" * 40)
            
            try:
                response = await rag.get_response(q)
                print(f"✅ RESPONSE ({len(response)} chars):")
                print(response)
                
                if len(response) > 200 and "I don't have information" not in response:
                    print("🎯 GOOD: Detailed response generated!")
                else:
                    print("⚠️  ISSUE: Response too short or no info found")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")
            
            print("=" * 60)
            
        print("\n🚀 QUICK TEST COMPLETE - Check if responses are comprehensive enough")
        
    except Exception as e:
        print(f"❌ SETUP ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(quick_test())
