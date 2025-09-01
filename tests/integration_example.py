"""
Integration example: Adding the Client Relationship Handler to your main bot
"""

from typing import Dict, Any
from dtce_ai_bot.services.client_relationship_handler import ClientRelationshipHandler
from dtce_ai_bot.services.smart_rag_handler import SmartRAGHandler

class EnhancedRAGHandler(SmartRAGHandler):
    """
    Main RAG handler that automatically detects and routes client relationship queries
    """
    
    def __init__(self, search_client, openai_client, model_name: str):
        super().__init__(search_client, openai_client, model_name)
        
        # Initialize the specialized client handler
        self.client_handler = ClientRelationshipHandler(
            search_client, openai_client, model_name
        )
    
    def _is_client_relationship_query(self, query: str) -> bool:
        """Detect if this is a client relationship query that needs special handling."""
        
        # Look for patterns that indicate client/person queries
        client_patterns = [
            r'working with \w+',
            r'\w+ from \w+',
            r'\w+ at \w+',
            r'contact.*for \w+',
            r'anyone.*with \w+',
            r'projects with \w+',
            r'who.*represents',
            r'email from \w+',
            r'contact details',
            r'job number.*for',
            r'client for',
        ]
        
        import re
        for pattern in client_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        
        return False
    
    async def get_smart_answer(self, user_question: str) -> Dict[str, Any]:
        """
        Enhanced answer generation that automatically routes to specialized handlers.
        """
        
        # Check if this is a client relationship query
        if self._is_client_relationship_query(user_question):
            # Use the specialized client relationship handler
            return await self.client_handler.get_client_relationship_answer(user_question)
        
        # Otherwise use the standard smart handler
        return await super().get_smart_answer(user_question)

# Usage example in your main bot code:
"""
# In your main bot initialization:
enhanced_rag = EnhancedRAGHandler(search_client, openai_client, "gpt-4")

# When handling user messages:
if user_message:
    response = await enhanced_rag.get_smart_answer(user_message)
    
    # The response will automatically include:
    # - Enhanced company/person recognition
    # - Project details with job numbers  
    # - Contact information and addresses
    # - Specialized formatting for client queries
"""
