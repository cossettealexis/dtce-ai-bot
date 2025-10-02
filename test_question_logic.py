#!/usr/bin/env python3
"""
Test the _is_likely_question logic
"""

def _is_likely_question(message: str) -> bool:
    """Determine if a message is likely a real question/search query."""
    message_lower = message.lower().strip()
    
    print(f"Testing message: '{message}'")
    print(f"Message length: {len(message)}")
    
    # Too short to be a meaningful question
    if len(message) < 8:
        print("❌ Too short (< 8 characters)")
        return False
    
    # Contains question words
    question_indicators = [
        'what', 'how', 'where', 'when', 'why', 'who', 'which', 'can', 'could', 
        'would', 'should', 'do', 'does', 'did', 'is', 'are', 'was', 'were',
        'find', 'show', 'search', 'look', 'tell', 'explain', 'help me',
        'need', 'want', 'looking for', 'project', 'report', 'document',
        'drawing', 'calculation', 'standard', 'policy', 'procedure'
    ]
    
    # Check if message contains question indicators
    for indicator in question_indicators:
        if indicator in message_lower:
            print(f"✅ Contains question indicator: '{indicator}'")
            return True
    
    # Contains question mark
    if '?' in message:
        print("✅ Contains question mark")
        return True
    
    # Contains engineering/technical terms
    technical_terms = [
        'structural', 'design', 'building', 'construction', 'engineering',
        'concrete', 'steel', 'timber', 'foundation', 'seismic', 'load',
        'beam', 'column', 'slab', 'wall', 'bridge', 'nzs', 'code',
        'compliance', 'certification', 'ps1', 'ps2', 'ps3', 'ps4'
    ]
    
    for term in technical_terms:
        if term in message_lower:
            print(f"✅ Contains technical term: '{term}'")
            return True
    
    # Multiple words (likely a sentence)
    if len(message.split()) >= 3:
        print(f"✅ Multiple words: {len(message.split())} words")
        return True
    
    print("❌ Not classified as a question")
    return False

# Test cases
test_messages = [
    "test",
    "hello",
    "What is NZS 3604?",
    "testing the system", 
    "hi there how are you",
    "Find structural calculations"
]

for msg in test_messages:
    result = _is_likely_question(msg)
    print(f"Result: {result}")
    print("-" * 40)
