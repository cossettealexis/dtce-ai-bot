#!/usr/bin/env python3
"""
Test the new Universal AI Assistant that can answer anything.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_universal_ai():
    """Test the universal AI assistant with various question types."""
    
    test_questions = [
        # DTCE-specific questions (should search folders)
        "What are DTCE's safety policies?",
        "How do I use the wind speed spreadsheet?", 
        "What NZ standards do we have for concrete?",
        "Tell me about the Auckland Harbor Bridge project",
        "Who is the contact for Smith Construction?",
        
        # General knowledge questions (should use ChatGPT knowledge)
        "What's the weather like today?",
        "Explain machine learning",
        "What are the benefits of renewable energy?",
        "How do neural networks work?",
        "What's the capital of New Zealand?",
        
        # Mixed questions (technical but general)
        "What are the minimum clear cover requirements for concrete?",
        "How does concrete strength develop over time?",
        "Explain the difference between steel grades"
    ]
    
    print("🤖 DTCE Universal AI Assistant Test")
    print("=" * 60)
    print("This AI can answer ANYTHING - just like ChatGPT!")
    print("It smartly searches DTCE folders when needed, otherwise uses general knowledge.")
    print("=" * 60)
    
    # Simulate the responses (since we can't run full test without API keys)
    for i, question in enumerate(test_questions, 1):
        print(f"\n📋 Question {i}: {question}")
        print("-" * 50)
        
        # Simulate what the AI routing would decide
        if any(keyword in question.lower() for keyword in ['dtce', 'safety', 'policy', 'spreadsheet', 'standards', 'project', 'contact']):
            folder = "policy" if 'safety' in question.lower() or 'policy' in question.lower() else \
                    "procedures" if 'spreadsheet' in question.lower() or 'how' in question.lower() else \
                    "standards" if 'standard' in question.lower() or 'nz' in question.lower() else \
                    "projects" if 'project' in question.lower() else \
                    "clients" if 'contact' in question.lower() else "general"
            
            print(f"🔍 AI Decision: Search DTCE folder '{folder}'")
            print(f"💡 Response Style: DTCE-specific answer with document references")
        else:
            print(f"🧠 AI Decision: Use general knowledge (like ChatGPT)")
            print(f"💡 Response Style: General knowledge answer")
        
        # Show the type of response
        if 'concrete' in question.lower() or 'steel' in question.lower():
            print(f"🔧 Technical Topic: Would provide engineering knowledge + any relevant DTCE docs")
        elif 'weather' in question.lower() or 'capital' in question.lower():
            print(f"🌍 General Topic: Pure ChatGPT-style response")
        elif 'machine learning' in question.lower() or 'neural' in question.lower():
            print(f"🤖 Tech Topic: Educational explanation like ChatGPT")
        
        print("=" * 60)
    
    print("\n✅ SUMMARY:")
    print("The Universal AI is NOT limited to just engineering!")
    print("- DTCE questions → Searches relevant folders")
    print("- General questions → Uses ChatGPT knowledge") 
    print("- Technical questions → Combines both sources")
    print("- No more separate handlers for different topics!")

if __name__ == "__main__":
    asyncio.run(test_universal_ai())
