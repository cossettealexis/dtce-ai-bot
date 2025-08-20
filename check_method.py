#!/usr/bin/env python3
"""
Simple test to check for the missing _generate_answer_from_documents method
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

try:
    # Import the DocumentQAService
    from dtce_ai_bot.services.document_qa import DocumentQAService
    
    # Check if the method exists
    qa_service = DocumentQAService()
    
    if hasattr(qa_service, '_generate_answer_from_documents'):
        print("✅ _generate_answer_from_documents method exists")
    else:
        print("❌ _generate_answer_from_documents method is MISSING")
        
        # List all methods that contain 'generate' and 'answer'
        methods = [method for method in dir(qa_service) if 'generate' in method and 'answer' in method]
        print(f"Available generate answer methods: {methods}")
        
except Exception as e:
    print(f"❌ Error importing or checking: {e}")
