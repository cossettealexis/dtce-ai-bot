#!/usr/bin/env python3
"""
Comprehensive test script for Azure deployment
Tests all RAG.TXT questions plus conversational inputs and other engineering questions
"""

import asyncio
import httpx
import json
import time
from typing import List, Dict, Any

# Azure API endpoint
AZURE_API_BASE = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"

async def test_question(client: httpx.AsyncClient, question: str, test_type: str = "unknown") -> Dict[str, Any]:
    """Test a single question against the Azure API"""
    try:
        start_time = time.time()
        
        response = await client.post(
            f"{AZURE_API_BASE}/documents/ask",
            params={"question": question},
            timeout=60.0
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        if response.status_code == 200:
            result = response.json()
            return {
                "question": question,
                "test_type": test_type,
                "status": "SUCCESS",
                "response_time": response_time,
                "answer_length": len(result.get("response", "")),
                "sources_count": len(result.get("sources", [])),
                "documents_searched": result.get("documents_searched", 0),
                "search_type": result.get("search_type", "unknown"),
                "confidence": result.get("confidence", "unknown"),
                "answer_preview": result.get("response", "")[:150] + "..." if len(result.get("response", "")) > 150 else result.get("response", "")
            }
        else:
            return {
                "question": question,
                "test_type": test_type,
                "status": "ERROR",
                "error": f"HTTP {response.status_code}: {response.text}",
                "response_time": response_time
            }
    
    except Exception as e:
        return {
            "question": question,
            "test_type": test_type,
            "status": "EXCEPTION",
            "error": str(e),
            "response_time": 0
        }

async def run_comprehensive_tests():
    """Run comprehensive tests on Azure deployment"""
    
    print("🚀 Starting comprehensive Azure deployment tests...")
    print(f"🌐 Testing endpoint: {AZURE_API_BASE}")
    
    # RAG.TXT Questions - exact ones from specification
    rag_questions = [
        # NZ Standards and Code Questions
        "Please tell me the minimum clear cover requirements as per NZS code in designing a concrete element.",
        "Tell me what particular clause talks about the detailing requirements in designing a beam.",
        "Tell me the strength reduction factors used when I'm designing a beam or when considering seismic actions.",
        "Tell me what particular NZS structural code to refer to if I'm designing a composite slab to make it a floor diaphragm?",
        
        # Past Projects Reference Questions
        "I am designing a precast panel, please tell me all past projects that have a scope about the following keywords or description: Precast Panel Precast Precast Connection Unispans",
        "I am designing a timber retaining wall, it's going to be 3m tall; can you provide me example past projects and help me draft a design philosophy?",
        "Please advise me on what DTCE has done in the past for a 2-storey concrete precast panel building maybe with a timber-framed structure on top?",
        
        # Product Specification Questions
        "I'm looking for a specific proprietary product that's suitable to provide a waterproofing layer to a concrete block wall that DTCE has used in the past.",
        "I need timber connection details for joining a timber beam to a column. Please provide specifications for the proprietary products DTCE usually refers to, as well as other options to consider.",
        "What are the available sizes of LVL timber on the market? Please list all links containing the sizes and price per length. Also, confirm if the suppliers are located near Wellington.",
        
        # Online References Questions
        "I am currently designing a composite beam but need to make it haunched/tapered. Please provide related references or online threads mentioning the keyword 'tapered composite beam', preferably from anonymous structural engineers.",
        "Please provide design guidelines for a reinforced concrete column to withstand both seismic and gravity actions. If possible, include a legitimate link that gives direct access to the specific design guidelines.",
        
        # Builder/Contact Questions
        "My client is asking about builders that we've worked with before. Can you find any companies and/or contact details that constructed a design for us in the past 3 years and didn't seem to have too many issues during construction? The design job I'm dealing with now is a steel structure retrofit of an old brick building.",
        
        # Template Questions
        "Please provide me with the template we generally use for preparing a PS1. Also, please provide me with the direct link to access it on SuiteFiles.",
        "I wasn't able to find a PS3 template in SuiteFiles. Please provide me with a legitimate link to a general PS3 template that can be submitted to any council in New Zealand.",
        "Please provide me with the link or the file for the timber beam design spreadsheet that DTCE usually uses or has used.",
        
        # Scenario-Based Technical Queries
        "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed.",
        "What foundation systems have we used for houses on steep slopes in Wellington?",
        "Find projects where we designed concrete shear walls for seismic strengthening.",
        "What connection details have we used for balconies on coastal apartment buildings?",
        
        # Problem-Solving & Lessons Learned
        "What issues have we run into when using screw piles in soft soils?",
        "Summarise any lessons learned from projects where retaining walls failed during construction.",
        
        # Additional Scenario Question from RAG.TXT
        "Here's the request for a fee proposal from an architect. Can you find me past DTCE projects that had similar scope to this? It looks like a double cantilever corner window. We're after a proposal for some SED structure required for a residential renovation in Seatoun. Likely scope would be for posts and beams supporting roof above a new sliding door corner unit at first floor level.",
        
        # Additional engineering questions that should work
        "What's the maximum building height allowed in Auckland?",
        "Show me seismic design requirements for Category 2 structures",
        "What fire rating is needed for 2-hour construction?",
        "Find structural calculations for beam design",
        "What are the wind load requirements for Wellington?",
        "Show me foundation design for soft soils",
        "What building consent process applies to commercial buildings?",
        "Find earthquake strengthening requirements",
        "What's the minimum ceiling height for residential buildings?",
        "Show me concrete strength requirements for foundations",
        "What drainage requirements apply to new builds?",
        "Find insulation standards for energy efficiency",
        "What structural steel specifications are required?",
        "Show me accessibility requirements for public buildings?",
        "What geotechnical reports are needed for foundations?",
        "Find fire safety systems for high-rise buildings",
        "What building code applies to industrial structures?",
        "Show me timber framing requirements",
        "What environmental assessments are required?",
        "Find structural peer review requirements",
        "What are the parking requirements for office buildings?",
        "Show me stormwater management for developments",
        "What heritage building restrictions apply?",
        "Find building warranty requirements",
        "What noise control measures are required for construction?",
        "Show me retaining wall design requirements",
        "What are the ventilation requirements for commercial kitchens?",
        "Find structural design for swimming pools",
        "What building inspection schedule is required?",
        "Show me energy efficiency standards for new builds",
        "What are the requirements for disabled access ramps?",
        "Find structural analysis for multi-storey buildings",
        "What building materials are approved for coastal areas?",
        "Show me foundation requirements for clay soils",
        "What fire egress requirements apply to schools?",
        "Find structural design for cantilevered structures",
        "What are the requirements for building on slopes?",
        "Show me structural steel connection details"
    ]
    
    # Conversational inputs (should NOT trigger document search)
    conversational_inputs = [
        "hi",
        "hello", 
        "help",
        "really",
        "really?",
        "ok",
        "thanks",
        "yes",
        "no",
        "wow",
        "cool",
        "es",
        "hmm",
        "ah",
        "nice"
    ]
    
    # General engineering questions (should trigger intelligent search)
    engineering_questions = [
        "How do I calculate beam deflection?",
        "What are the different types of foundations?",
        "Can you explain moment distribution method?",
        "What's the difference between dead load and live load?",
        "How do I design a steel beam for bending?",
        "What are the factors affecting concrete strength?",
        "How do earthquake forces affect building design?",
        "What are the principles of sustainable construction?",
        "How do I calculate wind loads on buildings?",
        "What are the different types of structural joints?",
        "How do I design reinforced concrete columns?",
        "What are the safety factors used in structural design?",
        "How do soil conditions affect foundation design?",
        "What are the requirements for fire resistance in buildings?"
    ]
    
    # Mixed questions (combination of everything)
    mixed_questions = [
        "What projects has DTCE worked on recently?",
        "Do you have templates for structural calculations?",
        "Who are DTCE's main clients?",
        "What software does DTCE use for design?",
        "Can you help me with a specific calculation?",
        "What standards does DTCE follow?",
        "Do you have examples of past projects?"
    ]
    
    all_tests = [
        (rag_questions, "RAG_SPECIFICATION"),
        (conversational_inputs, "CONVERSATIONAL"),
        (engineering_questions, "ENGINEERING_GENERAL"),
        (mixed_questions, "MIXED_QUERIES")
    ]
    
    async with httpx.AsyncClient() as client:
        # Test health endpoint first
        print("\n🏥 Testing health endpoint...")
        try:
            health_response = await client.get(f"{AZURE_API_BASE}/api/health", timeout=30.0)
            if health_response.status_code == 200:
                print("✅ Health check passed")
            else:
                print(f"⚠️  Health check returned {health_response.status_code}")
        except Exception as e:
            print(f"❌ Health check failed: {e}")
        
        total_tests = sum(len(questions) for questions, _ in all_tests)
        current_test = 0
        results = []
        
        # Run all test categories
        for questions, test_type in all_tests:
            print(f"\n📋 Testing {test_type} ({len(questions)} questions)...")
            
            category_results = []
            for question in questions:
                current_test += 1
                print(f"  [{current_test}/{total_tests}] Testing: '{question[:50]}...'")
                
                result = await test_question(client, question, test_type)
                category_results.append(result)
                results.append(result)
                
                # Show result summary
                if result["status"] == "SUCCESS":
                    print(f"    ✅ {result['response_time']:.1f}s | {result['search_type']} | {result['answer_length']} chars")
                else:
                    print(f"    ❌ {result['status']}: {result.get('error', 'Unknown error')}")
                
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.5)
            
            # Category summary
            successful = [r for r in category_results if r["status"] == "SUCCESS"]
            print(f"  📊 {test_type}: {len(successful)}/{len(category_results)} successful ({len(successful)/len(category_results)*100:.1f}%)")
        
        # Overall analysis
        print(f"\n📈 COMPREHENSIVE TEST RESULTS")
        print(f"=" * 50)
        
        total_successful = [r for r in results if r["status"] == "SUCCESS"]
        total_failed = [r for r in results if r["status"] != "SUCCESS"]
        
        print(f"Total Tests: {len(results)}")
        print(f"Successful: {len(total_successful)} ({len(total_successful)/len(results)*100:.1f}%)")
        print(f"Failed: {len(total_failed)} ({len(total_failed)/len(results)*100:.1f}%)")
        
        if total_successful:
            avg_response_time = sum(r["response_time"] for r in total_successful) / len(total_successful)
            print(f"Average Response Time: {avg_response_time:.2f}s")
        
        # Category breakdown
        print(f"\n📊 BREAKDOWN BY CATEGORY:")
        for questions, test_type in all_tests:
            category_results = [r for r in results if r["test_type"] == test_type]
            successful = [r for r in category_results if r["status"] == "SUCCESS"]
            print(f"  {test_type}: {len(successful)}/{len(category_results)} ({len(successful)/len(category_results)*100:.1f}%)")
        
        # Check conversational handling
        conversational_results = [r for r in results if r["test_type"] == "CONVERSATIONAL" and r["status"] == "SUCCESS"]
        no_doc_search = [r for r in conversational_results if r.get("documents_searched", 0) == 0]
        print(f"\n🗣️  CONVERSATIONAL INPUT ANALYSIS:")
        print(f"  Conversational inputs that avoided document search: {len(no_doc_search)}/{len(conversational_results)}")
        
        # Show any failures
        if total_failed:
            print(f"\n❌ FAILED TESTS:")
            for result in total_failed:
                print(f"  '{result['question'][:50]}...' - {result['status']}: {result.get('error', 'Unknown')}")
        
        # Show sample responses
        print(f"\n💬 SAMPLE RESPONSES:")
        sample_categories = ["CONVERSATIONAL", "RAG_SPECIFICATION", "ENGINEERING_GENERAL"]
        for category in sample_categories:
            category_results = [r for r in results if r["test_type"] == category and r["status"] == "SUCCESS"]
            if category_results:
                sample = category_results[0]
                print(f"\n  {category} - '{sample['question']}':")
                print(f"    {sample['answer_preview']}")
        
        print(f"\n🎉 Comprehensive testing complete!")
        
        return results

if __name__ == "__main__":
    results = asyncio.run(run_comprehensive_tests())
