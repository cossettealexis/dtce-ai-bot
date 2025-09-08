#!/usr/bin/env python3
"""
Test the Universal AI Assistant with complex engineering scenarios
to verify ChatGPT-level conversation capabilities.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import get_settings
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncOpenAI

async def test_advanced_scenarios():
    """Test complex engineering scenarios that require ChatGPT-level intelligence."""
    
    settings = get_settings()
    
    # Initialize services
    search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key or settings.azure_openai_api_key)
    
    rag_handler = RAGHandler(
        search_client=search_client,
        openai_client=openai_client,
        model_name=settings.openai_model_name or settings.azure_openai_deployment_name
    )
    
    # Test scenarios from your requirements
    test_scenarios = [
        {
            "category": "Scenario-Based Technical",
            "query": "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed.",
            "expected_capabilities": ["project_search", "technical_filtering", "job_numbers", "design_examples"]
        },
        {
            "category": "Problem-Solving & Lessons Learned", 
            "query": "What issues have we run into when using screw piles in soft soils?",
            "expected_capabilities": ["lessons_learned", "technical_analysis", "problem_patterns", "solutions"]
        },
        {
            "category": "Cost & Time Insights",
            "query": "How long does it typically take from concept to PS1 for small commercial alterations?",
            "expected_capabilities": ["project_analytics", "time_analysis", "statistical_insights", "process_knowledge"]
        },
        {
            "category": "Materials & Methods Comparison",
            "query": "When have we chosen precast concrete over in-situ concrete for floor slabs, and why?",
            "expected_capabilities": ["comparative_analysis", "decision_reasoning", "technical_trade_offs", "case_studies"]
        },
        {
            "category": "ChatGPT-Style General",
            "query": "Explain the difference between ductile and brittle failure in structural engineering",
            "expected_capabilities": ["general_knowledge", "educational_explanation", "technical_concepts", "engineering_theory"]
        },
        {
            "category": "Hybrid DTCE + General",
            "query": "What are best practices for seismic design, and how do our DTCE projects implement these?",
            "expected_capabilities": ["general_best_practices", "dtce_specific_examples", "hybrid_response", "real_project_references"]
        }
    ]
    
    print("🧪 TESTING ADVANCED AI SCENARIOS")
    print("=" * 60)
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n📋 TEST {i}: {scenario['category']}")
        print(f"❓ Query: {scenario['query']}")
        print("-" * 50)
        
        try:
            # Test with universal AI assistant
            result = await rag_handler.universal_ai_assistant(scenario['query'])
            
            print(f"✅ Response Type: {result.get('rag_type', 'unknown')}")
            print(f"📁 Folder Searched: {result.get('folder_searched', 'none')}")
            print(f"📄 Documents Found: {result.get('documents_searched', 0)}")
            print(f"🎯 Confidence: {result.get('confidence', 'unknown')}")
            
            answer = result.get('answer', 'No answer generated')
            
            # Show first 300 characters of response
            preview = answer[:300] + "..." if len(answer) > 300 else answer
            print(f"\n💬 Response Preview:")
            print(f"   {preview}")
            
            # Analyze response quality
            response_analysis = await analyze_response_quality(answer, scenario['expected_capabilities'])
            print(f"\n📊 Quality Analysis:")
            for capability, score in response_analysis.items():
                status = "✅" if score >= 0.7 else "⚠️" if score >= 0.4 else "❌"
                print(f"   {status} {capability}: {score:.2f}")
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
    
    print(f"\n🏁 ADVANCED SCENARIO TESTING COMPLETE")
    print("=" * 60)

async def analyze_response_quality(answer: str, expected_capabilities: list) -> dict:
    """Simple heuristic analysis of response quality."""
    
    analysis = {}
    
    for capability in expected_capabilities:
        score = 0.0
        
        if capability == "project_search":
            # Look for project numbers, job references
            if any(term in answer.lower() for term in ["project", "job", "#", "225", "224", "example"]):
                score += 0.5
            if any(term in answer.lower() for term in ["timber", "wind", "building", "designed"]):
                score += 0.3
                
        elif capability == "technical_analysis":
            # Look for technical depth
            if any(term in answer.lower() for term in ["analysis", "design", "calculation", "specification"]):
                score += 0.4
            if any(term in answer.lower() for term in ["structural", "engineering", "technical", "method"]):
                score += 0.3
                
        elif capability == "general_knowledge":
            # Look for educational content
            if any(term in answer.lower() for term in ["explain", "definition", "concept", "principle"]):
                score += 0.4
            if any(term in answer.lower() for term in ["ductile", "brittle", "failure", "structural"]):
                score += 0.3
                
        elif capability == "hybrid_response":
            # Look for both general and specific content
            if any(term in answer.lower() for term in ["best practice", "industry standard", "general"]):
                score += 0.3
            if any(term in answer.lower() for term in ["dtce", "our project", "we", "example"]):
                score += 0.4
                
        else:
            # Generic capability scoring
            if len(answer) > 100:
                score += 0.3
            if any(term in answer.lower() for term in ["detailed", "comprehensive", "specific", "example"]):
                score += 0.2
            if "I don't" not in answer and "error" not in answer.lower():
                score += 0.2
        
        analysis[capability] = min(score, 1.0)
    
    return analysis

if __name__ == "__main__":
    asyncio.run(test_advanced_scenarios())
