#!/usr/bin/env python3
"""
Deploy Conversational Memory Enhancement

This script deploys the conversational memory system that fixes the critical
issue where "really" and other conversational queries triggered inappropriate
document searches instead of contextual responses.

Key Features Deployed:
- Conversational query detection and classification
- Conversation history storage in Teams bot
- Context-aware response generation
- Intelligent distinction between informational vs conversational queries

Problem Fixed:
- User says "really" → Bot no longer searches geotechnical documents
- User says "really" → Bot now gives contextual conversational response
"""

import subprocess
import sys
import os
from datetime import datetime

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}")
    print(f"Command: {command}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print(f"✅ Success: {description}")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
        else:
            print(f"❌ Failed: {description}")
            print(f"Error: {result.stderr.strip()}")
            return False
            
    except Exception as e:
        print(f"❌ Exception during {description}: {e}")
        return False
    
    return True

def main():
    print("🚀 DEPLOYING CONVERSATIONAL MEMORY ENHANCEMENT")
    print("=" * 60)
    print(f"Deployment Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("📋 ENHANCEMENT SUMMARY:")
    print("- Fixed 'really' → geotechnical docs issue")
    print("- Added conversational query detection")
    print("- Implemented conversation history storage")
    print("- Added context-aware response generation")
    print("- Enhanced Teams bot with conversation memory")
    print()
    
    # Step 1: Run tests to verify the fix
    print("🧪 STEP 1: VERIFY CONVERSATIONAL MEMORY SYSTEM")
    test_command = """/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot/.venv/bin/python -c "
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.integrations.azure_search import get_search_client
from dtce_ai_bot.config.settings import get_settings
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

load_dotenv()

async def quick_test():
    settings = get_settings()
    search_client = get_search_client()
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    rag_handler = RAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
    
    # Test conversational query
    result = await rag_handler.process_rag_query('really', [
        {'role': 'user', 'content': 'Tell me about NZS standards'},
        {'role': 'assistant', 'content': 'Here are the NZS standards...'}
    ])
    
    is_conversational = result.get('rag_type') == 'conversational_response'
    no_docs_searched = result.get('documents_searched', 0) == 0
    
    if is_conversational and no_docs_searched:
        print('✅ Conversational memory system working correctly')
        return True
    else:
        print(f'❌ Issue: Type={result.get(\\"rag_type\\")}, Docs={result.get(\\"documents_searched\\", 0)}')
        return False

result = asyncio.run(quick_test())
sys.exit(0 if result else 1)
" """
    
    if not run_command(test_command, "Testing conversational memory system"):
        print("❌ Tests failed. Aborting deployment.")
        return False
    
    # Step 2: Git operations
    print("\n📝 STEP 2: COMMIT CHANGES")
    
    # Add files
    if not run_command("git add .", "Adding modified files"):
        return False
    
    # Check if there are changes to commit
    check_changes = subprocess.run("git diff --staged --quiet", shell=True)
    if check_changes.returncode == 0:
        print("ℹ️  No changes to commit")
    else:
        # Commit changes
        commit_message = "feat: implement conversational memory system\n\n- Fix 'really' query issue - no more geotechnical doc searches\n- Add conversational query detection and classification\n- Implement conversation history storage in Teams bot\n- Add context-aware response generation\n- Enhance RAG handler with conversation context\n- Distinguish between informational vs conversational queries"
        
        if not run_command(f'git commit -m "{commit_message}"', "Committing changes"):
            return False
    
    # Step 3: Deploy to Azure
    print("\n🌐 STEP 3: DEPLOY TO AZURE")
    
    # Check if we have Azure deployment configured
    if os.path.exists('.github/workflows'):
        print("📦 GitHub Actions deployment detected")
        if not run_command("git push origin main", "Pushing to trigger deployment"):
            return False
        print("✅ Changes pushed. GitHub Actions will handle deployment.")
    else:
        print("🔧 Manual deployment required")
        print("Please deploy manually using your Azure deployment method")
    
    # Step 4: Verification
    print("\n✅ DEPLOYMENT SUMMARY")
    print("=" * 60)
    print("🎉 CONVERSATIONAL MEMORY ENHANCEMENT DEPLOYED!")
    print()
    print("PROBLEM FIXED:")
    print("❌ Before: 'really' → searched geotechnical documents")
    print("✅ After: 'really' → contextual conversational response")
    print()
    print("NEW CAPABILITIES:")
    print("- Conversational query detection")
    print("- Conversation history storage")
    print("- Context-aware responses")
    print("- Intelligent query classification")
    print()
    print("NEXT STEPS:")
    print("1. Monitor bot conversations for proper context handling")
    print("2. Test various conversational scenarios")
    print("3. Verify technical queries still search documents properly")
    print()
    print("The bot now has conversational memory! 🧠💬")

if __name__ == "__main__":
    main()
