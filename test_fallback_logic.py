#!/usr/bin/env python3
"""
Test the complete fallback mechanism locally
"""
import sys
import os
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

def test_fallback_logic():
    """Test the fallback logic for intent classification"""
    
    # Simulate failed intent classification
    failed_intent = {
        'category': 'general',
        'confidence': 0.5,
        'reasoning': 'Classification failed, defaulting to general',
        'search_keywords': ['Who', 'is', 'the']
    }
    
    test_questions = [
        "Who is the contact for project 224?",
        "Who is the contact for project 225001?",
        "What is project 224050?",
        "Contact for project 123?"
    ]
    
    print("Testing Fallback Logic for Failed Intent Classification")
    print("=" * 65)
    
    for question in test_questions:
        print(f"\nTesting: '{question}'")
        print(f"Original classification: {failed_intent['category']} (confidence: {failed_intent['confidence']})")
        print("-" * 50)
        
        # Simulate the fallback logic
        category = failed_intent['category']
        confidence = failed_intent.get('confidence', 0)
        
        if category == 'general' and confidence < 0.7:
            question_lower = question.lower()
            if any(pattern in question_lower for pattern in [
                "who is the contact", "contact for project", "who is contact", 
                "contact for", "who works with"
            ]):
                print("✅ FALLBACK TRIGGERED: Detected client_info question")
                corrected_category = 'client_info'
            elif any(pattern in question_lower for pattern in [
                "what is project", "what is the project", "project number"
            ]):
                print("✅ FALLBACK TRIGGERED: Detected project_search question")
                corrected_category = 'project_search'
            else:
                print("❌ No fallback pattern matched")
                corrected_category = category
        else:
            print("❌ Fallback not triggered (category not general or confidence too high)")
            corrected_category = category
            
        print(f"Final category: {corrected_category}")
        
        # Test prompt builder with corrected category
        from dtce_ai_bot.services.prompt_builder import PromptBuilder
        prompt_builder = PromptBuilder()
        
        system_prompt = prompt_builder.build_simple_system_prompt(corrected_category, question)
        
        if 'DIRECT ANSWER MODE' in system_prompt:
            print("✅ Direct Answer Mode activated")
        elif 'FORBIDDEN' in system_prompt:
            print("✅ Direct answer instructions present")
        else:
            print("❌ Generic response mode (BAD)")

if __name__ == "__main__":
    test_fallback_logic()
