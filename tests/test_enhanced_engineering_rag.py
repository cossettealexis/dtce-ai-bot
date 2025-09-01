#!/usr/bin/env python3
"""
Test Enhanced Engineering RAG Handler
Tests all the specific engineering use cases from the FAQ:
- NZ Standards queries
- Project references  
- Product specifications
- Design discussions
- Contractor references
- Template access
- Scope comparisons
"""
import asyncio
import sys
import os
from typing import Dict, List
from dotenv import load_dotenv

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.integrations.azure_search import get_search_client
from dtce_ai_bot.services.enhanced_engineering_rag import EnhancedEngineeringRAGHandler
from openai import AsyncAzureOpenAI

# Load environment variables
load_dotenv()


async def test_engineering_rag_handler():
    """Test the enhanced engineering RAG handler with FAQ examples."""
    
    # Initialize the enhanced engineering RAG handler
    settings = get_settings()
    search_client = get_search_client()
    
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    engineering_rag = EnhancedEngineeringRAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
    
    # Test cases from the FAQ
    engineering_test_cases = {
        "NZ Standards": [
            "Please tell me the minimum clear cover requirements as per NZS code in designing a concrete element",
            "Tell me what particular clause that talks about the detailing requirements in designing a beam",
            "Tell me the strength reduction factors used when I'm designing a beam or when considering seismic actions",
            "Tell me what particular NZS structural code to refer with if I'm designing a composite slab to make it as floor diaphragm?"
        ],
        
        "Project References": [
            "I am designing a precast panel, please tell me all past project that has a scope about the following keywords: Precast Panel, Precast, Precast Connection, Unispans",
            "I am designing a timber retaining wall it's going to be 3m tall; can you provide me example past projects and help me draft a design philosophy?",
            "Please advise me on what DTCE has done in the past for a 2 storey concrete precast panel building maybe with a timber framed structure on top?"
        ],
        
        "Product Specifications": [
            "I'm looking for a specific proprietary product that's suitable to provide a waterproofing layer to a concrete block wall that DTCE has used in the past",
            "I need timber connection details for joining a timber beam to a column. Please provide specifications for the proprietary products DTCE usually refers to, as well as other options to consider",
            "What are the available sizes of LVL timber on the market? Please list all links containing the sizes and price per length. Also, confirm if the suppliers are located near Wellington"
        ],
        
        "Design Discussions": [
            "I am currently designing a composite beam but need to make it haunched/tapered. Please provide related references or online threads mentioning the keyword 'tapered composite beam', preferably from anonymous structural engineers",
            "Please provide design guidelines for a reinforced concrete column to withstand both seismic and gravity actions. If possible, include a legitimate link that gives direct access to the specific design guidelines"
        ],
        
        "Contractor References": [
            "My client is asking about builders that we've worked with before. Can you find any companies and or contact details that constructed a design for us in the past 3 years and didn't seem to have too many issues during construction. The design job I'm dealing with now is a steel structure retrofit of an old brick building"
        ],
        
        "Template Access": [
            "Please provide me with the template we generally use for preparing a PS1. Also, please provide me with the direct link to access it on SuiteFiles",
            "I wasn't able to find a PS3 template in SuiteFiles. Please provide me with a legitimate link to a general PS3 template that can be submitted to any council in New Zealand",
            "Please provide me with the link or the file for the timber beam design spreadsheet that DTCE usually uses or has used"
        ],
        
        "Scope Comparison": [
            "Here's the request for a fee proposal from an architect. Can you find me past DTCE projects that had similar scope to this? It looks like a double cantilever corner window. We're after a proposal for some SED structure required for a residential renovation in Seatoun. Likely scope would be for posts and beams supporting roof above a new sliding door corner unit at first floor level"
        ]
    }
    
    print("🔧 ENHANCED ENGINEERING RAG HANDLER TEST")
    print("=" * 80)
    print("Testing specialized engineering query handling with FAQ examples...")
    print("=" * 80)
    
    total_tests = 0
    successful_responses = 0
    
    for category, test_queries in engineering_test_cases.items():
        print(f"\n📋 Testing {category.upper()} Queries:")
        print("-" * 60)
        
        for query in test_queries:
            total_tests += 1
            
            try:
                print(f"\n🔍 Query: {query[:80]}{'...' if len(query) > 80 else ''}")
                
                # Test the enhanced engineering RAG
                response = await engineering_rag.get_engineering_answer(query)
                
                answer = response.get("answer", "No answer")
                engineering_type = response.get("engineering_type", "unknown")
                intent = response.get("intent", "unknown") 
                sources = response.get("sources", [])
                
                # Check if we got a meaningful response
                if len(answer) > 50 and "error" not in answer.lower():
                    successful_responses += 1
                    status = "✅"
                else:
                    status = "⚠️"
                
                print(f"   {status} Engineering Type: {engineering_type}")
                print(f"   📊 Intent: {intent}")
                print(f"   📄 Sources: {len(sources)} documents found")
                print(f"   💬 Response Length: {len(answer)} characters")
                print(f"   📝 Preview: {answer[:200]}{'...' if len(answer) > 200 else ''}")
                
                # Check for specific formatting based on engineering type
                format_quality = _assess_response_format(answer, engineering_type)
                print(f"   🎯 Format Quality: {format_quality}")
                
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
    
    # Calculate success rate
    success_rate = (successful_responses / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"\n" + "="*80)
    print(f"📊 ENHANCED ENGINEERING RAG TEST RESULTS:")
    print(f"Total Tests: {total_tests}")
    print(f"Successful Responses: {successful_responses}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("✅ EXCELLENT: Engineering RAG handler is working great!")
    elif success_rate >= 75:
        print("✅ GOOD: Engineering RAG handler is working well")
    elif success_rate >= 60:
        print("⚠️  FAIR: Engineering RAG handler needs improvement")
    else:
        print("❌ POOR: Engineering RAG handler needs major work")
    
    print("="*80)
    
    # Test specific engineering patterns
    print("\n🎯 TESTING ENGINEERING PATTERN DETECTION:")
    print("-" * 50)
    
    pattern_tests = [
        ("NZS 3101 clause requirements", "technical_standard"),
        ("precast panel project references", "project_reference"), 
        ("timber connection products", "product_specification"),
        ("composite beam discussions", "design_discussion"),
        ("steel retrofit contractors", "contractor_reference"),
        ("PS1 template access", "template_access"),
        ("cantilever window scope", "scope_comparison")
    ]
    
    for query, expected_type in pattern_tests:
        detected_type = engineering_rag._detect_engineering_query_type(query)
        status = "✅" if detected_type == expected_type else "❌"
        print(f"   {status} '{query}' → Expected: {expected_type}, Detected: {detected_type}")


def _assess_response_format(answer: str, engineering_type: str) -> str:
    """Assess if the response follows the expected format for the engineering type."""
    
    format_criteria = {
        "technical_standard": ["NZS", "clause", "according to", "minimum", "requirement"],
        "project_reference": ["job", "project", "reference", "suitefiles", "scope"],
        "product_specification": ["product", "supplier", "specification", "contact", "wellington"],
        "design_discussion": ["forum", "discussion", "link", "thread", "engineering"],
        "contractor_reference": ["company", "contact", "experience", "performance", "past"],
        "template_access": ["template", "suitefiles", "link", "download", "ps1"],
        "scope_comparison": ["similar", "project", "scope", "fee", "comparison"]
    }
    
    expected_terms = format_criteria.get(engineering_type, [])
    answer_lower = answer.lower()
    
    found_terms = sum(1 for term in expected_terms if term in answer_lower)
    coverage = (found_terms / len(expected_terms)) * 100 if expected_terms else 0
    
    if coverage >= 80:
        return f"Excellent ({coverage:.0f}%)"
    elif coverage >= 60:
        return f"Good ({coverage:.0f}%)"
    elif coverage >= 40:
        return f"Fair ({coverage:.0f}%)"
    else:
        return f"Poor ({coverage:.0f}%)"


async def main():
    """Run enhanced engineering RAG tests."""
    await test_engineering_rag_handler()


if __name__ == "__main__":
    asyncio.run(main())
