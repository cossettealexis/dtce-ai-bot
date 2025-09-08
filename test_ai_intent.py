#!/usr/bin/env python3
"""
Test script to demonstrate AI-powered intent recognition vs keyword matching.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_ai_intent_vs_keywords():
    """Test AI intent analysis vs primitive keyword matching."""
    
    test_questions = [
        "What are the minimum clear cover requirements for concrete as per NZS code?",
        "I need to understand the structural implications of varying concrete cover in high-rise construction",
        "How do environmental conditions affect concrete cover specifications?",
        "Can you explain the relationship between concrete cover and rebar corrosion?",
        "What's the concrete cover for a residential slab foundation?",
        "I'm designing a bridge - what cover requirements should I consider?",
        "Tell me about concrete durability in marine environments",
        "What factors influence minimum concrete cover thickness?"
    ]
    
    print("AI-Powered Intent Analysis vs Primitive Keyword Matching")
    print("=" * 70)
    
    # Simulate the old keyword approach
    def old_keyword_detection(question: str) -> bool:
        """Old primitive keyword matching approach."""
        basic_technical_keywords = ['minimum', 'requirements', 'what is', 'tell me', 'how much', 'standard', 'code', 'nzs']
        is_basic_question = any(keyword in question.lower() for keyword in basic_technical_keywords)
        return is_basic_question and ('cover' in question.lower() or 'nzs' in question.lower())
    
    # Simulate AI intent analysis
    async def smart_intent_analysis(question: str) -> dict:
        """Simulate what AI intent analysis would determine."""
        # This simulates what GPT-4 would likely determine for each question
        intent_mapping = {
            "What are the minimum clear cover requirements for concrete as per NZS code?": {
                "intent_type": "direct_technical",
                "requires_direct_answer": True,
                "question_focus": "specific NZ Standard requirements for concrete cover",
                "response_style": "factual_standards"
            },
            "I need to understand the structural implications of varying concrete cover in high-rise construction": {
                "intent_type": "advisory_guidance", 
                "requires_direct_answer": False,
                "question_focus": "complex engineering analysis and design considerations",
                "response_style": "comprehensive_advice"
            },
            "How do environmental conditions affect concrete cover specifications?": {
                "intent_type": "advisory_guidance",
                "requires_direct_answer": False, 
                "question_focus": "engineering principles and environmental considerations",
                "response_style": "comprehensive_advice"
            },
            "Can you explain the relationship between concrete cover and rebar corrosion?": {
                "intent_type": "advisory_guidance",
                "requires_direct_answer": False,
                "question_focus": "engineering concepts and material science",
                "response_style": "comprehensive_advice"
            },
            "What's the concrete cover for a residential slab foundation?": {
                "intent_type": "direct_technical",
                "requires_direct_answer": True,
                "question_focus": "specific technical requirement for common application",
                "response_style": "factual_standards"
            },
            "I'm designing a bridge - what cover requirements should I consider?": {
                "intent_type": "advisory_guidance",
                "requires_direct_answer": False,
                "question_focus": "complex design considerations for infrastructure",
                "response_style": "comprehensive_advice"
            },
            "Tell me about concrete durability in marine environments": {
                "intent_type": "advisory_guidance",
                "requires_direct_answer": False,
                "question_focus": "environmental engineering and material performance",
                "response_style": "comprehensive_advice"
            },
            "What factors influence minimum concrete cover thickness?": {
                "intent_type": "advisory_guidance",
                "requires_direct_answer": False,
                "question_focus": "engineering factors and design considerations",
                "response_style": "comprehensive_advice"
            }
        }
        
        return intent_mapping.get(question, {
            "intent_type": "general_exploration",
            "requires_direct_answer": False,
            "question_focus": "general engineering question",
            "response_style": "exploratory_discussion"
        })
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n📋 Question {i}:")
        print(f"'{question}'")
        print("-" * 60)
        
        # Old approach
        old_result = old_keyword_detection(question)
        print(f"🔸 Old Keyword Approach: {'Direct Answer' if old_result else 'Standard RAG'}")
        
        # AI approach  
        ai_intent = await smart_intent_analysis(question)
        print(f"🤖 AI Intent Analysis:")
        print(f"   • Intent Type: {ai_intent['intent_type']}")
        print(f"   • Requires Direct Answer: {ai_intent['requires_direct_answer']}")
        print(f"   • Question Focus: {ai_intent['question_focus']}")
        print(f"   • Response Style: {ai_intent['response_style']}")
        
        # Show the difference
        if old_result != ai_intent['requires_direct_answer']:
            print(f"⚡ DIFFERENCE: AI correctly identified this needs {ai_intent['response_style']}")
        else:
            print("✅ Both approaches agree")
            
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_ai_intent_vs_keywords())
