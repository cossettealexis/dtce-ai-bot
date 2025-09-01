#!/usr/bin/env python3
"""
Test Advanced Scenario-Based Engineering Queries
Tests sophisticated engineering use cases including:
- Scenario-based technical queries
- Problem-solving & lessons learned
- Regulatory & consent precedents
- Cost & time insights
- Best practices & templates
- Materials & methods comparisons
- Internal knowledge mapping
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


async def test_advanced_engineering_scenarios():
    """Test advanced scenario-based engineering queries."""
    
    # Initialize the enhanced engineering RAG handler
    settings = get_settings()
    search_client = get_search_client()
    
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    engineering_rag = EnhancedEngineeringRAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
    
    # Advanced engineering test cases
    advanced_test_cases = {
        "Scenario-Based Technical": [
            "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed",
            "What foundation systems have we used for houses on steep slopes in Wellington?",
            "Find projects where we designed concrete shear walls for seismic strengthening",
            "What connection details have we used for balconies on coastal apartment buildings?"
        ],
        
        "Problem-Solving & Lessons Learned": [
            "What issues have we run into when using screw piles in soft soils?",
            "Summarise any lessons learned from projects where retaining walls failed during construction",
            "What waterproofing methods have worked best for basement walls in high water table areas?"
        ],
        
        "Regulatory & Consent Precedents": [
            "Give me examples of projects where council questioned our wind load calculations",
            "How have we approached alternative solution applications for non-standard stair designs?",
            "Show me precedent for using non-standard bracing in heritage building retrofits"
        ],
        
        "Cost & Time Insights": [
            "How long does it typically take from concept to PS1 for small commercial alterations?",
            "What's the typical cost range for structural design of multi-unit residential projects?",
            "Find projects where the structural scope expanded significantly after concept design"
        ],
        
        "Best Practices & Templates": [
            "What's our standard approach to designing steel portal frames for industrial buildings?",
            "Show me our best example drawings for timber diaphragm design",
            "What calculation templates do we have for multi-storey timber buildings?"
        ],
        
        "Materials & Methods Comparisons": [
            "When have we chosen precast concrete over in-situ concrete for floor slabs, and why?",
            "What timber treatment levels have we specified for exterior beams in coastal conditions?",
            "Compare different seismic retrofit methods we've used for unreinforced masonry buildings"
        ],
        
        "Internal Knowledge Mapping": [
            "Which engineers have experience with tilt-slab construction?",
            "Who has documented expertise in pile design for soft coastal soils?",
            "Show me project notes authored by our senior engineer on seismic strengthening"
        ]
    }
    
    print("🏗️  ADVANCED SCENARIO-BASED ENGINEERING QUERIES TEST")
    print("=" * 80)
    print("Testing sophisticated engineering analysis and knowledge synthesis...")
    print("=" * 80)
    
    total_tests = 0
    successful_responses = 0
    category_results = {}
    
    for category, test_queries in advanced_test_cases.items():
        print(f"\n📋 Testing {category.upper()}:")
        print("-" * 60)
        
        category_success = 0
        category_total = len(test_queries)
        
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
                
                # Assess response quality for advanced queries
                quality_score = _assess_advanced_response_quality(answer, engineering_type, category)
                
                if quality_score >= 3:  # 3+ out of 5 quality score
                    successful_responses += 1
                    category_success += 1
                    status = "✅"
                elif quality_score >= 2:
                    status = "⚠️"
                else:
                    status = "❌"
                
                print(f"   {status} Engineering Type: {engineering_type}")
                print(f"   📊 Intent: {intent}")
                print(f"   📄 Sources: {len(sources)} documents found")
                print(f"   🎯 Quality Score: {quality_score}/5")
                print(f"   💬 Response Length: {len(answer)} characters")
                print(f"   📝 Preview: {answer[:200]}{'...' if len(answer) > 200 else ''}")
                
                # Check for advanced analysis indicators
                analysis_indicators = _check_advanced_analysis_indicators(answer, category)
                if analysis_indicators:
                    print(f"   🔬 Analysis Elements: {', '.join(analysis_indicators)}")
                
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
        
        category_results[category] = {
            "success": category_success,
            "total": category_total,
            "rate": (category_success / category_total) * 100 if category_total > 0 else 0
        }
    
    # Overall results
    success_rate = (successful_responses / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"\n" + "="*80)
    print(f"📊 ADVANCED ENGINEERING SCENARIOS TEST RESULTS:")
    print(f"Total Tests: {total_tests}")
    print(f"Successful Responses: {successful_responses}")
    print(f"Overall Success Rate: {success_rate:.1f}%")
    print("\n📈 Category Breakdown:")
    
    for category, results in category_results.items():
        print(f"   {category}: {results['rate']:.1f}% ({results['success']}/{results['total']})")
    
    if success_rate >= 85:
        print("\n✅ EXCELLENT: Advanced engineering scenarios handled expertly!")
    elif success_rate >= 70:
        print("\n✅ GOOD: Advanced engineering scenarios handled well")
    elif success_rate >= 55:
        print("\n⚠️  FAIR: Advanced engineering scenarios need improvement")
    else:
        print("\n❌ POOR: Advanced engineering scenarios need major work")
    
    print("="*80)
    
    # Test pattern detection for advanced scenarios
    print("\n🎯 TESTING ADVANCED PATTERN DETECTION:")
    print("-" * 50)
    
    pattern_tests = [
        ("mid-rise timber frame buildings", "scenario_technical"),
        ("issues with screw piles", "problem_solving"),
        ("council questioned wind loads", "regulatory_precedents"),
        ("cost range for structural design", "cost_time_insights"),
        ("standard approach to steel portal frames", "best_practices"),
        ("chosen precast over in-situ concrete", "materials_comparison"),
        ("engineers with tilt-slab experience", "knowledge_mapping")
    ]
    
    pattern_accuracy = 0
    for query, expected_type in pattern_tests:
        detected_type = engineering_rag._detect_engineering_query_type(query)
        if detected_type == expected_type:
            pattern_accuracy += 1
            status = "✅"
        else:
            status = "❌"
        print(f"   {status} '{query}' → Expected: {expected_type}, Detected: {detected_type}")
    
    pattern_rate = (pattern_accuracy / len(pattern_tests)) * 100
    print(f"\n🎯 Pattern Detection Accuracy: {pattern_rate:.1f}% ({pattern_accuracy}/{len(pattern_tests)})")


def _assess_advanced_response_quality(answer: str, engineering_type: str, category: str) -> int:
    """Assess response quality for advanced engineering scenarios (1-5 scale)."""
    
    answer_lower = answer.lower()
    quality_score = 1  # Base score
    
    # Check for technical depth
    technical_terms = ["project", "design", "structural", "engineering", "analysis", "specification"]
    if sum(1 for term in technical_terms if term in answer_lower) >= 3:
        quality_score += 1
    
    # Check for specific references
    specific_refs = ["job #", "nzs", "wellington", "auckland", "concrete", "steel", "timber"]
    if sum(1 for ref in specific_refs if ref in answer_lower) >= 2:
        quality_score += 1
    
    # Check for comparative/analytical content
    analytical_terms = ["compare", "analysis", "performance", "lessons", "approach", "method"]
    if sum(1 for term in analytical_terms if term in answer_lower) >= 2:
        quality_score += 1
    
    # Check for actionable content
    actionable_terms = ["recommend", "consider", "approach", "best practice", "guidelines", "procedure"]
    if sum(1 for term in actionable_terms if term in answer_lower) >= 2:
        quality_score += 1
    
    # Minimum length check for advanced queries
    if len(answer) < 200:
        quality_score = max(1, quality_score - 2)
    
    return min(5, quality_score)


def _check_advanced_analysis_indicators(answer: str, category: str) -> List[str]:
    """Check for indicators of advanced analysis in the response."""
    
    indicators = []
    answer_lower = answer.lower()
    
    # Scenario analysis indicators
    if any(term in answer_lower for term in ["project examples", "specific projects", "technical details"]):
        indicators.append("Project Examples")
    
    # Problem-solving indicators
    if any(term in answer_lower for term in ["lessons learned", "root cause", "preventive measures"]):
        indicators.append("Lessons Learned")
    
    # Comparative analysis indicators
    if any(term in answer_lower for term in ["comparison", "versus", "alternative", "different methods"]):
        indicators.append("Comparative Analysis")
    
    # Cost/time analysis indicators
    if any(term in answer_lower for term in ["timeline", "cost range", "benchmark", "typical"]):
        indicators.append("Cost/Time Analysis")
    
    # Best practice indicators
    if any(term in answer_lower for term in ["standard approach", "best practice", "proven", "template"]):
        indicators.append("Best Practices")
    
    # Knowledge mapping indicators
    if any(term in answer_lower for term in ["engineer", "expertise", "experience", "specialization"]):
        indicators.append("Knowledge Mapping")
    
    # Regulatory analysis indicators
    if any(term in answer_lower for term in ["council", "consent", "precedent", "approval"]):
        indicators.append("Regulatory Analysis")
    
    return indicators


async def main():
    """Run advanced engineering scenario tests."""
    await test_advanced_engineering_scenarios()


if __name__ == "__main__":
    asyncio.run(main())
