"""
Simple Conversation Context Manager for Enhanced RAG
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ConversationTurn:
    """Represents a single turn in a conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ConversationContextManager:
    """
    Manages conversation history and context for enhanced RAG interactions.
    """
    
    def __init__(self, max_history_length: int = 20):
        self.max_history_length = max_history_length
        self.conversations: Dict[str, List[ConversationTurn]] = {}
        logger.info("Conversation Context Manager initialized")
    
    def add_turn(self, session_id: str, role: str, content: str, 
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a conversation turn."""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.conversations[session_id].append(turn)
        
        # Keep only recent history
        if len(self.conversations[session_id]) > self.max_history_length:
            self.conversations[session_id] = self.conversations[session_id][-self.max_history_length:]
    
    def get_context(self, session_id: str, max_turns: int = 10) -> List[ConversationTurn]:
        """Get recent conversation context."""
        if session_id not in self.conversations:
            return []
        
        return self.conversations[session_id][-max_turns:]
    
    def clear_context(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        if session_id in self.conversations:
            del self.conversations[session_id]


# Global conversation manager instance
conversation_manager = ConversationContextManager()
