#!/usr/bin/env python3
"""
Comprehensive Test Suite for DTCE AI Bot Enhanced RAG System
Tests all scenarios provided in the requirements
"""

import asyncio
import json
import time
from typing import List, Dict, Any
import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DTCEBotTester:
    """Comprehensive tester for DTCE AI Bot functionality"""
    
    def __init__(self, base_url: str = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"):
        self.base_url = base_url
        self.api_endpoint = f"{base_url}/api/messages"
        self.test_results = []
        
    async def send_message(self, text: str, conversation_id: str = None) -> Dict[str, Any]:
        """Send message to bot and get response"""
        
        payload = {
            "type": "message",
            "text": text,
            "from": {
                "id": "test-user",
                "name": "Test User"
            },
            "recipient": {
                "id": "dtce-bot"
            },
            "conversation": {
                "id": conversation_id or f"test-{int(time.time())}"
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "response": response.json(),
                        "status_code": response.status_code
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": None
            }
    
    async def run_test_scenario(self, category: str, test_cases: List[Dict[str, str]]) -> Dict[str, Any]:
        """Run a category of test cases"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"TESTING CATEGORY: {category.upper()}")
        logger.info(f"{'='*60}")
        
        category_results = {
            "category": category,
            "total_tests": len(test_cases),
            "successful_tests": 0,
            "failed_tests": 0,
            "test_results": []
        }
        
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"\nTest {i}/{len(test_cases)}: {test_case['description']}")
            logger.info(f"Query: '{test_case['query']}'")
            
            start_time = time.time()
            result = await self.send_message(test_case['query'])
            end_time = time.time()
            
            test_result = {
                "test_number": i,
                "description": test_case['description'],
                "query": test_case['query'],
                "expected_behavior": test_case.get('expected', 'Should provide relevant response'),
                "response_time": round(end_time - start_time, 2),
                "success": result['success'],
                "response": result.get('response', {}),
                "error": result.get('error')
            }
            
            if result['success']:
                category_results["successful_tests"] += 1
                logger.info(f"✅ SUCCESS (Time: {test_result['response_time']}s)")
                
                # Log response details
                bot_response = result['response']
                if 'activities' in bot_response and bot_response['activities']:
                    activity = bot_response['activities'][0]
                    response_text = activity.get('text', 'No text response')
                    logger.info(f"Response: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")
                
            else:
                category_results["failed_tests"] += 1
                logger.error(f"❌ FAILED: {result['error']}")
            
            category_results["test_results"].append(test_result)
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        # Category summary
        success_rate = (category_results["successful_tests"] / category_results["total_tests"]) * 100
        logger.info(f"\n{category.upper()} SUMMARY:")
        logger.info(f"Success Rate: {success_rate:.1f}% ({category_results['successful_tests']}/{category_results['total_tests']})")
        
        return category_results
    
    async def run_comprehensive_tests(self):
        """Run all test scenarios"""
        
        logger.info("Starting Comprehensive DTCE AI Bot Test Suite")
        logger.info("Testing Enhanced RAG Pipeline Implementation")
        
        # Test Categories
        test_categories = {
            "basic_policies": [
                {
                    "description": "Wellness Policy Query",
                    "query": "What is our wellness policy?",
                    "expected": "Should return specific wellness policy information"
                },
                {
                    "description": "Wellness Policy Detailed",
                    "query": "What's our wellness policy and what does it say?",
                    "expected": "Should provide detailed wellness policy content"
                },
                {
                    "description": "Wellness Policy Short",
                    "query": "wellness policy",
                    "expected": "Should understand short query and return policy info"
                },
                {
                    "description": "Wellbeing Policy",
                    "query": "wellbeing policy", 
                    "expected": "Should map wellbeing to wellness policy"
                }
            ],
            
            "client_contact_queries": [
                {
                    "description": "Aaron from TGCS Contact",
                    "query": "Does anyone work with Aaron from TGCS?",
                    "expected": "Should provide contact information if available"
                },
                {
                    "description": "General Client Contact",
                    "query": "Who is the contact for project 224?",
                    "expected": "Should provide project contact information"
                }
            ],
            
            "project_queries": [
                {
                    "description": "Project 225 Query",
                    "query": "What is project 225",
                    "expected": "Should provide project details and documentation"
                },
                {
                    "description": "Client Satisfaction Query",
                    "query": "Can you give me sample projects where client don't like",
                    "expected": "Should identify problematic client relationships"
                }
            ],
            
            "superseded_folders": [
                {
                    "description": "Project 221 with Superseded",
                    "query": "WHAT IS project 221 INCLUDE SUPERSEDED FOLDERS?",
                    "expected": "Should include older/overwritten versions"
                },
                {
                    "description": "Draft vs Final Comparison",
                    "query": "I want to see what changed between the draft and the final issued specs for project 223.",
                    "expected": "Should compare different versions"
                },
                {
                    "description": "Older Calculation Versions",
                    "query": "Were there any older versions of the calculations issued before revision B?",
                    "expected": "Should find version history"
                },
                {
                    "description": "Superseded Calculations",
                    "query": "Include the superseded drawing files from 06_Calculations for project 220.",
                    "expected": "Should include superseded calculation files"
                }
            ],
            
            "engineering_advice": [
                {
                    "description": "Project 224 Design Considerations",
                    "query": "What were the main design considerations mentioned in the final report for project 224?",
                    "expected": "Should summarize technical insights"
                },
                {
                    "description": "Bridge Foundations 2023",
                    "query": "Summarize what kind of foundations were used across bridge projects completed in 2023.",
                    "expected": "Should analyze patterns across projects"
                },
                {
                    "description": "Wind Loading Approach",
                    "query": "What is the typical approach used for wind loading in these calculations?",
                    "expected": "Should provide technical methodology"
                },
                {
                    "description": "Timber Bridge Standards",
                    "query": "Can you advise what standard detail we usually use for timber bridges based on past projects?",
                    "expected": "Should recommend based on historical data"
                }
            ],
            
            "nz_standards": [
                {
                    "description": "Concrete Cover Requirements",
                    "query": "Please tell me that minimum clear cover requirements as per NZS code in designing a concrete element",
                    "expected": "Should cite specific NZS clauses"
                },
                {
                    "description": "Beam Detailing Requirements",
                    "query": "Tell me what particular clause that talks about the detailing requirements in designing a beam",
                    "expected": "Should reference specific standard sections"
                },
                {
                    "description": "Strength Reduction Factors",
                    "query": "Tell me the strength reduction factors used when I'm designing a beam or when considering seismic actions.",
                    "expected": "Should provide specific factors from standards"
                },
                {
                    "description": "Composite Slab Standards",
                    "query": "Tell me what particular NZS structural code to refer with if I'm designing a composite slab to make it as floor diaphragm?",
                    "expected": "Should identify relevant NZS codes"
                }
            ],
            
            "technical_procedures": [
                {
                    "description": "Precast Panel Design",
                    "query": "I am designing a precast panel, please tell me all past project that has a scope about the following keywords: Precast Panel, Precast Connection, Unispans",
                    "expected": "Should find projects with precast elements"
                },
                {
                    "description": "Timber Retaining Wall",
                    "query": "I am designing a timber retaining wall it's going to be 3m tall; can you provide me example past projects and help me draft a design philosophy?",
                    "expected": "Should provide examples and methodology"
                },
                {
                    "description": "Precast Building Design",
                    "query": "Please advise me on what DTCE has done in the past for a 2 storey concrete precast panel building maybe with a timber framed structure on top?",
                    "expected": "Should provide hybrid construction examples"
                }
            ],
            
            "scenario_based": [
                {
                    "description": "Mid-rise Timber High Wind",
                    "query": "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed.",
                    "expected": "Should find relevant project examples"
                },
                {
                    "description": "Steep Slope Foundations",
                    "query": "What foundation systems have we used for houses on steep slopes in Wellington?",
                    "expected": "Should provide foundation solutions"
                },
                {
                    "description": "Seismic Strengthening",
                    "query": "Find projects where we designed concrete shear walls for seismic strengthening.",
                    "expected": "Should identify strengthening projects"
                }
            ]
        }
        
        all_results = []
        total_tests = sum(len(tests) for tests in test_categories.values())
        
        logger.info(f"Running {total_tests} tests across {len(test_categories)} categories")
        
        for category, test_cases in test_categories.items():
            category_result = await self.run_test_scenario(category, test_cases)
            all_results.append(category_result)
        
        # Overall summary
        total_successful = sum(result["successful_tests"] for result in all_results)
        total_failed = sum(result["failed_tests"] for result in all_results)
        overall_success_rate = (total_successful / total_tests) * 100
        
        logger.info(f"\n{'='*80}")
        logger.info(f"COMPREHENSIVE TEST RESULTS SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Successful: {total_successful}")
        logger.info(f"Failed: {total_failed}")
        logger.info(f"Overall Success Rate: {overall_success_rate:.1f}%")
        logger.info(f"{'='*80}")
        
        # Category breakdown
        for result in all_results:
            success_rate = (result["successful_tests"] / result["total_tests"]) * 100
            logger.info(f"{result['category']:.<25} {success_rate:>6.1f}% ({result['successful_tests']}/{result['total_tests']})")
        
        # Save detailed results
        timestamp = int(time.time())
        results_file = f"test_results_{timestamp}.json"
        
        final_report = {
            "timestamp": timestamp,
            "total_tests": total_tests,
            "successful_tests": total_successful,
            "failed_tests": total_failed,
            "success_rate": overall_success_rate,
            "category_results": all_results
        }
        
        with open(results_file, 'w') as f:
            json.dump(final_report, f, indent=2)
        
        logger.info(f"Detailed results saved to: {results_file}")
        
        return final_report

async def main():
    """Main test execution"""
    tester = DTCEBotTester()
    
    # First check if bot is available
    logger.info("Checking bot availability...")
    test_response = await tester.send_message("Hello, are you working?")
    
    if not test_response['success']:
        logger.error("Bot is not available. Cannot run tests.")
        logger.error(f"Error: {test_response['error']}")
        return
    
    logger.info("✅ Bot is available. Starting comprehensive tests...")
    
    # Run all tests
    results = await tester.run_comprehensive_tests()
    
    # Recommendations based on results
    if results['success_rate'] >= 90:
        logger.info("🎉 EXCELLENT: Enhanced RAG system is working very well!")
    elif results['success_rate'] >= 75:
        logger.info("✅ GOOD: Enhanced RAG system is working well with minor issues")
    elif results['success_rate'] >= 50:
        logger.info("⚠️  MODERATE: Enhanced RAG system needs improvements")
    else:
        logger.error("❌ POOR: Enhanced RAG system needs significant work")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())
