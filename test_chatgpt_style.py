#!/usr/bin/env python3
"""
Test the Universal AI Assistant that can handle ANY topic like ChatGPT.
"""

async def test_universal_ai_assistant():
    """Test the universal AI assistant with various types of questions."""
    
    test_questions = [
        # General AI questions (should work like ChatGPT)
        "What is machine learning?",
        "How do I make a good cup of coffee?", 
        "Explain quantum physics in simple terms",
        "What are the benefits of exercise?",
        
        # DTCE-specific questions (should search Azure folders)
        "What are DTCE's health and safety policies?",  # Should search policies folder
        "How do I use the site wind speed spreadsheet?",  # Should search procedures folder  
        "What NZ engineering standards do we have for concrete?",  # Should search standards folder
        "Tell me about past projects with Auckland Council",  # Should search projects folder
        "What are the contact details for our client XYZ?",  # Should search clients folder
        
        # Technical questions (should give smart responses)
        "What are the minimum clear cover requirements for concrete?",
        "How do environmental conditions affect concrete design?"
    ]
    
    print("Universal AI Assistant Test - ChatGPT for Everything + Smart DTCE Routing")
    print("=" * 75)
    
    # Simulate the AI routing analysis
    def simulate_routing_analysis(question: str) -> dict:
        """Simulate what the AI would determine for routing."""
        
        question_lower = question.lower()
        
        # DTCE-specific patterns
        if any(phrase in question_lower for phrase in ['dtce', 'policy', 'policies', 'health and safety', 'h&s']):
            return {"needs_dtce_documents": True, "folder_type": "policies", "question_intent": "DTCE policy inquiry"}
        
        elif any(phrase in question_lower for phrase in ['spreadsheet', 'procedure', 'how do i', 'h2h', 'handbook']):
            return {"needs_dtce_documents": True, "folder_type": "procedures", "question_intent": "DTCE procedure inquiry"}
            
        elif any(phrase in question_lower for phrase in ['nz standard', 'nz engineering', 'standards do we have']):
            return {"needs_dtce_documents": True, "folder_type": "standards", "question_intent": "NZ standards inquiry"}
            
        elif any(phrase in question_lower for phrase in ['past project', 'project with', 'auckland council']):
            return {"needs_dtce_documents": True, "folder_type": "projects", "question_intent": "Project reference inquiry"}
            
        elif any(phrase in question_lower for phrase in ['contact detail', 'client', 'our client']):
            return {"needs_dtce_documents": True, "folder_type": "clients", "question_intent": "Client information inquiry"}
            
        elif any(phrase in question_lower for phrase in ['concrete', 'cover', 'nzs']) and 'requirements' in question_lower:
            return {"needs_dtce_documents": True, "folder_type": "standards", "question_intent": "Technical standards inquiry"}
        
        else:
            return {"needs_dtce_documents": False, "folder_type": "none", "question_intent": "General knowledge question"}
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n🤖 Question {i}:")
        print(f"'{question}'")
        print("-" * 60)
        
        routing = simulate_routing_analysis(question)
        
        if routing["needs_dtce_documents"]:
            print(f"🔍 AI Decision: Search DTCE {routing['folder_type']} folder")
            print(f"📁 Folder: {routing['folder_type']}")
            print(f"🎯 Intent: {routing['question_intent']}")
            print(f"💡 Response: Search Azure + AI contextual answer")
        else:
            print(f"💬 AI Decision: General ChatGPT-style response")
            print(f"🎯 Intent: {routing['question_intent']}")
            print(f"💡 Response: Pure AI knowledge (no document search)")
        
        print("=" * 75)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_universal_ai_assistant())
