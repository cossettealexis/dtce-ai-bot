#!/usr/bin/env python3
"""
Debug script to check syntax of teams_bot.py in Azure environment
"""

import ast
import sys
import traceback

def check_teams_bot_syntax():
    """Check the syntax of teams_bot.py"""
    try:
        with open('dtce_ai_bot/bot/teams_bot.py', 'r') as f:
            source_code = f.read()
        
        print(f"📄 File size: {len(source_code)} characters")
        print(f"📄 Lines: {len(source_code.splitlines())}")
        
        # Try to compile
        try:
            compile(source_code, 'dtce_ai_bot/bot/teams_bot.py', 'exec')
            print("✅ Compile successful")
        except SyntaxError as e:
            print(f"❌ Syntax Error during compile: {e}")
            print(f"   Line {e.lineno}: {e.text}")
            return False
        
        # Try to parse AST
        try:
            tree = ast.parse(source_code)
            print("✅ AST parse successful")
        except SyntaxError as e:
            print(f"❌ Syntax Error during AST parse: {e}")
            print(f"   Line {e.lineno}: {e.text}")
            return False
        
        # Try to import
        try:
            sys.path.insert(0, '.')
            from dtce_ai_bot.bot.teams_bot import DTCETeamsBot
            print("✅ Import successful")
        except Exception as e:
            print(f"❌ Import error: {e}")
            # This is expected due to missing dependencies
        
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔍 Debugging teams_bot.py syntax...")
    success = check_teams_bot_syntax()
    print(f"🏁 Result: {'✅ PASS' if success else '❌ FAIL'}")
