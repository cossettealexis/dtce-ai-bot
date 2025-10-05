#!/usr/bin/env python3
"""
Simple RAG test
"""
print("🚀 Starting RAG test...")

try:
    from dtce_ai_bot.config.settings import get_settings
    settings = get_settings()
    print(f"✅ Settings loaded: {settings.app_name}")
    
    from dtce_ai_bot.services.azure_rag_service import AzureRAGService
    print("✅ Azure RAG Service imported")
    
    print("🎯 RAG system is properly set up!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
