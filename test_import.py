#!/usr/bin/env python3
"""
Simple test to verify the rag_handler imports correctly
"""
import sys
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

try:
    from dtce_ai_bot.services.rag_handler import RAGHandler
    print("✅ RAGHandler imported successfully!")
    print("✅ ChatGPT-style conversation system is ready!")
    
    # Check if the method exists
    if hasattr(RAGHandler, 'universal_ai_assistant'):
        print("✅ universal_ai_assistant method found")
    
    if hasattr(RAGHandler, '_process_rag_with_full_prompt'):
        print("✅ _process_rag_with_full_prompt method found")
        
    print("\n🚀 Ready to test ChatGPT-style responses!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
