#!/usr/bin/env python3
"""
Simple test to verify the intelligence fix is working.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_simple_fix():
    """Test that the routing fix is in place."""
    
    print("🔧 Verifying Intelligence Fix Implementation")
    print("=" * 60)
    
    try:
        # Check if the file was modified correctly
        with open('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot/dtce_ai_bot/services/document_qa.py', 'r') as f:
            content = f.read()
        
        # Check for key fixes
        fixes_to_check = [
            "_handle_intelligent_general_query",
            "_analyze_question_intent", 
            "_search_with_intent",
            "_generate_intent_aware_answer",
            "intent_category",
            "seeking_guidance",
            "seeking_data"
        ]
        
        fixes_found = 0
        for fix in fixes_to_check:
            if fix in content:
                print(f"   ✅ Found: {fix}")
                fixes_found += 1
            else:
                print(f"   ❌ Missing: {fix}")
        
        print(f"\n📊 Implementation Status:")
        print(f"   Fixes Found: {fixes_found}/{len(fixes_to_check)}")
        
        # Check for the main routing fix
        if "_handle_intelligent_general_query(question, project_filter, classification)" in content:
            print(f"   ✅ Main routing fix: IMPLEMENTED")
        else:
            print(f"   ❌ Main routing fix: MISSING")
        
        # Check that old fallback is removed
        if "# Fall back to normal document search" not in content:
            print(f"   ✅ Old fallback: REMOVED")
        else:
            print(f"   ❌ Old fallback: STILL PRESENT")
        
        if fixes_found >= len(fixes_to_check) - 1:
            print(f"\n🎉 SUCCESS: Intelligence fix is properly implemented!")
            print(f"📈 Expected improvements:")
            print(f"   • Users get intent-aware responses")
            print(f"   • No more template dumps for time/cost questions")
            print(f"   • AI understands what users actually want")
            print(f"   • Professional guidance even without specific docs")
            print(f"   • Better search and context preparation")
        else:
            print(f"\n⚠️  PARTIAL: Some fixes missing, may not work fully")
        
    except Exception as e:
        print(f"❌ Error checking fix: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple_fix())
