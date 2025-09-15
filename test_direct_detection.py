#!/usr/bin/env python3
"""
Direct test of intent classification and prompt building
"""
import sys
import os
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

from dtce_ai_bot.services.prompt_builder import PromptBuilder

def test_direct_question_detection():
    """Test if the prompt builder detects direct questions correctly"""
    
    prompt_builder = PromptBuilder()
    
    test_questions = [
        "Who is the contact for project 224?",
        "Who is the contact for project 225001?", 
        "What is project 224050?",
        "Contact for project 123?"
    ]
    
    print("Testing Direct Question Detection in Prompt Builder")
    print("=" * 60)
    
    for question in test_questions:
        print(f"\nTesting: '{question}'")
        print("-" * 40)
        
        # Test user override detection
        overrides = prompt_builder._detect_user_instruction_overrides(question)
        print(f"Detected overrides: {overrides}")
        
        # Test if direct answer required is detected
        if overrides.get('direct_answer_required', False):
            print("✅ DIRECT ANSWER REQUIRED detected")
        else:
            print("❌ Direct answer NOT detected")
        
        # Test client_info instructions
        client_instructions = prompt_builder._get_client_info_instructions()
        print(f"Client info instructions length: {len(client_instructions)} chars")
        
        # Test the full system prompt
        system_prompt = prompt_builder.build_simple_system_prompt('client_info', question)
        
        if 'DIRECT ANSWER MODE' in system_prompt:
            print("✅ Direct Answer Mode activated")
        elif 'direct_answer_required' in system_prompt.lower():
            print("⚠️ Direct answer mentioned but mode not activated")
        else:
            print("❌ NO direct answer mode detected")
            
        print(f"System prompt length: {len(system_prompt)} chars")
        print(f"Contains 'FORBIDDEN': {'FORBIDDEN' in system_prompt}")
        print(f"Contains 'methodology': {'methodology' in system_prompt}")

if __name__ == "__main__":
    test_direct_question_detection()
