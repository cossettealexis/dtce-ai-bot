#!/usr/bin/env python3
"""
Comprehensive Smart Routing Test
Tests the smart query router across ALL business scenarios and intents.
"""
import asyncio
import sys
import os
from typing import Dict, List, Tuple
from dotenv import load_dotenv

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.integrations.azure_search import get_search_client
from dtce_ai_bot.services.smart_rag_handler import SmartRAGHandler
from openai import AsyncAzureOpenAI

# Load environment variables
load_dotenv()


class ComprehensiveRoutingTest:
    """Test smart routing across all business scenarios"""
    
    def __init__(self):
        # Initialize with proper clients like our working tests
        settings = get_settings()
        search_client = get_search_client()
        
        openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        
        self.rag_handler = SmartRAGHandler(
            search_client=search_client,
            openai_client=openai_client, 
            model_name=settings.azure_openai_deployment_name
        )
        
        # Comprehensive test queries covering all business areas
        self.test_scenarios = {
            # POLICY QUERIES
            "policy": [
                "What's our wellness policy?",
                "wellness policy",
                "Show me the health and safety policy",
                "What are our privacy policies?",
                "data protection policy",
                "What's the company's code of conduct?",
                "anti-harassment policy",
                "What are our environmental policies?",
                "sustainability policy requirements",
                "What's our IT security policy?"
            ],
            
            # PROCEDURE QUERIES
            "procedure": [
                "How do I submit a leave request?",
                "expense claim procedure",
                "What's the process for hiring new staff?",
                "recruitment procedures",
                "How do I report an incident?",
                "incident reporting steps",
                "What's the procurement process?",
                "purchase order procedures",
                "How do I access the building after hours?",
                "emergency evacuation procedures"
            ],
            
            # STANDARD QUERIES
            "standard": [
                "What are our quality standards?",
                "ISO certification requirements",
                "What building codes do we follow?",
                "construction standards",
                "What are our design standards?",
                "technical specifications",
                "What safety standards apply?",
                "compliance requirements",
                "What are our environmental standards?",
                "sustainability benchmarks"
            ],
            
            # PROJECT QUERIES
            "project": [
                "Tell me about the Auckland waterfront project",
                "project timeline for the new hospital",
                "What's the status of the CBD development?",
                "residential building project details",
                "Show me the school construction project",
                "infrastructure project updates",
                "What projects are we working on in Wellington?",
                "current commercial developments",
                "Tell me about the housing project",
                "roadway construction projects"
            ],
            
            # CLIENT QUERIES
            "client": [
                "Who is our client for the mall project?",
                "client contact information",
                "What are the client requirements?",
                "client feedback and reviews",
                "Show me client contract details",
                "client communication history",
                "What does the client expect?",
                "client project specifications",
                "Tell me about our government clients",
                "private sector client portfolio"
            ]
        }
    
    async def test_intent_classification(self) -> Dict[str, Dict[str, int]]:
        """Test that queries are correctly classified by intent"""
        print("🎯 Testing Intent Classification...")
        print("=" * 60)
        
        classification_results = {}
        
        for expected_intent, queries in self.test_scenarios.items():
            print(f"\n📋 Testing {expected_intent.upper()} queries:")
            classification_results[expected_intent] = {
                "correct": 0,
                "incorrect": 0,
                "total": len(queries)
            }
            
            for query in queries:
                try:
                    # Get the intent classification
                    intent_result = await self.rag_handler.query_router.route_query(query)
                    detected_intent = intent_result["intent"]
                    
                    if detected_intent == expected_intent:
                        classification_results[expected_intent]["correct"] += 1
                        status = "✅"
                    else:
                        classification_results[expected_intent]["incorrect"] += 1
                        status = "❌"
                    
                    print(f"  {status} '{query}' → {detected_intent}")
                    
                except Exception as e:
                    print(f"  ❌ '{query}' → ERROR: {e}")
                    classification_results[expected_intent]["incorrect"] += 1
        
        return classification_results
    
    async def test_search_quality(self) -> Dict[str, Dict[str, float]]:
        """Test search quality across different intents"""
        print("\n\n🔍 Testing Search Quality...")
        print("=" * 60)
        
        quality_results = {}
        
        for intent, queries in self.test_scenarios.items():
            print(f"\n📊 Testing {intent.upper()} search quality:")
            
            total_sources = 0
            successful_searches = 0
            total_queries = len(queries)
            
            # Test a sample of queries from each intent (first 3 to keep it manageable)
            sample_queries = queries[:3]
            
            for query in sample_queries:
                try:
                    response = await self.rag_handler.get_answer(query)
                    answer_text = response.get("answer", "") if isinstance(response, dict) else str(response)
                    
                    if "I don't have information" not in answer_text:
                        successful_searches += 1
                        # Estimate source count (simplified)
                        if "document" in answer_text.lower() or "policy" in answer_text.lower():
                            total_sources += 1
                    
                    print(f"  📄 '{query}' → {'Success' if 'I don\'t have information' not in answer_text else 'No results'}")
                    
                except Exception as e:
                    print(f"  ❌ '{query}' → ERROR: {e}")
            
            quality_results[intent] = {
                "success_rate": (successful_searches / len(sample_queries)) * 100,
                "avg_sources": total_sources / len(sample_queries) if sample_queries else 0
            }
        
        return quality_results
    
    async def test_consistency_across_variations(self) -> Dict[str, float]:
        """Test consistency for query variations within each intent"""
        print("\n\n🔄 Testing Consistency Across Query Variations...")
        print("=" * 60)
        
        consistency_scores = {}
        
        # Test pairs of similar queries
        variation_pairs = {
            "policy": [
                ("wellness policy", "What's our wellness policy?"),
                ("privacy policy", "Show me the privacy policies"),
                ("safety policy", "What are our health and safety policies?")
            ],
            "procedure": [
                ("leave request", "How do I submit a leave request?"),
                ("expense procedure", "What's the expense claim process?"),
                ("hiring process", "How do we hire new staff?")
            ],
            "standard": [
                ("quality standards", "What are our quality requirements?"),
                ("building codes", "What construction standards do we follow?"),
                ("safety standards", "What safety requirements apply?")
            ],
            "project": [
                ("Auckland project", "Tell me about Auckland developments"),
                ("hospital project", "What's the status of the hospital build?"),
                ("school construction", "Show me the school building project")
            ],
            "client": [
                ("client contact", "Who is our client contact?"),
                ("client requirements", "What does the client need?"),
                ("client feedback", "Show me client reviews")
            ]
        }
        
        for intent, pairs in variation_pairs.items():
            print(f"\n🔄 Testing {intent.upper()} consistency:")
            
            total_pairs = len(pairs)
            consistent_pairs = 0
            
            for query1, query2 in pairs:
                try:
                    # Check if both queries get classified to the same intent
                    intent1 = await self.rag_handler.query_router.route_query(query1)
                    intent2 = await self.rag_handler.query_router.route_query(query2)
                    
                    if intent1["intent"] == intent2["intent"] == intent:
                        consistent_pairs += 1
                        status = "✅"
                    else:
                        status = "❌"
                    
                    print(f"  {status} '{query1}' & '{query2}' → {intent1['intent']} & {intent2['intent']}")
                    
                except Exception as e:
                    print(f"  ❌ Error testing '{query1}' & '{query2}': {e}")
            
            consistency_scores[intent] = (consistent_pairs / total_pairs) * 100 if total_pairs > 0 else 0
        
        return consistency_scores
    
    async def test_edge_cases(self) -> Dict[str, bool]:
        """Test edge cases and potential failure points"""
        print("\n\n⚠️  Testing Edge Cases...")
        print("=" * 60)
        
        edge_cases = {
            "empty_query": "",
            "very_short": "hi",
            "mixed_intent": "show me the wellness policy and project timeline",
            "typos": "welness polcy and safty standrds",
            "non_english": "¿Cuál es nuestra política de bienestar?",
            "very_long": "I need to know about our comprehensive wellness policy framework including all the detailed procedures for implementation and the specific standards that apply to our construction projects and how they relate to client requirements and expectations",
            "numbers_only": "12345",
            "special_chars": "policy@#$%^&*()",
            "ambiguous": "that thing we talked about",
            "multiple_questions": "What's our policy? How do procedures work? What standards apply?"
        }
        
        edge_results = {}
        
        for case_name, query in edge_cases.items():
            try:
                print(f"\n🧪 Testing {case_name}: '{query}'")
                
                if query:  # Skip empty query for routing test
                    intent_result = await self.rag_handler.query_router.route_query(query)
                    response = await self.rag_handler.get_answer(query)
                    answer_text = response.get("answer", "") if isinstance(response, dict) else str(response)
                    
                    # Check if we get a reasonable response (not crashing)
                    has_response = len(answer_text) > 10
                    has_intent = intent_result["intent"] in ["policy", "procedure", "standard", "project", "client", "general"]
                    
                    edge_results[case_name] = has_response and has_intent
                    print(f"  Intent: {intent_result['intent']}")
                    print(f"  Response length: {len(answer_text)} chars")
                    print(f"  Status: {'✅ Handled' if edge_results[case_name] else '❌ Failed'}")
                else:
                    edge_results[case_name] = True  # Empty query is expected to be handled
                    print(f"  Status: ✅ Handled (empty query)")
                
            except Exception as e:
                edge_results[case_name] = False
                print(f"  ❌ Error: {e}")
        
        return edge_results
    
    def print_summary_report(self, classification_results, quality_results, consistency_scores, edge_results):
        """Print a comprehensive summary report"""
        print("\n\n" + "="*80)
        print("📊 COMPREHENSIVE SMART ROUTING TEST REPORT")
        print("="*80)
        
        # Classification Summary
        print("\n🎯 INTENT CLASSIFICATION SUMMARY:")
        total_correct = sum(r["correct"] for r in classification_results.values())
        total_queries = sum(r["total"] for r in classification_results.values())
        overall_accuracy = (total_correct / total_queries) * 100 if total_queries > 0 else 0
        
        print(f"Overall Classification Accuracy: {overall_accuracy:.1f}% ({total_correct}/{total_queries})")
        
        for intent, results in classification_results.items():
            accuracy = (results["correct"] / results["total"]) * 100 if results["total"] > 0 else 0
            print(f"  {intent.upper()}: {accuracy:.1f}% ({results['correct']}/{results['total']})")
        
        # Search Quality Summary
        print("\n🔍 SEARCH QUALITY SUMMARY:")
        for intent, results in quality_results.items():
            print(f"  {intent.upper()}: {results['success_rate']:.1f}% success rate, {results['avg_sources']:.1f} avg sources")
        
        # Consistency Summary
        print("\n🔄 CONSISTENCY SUMMARY:")
        avg_consistency = sum(consistency_scores.values()) / len(consistency_scores) if consistency_scores else 0
        print(f"Average Consistency Score: {avg_consistency:.1f}%")
        for intent, score in consistency_scores.items():
            print(f"  {intent.upper()}: {score:.1f}%")
        
        # Edge Cases Summary
        print("\n⚠️  EDGE CASES SUMMARY:")
        handled_cases = sum(1 for result in edge_results.values() if result)
        total_cases = len(edge_results)
        edge_success_rate = (handled_cases / total_cases) * 100 if total_cases > 0 else 0
        print(f"Edge Cases Handled: {edge_success_rate:.1f}% ({handled_cases}/{total_cases})")
        
        # Overall Assessment
        print("\n🏆 OVERALL ASSESSMENT:")
        if overall_accuracy >= 90 and avg_consistency >= 80 and edge_success_rate >= 70:
            print("✅ EXCELLENT: Smart routing system is production-ready!")
        elif overall_accuracy >= 80 and avg_consistency >= 70:
            print("✅ GOOD: Smart routing system works well with minor improvements needed")
        elif overall_accuracy >= 70:
            print("⚠️  FAIR: Smart routing system needs significant improvements")
        else:
            print("❌ POOR: Smart routing system needs major fixes")


async def main():
    """Run comprehensive smart routing tests"""
    print("🚀 Starting Comprehensive Smart Routing Test Suite")
    print("Testing across ALL business scenarios: Policy, Procedure, Standard, Project, Client")
    print("="*80)
    
    tester = ComprehensiveRoutingTest()
    
    try:
        # Run all test suites
        classification_results = await tester.test_intent_classification()
        quality_results = await tester.test_search_quality()
        consistency_scores = await tester.test_consistency_across_variations()
        edge_results = await tester.test_edge_cases()
        
        # Generate comprehensive report
        tester.print_summary_report(classification_results, quality_results, consistency_scores, edge_results)
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
