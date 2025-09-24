"""
Conversation Context Manager for Enhanced RAG
Manages conversation history and context for improved multi-turn interactions
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationTurn':
        """Create from dictionary."""
        return cls(
            role=data['role'],
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=data.get('metadata', {})
        )


class ConversationContextManager:
    """
    Manages conversation history and context for enhanced RAG interactions.
    
    Features:
    - Context-aware query understanding
    - Reference resolution (pronouns, "this project", etc.)
    - Topic continuity tracking
    - Conversation summarization for long histories
    """
    
    def __init__(self, max_history_length: int = 20, context_window_minutes: int = 30):
        self.max_history_length = max_history_length
        self.context_window_minutes = context_window_minutes
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
        
        # Trim history if too long
        if len(self.conversations[session_id]) > self.max_history_length:
            self.conversations[session_id] = self.conversations[session_id][-self.max_history_length:]
        
        logger.info("Added conversation turn", 
                   session_id=session_id, 
                   role=role, 
                   content_length=len(content))
    
    def get_context_for_query(self, session_id: str, current_query: str) -> Dict[str, Any]:
        """
        Get relevant conversation context for the current query.
        
        Returns enhanced context including:
        - Recent conversation history
        - Resolved references
        - Topic continuity
        - Previous source information
        """
        
        if session_id not in self.conversations:
            return {
                'has_context': False,
                'history': [],
                'resolved_references': {},
                'topics': [],
                'previous_sources': []
            }
        
        recent_turns = self._get_recent_turns(session_id)
        
        if not recent_turns:
            return {
                'has_context': False,
                'history': [],
                'resolved_references': {},
                'topics': [],
                'previous_sources': []
            }
        
        # Resolve references in current query
        resolved_references = self._resolve_references(current_query, recent_turns)
        
        # Extract topics and continuity
        topics = self._extract_topics(recent_turns)
        
        # Get previous source information
        previous_sources = self._extract_previous_sources(recent_turns)
        
        # Format history for LLM context
        formatted_history = self._format_history_for_llm(recent_turns)
        
        return {
            'has_context': True,
            'history': formatted_history,
            'resolved_references': resolved_references,
            'topics': topics,
            'previous_sources': previous_sources,
            'context_summary': self._create_context_summary(recent_turns)
        }
    
    def _get_recent_turns(self, session_id: str) -> List[ConversationTurn]:
        """Get recent conversation turns within the context window."""
        
        if session_id not in self.conversations:
            return []
        
        cutoff_time = datetime.now() - timedelta(minutes=self.context_window_minutes)
        recent_turns = [
            turn for turn in self.conversations[session_id]
            if turn.timestamp > cutoff_time
        ]
        
        # Limit to last few exchanges for token efficiency
        return recent_turns[-10:]  # Last 5 exchanges (10 turns)
    
    def _resolve_references(self, query: str, history: List[ConversationTurn]) -> Dict[str, str]:
        """
        Resolve pronouns and references in the query based on conversation history.
        
        Examples:
        - "it" -> "the foundation design"
        - "this project" -> "Project 225 - Auckland Bridge"
        - "that report" -> "Structural Analysis Report v2.1"
        """
        
        references = {}
        query_lower = query.lower()
        
        # Find recent entities mentioned
        recent_entities = self._extract_entities_from_history(history)
        
        # Resolve common references
        if 'it' in query_lower and recent_entities.get('last_document'):
            references['it'] = recent_entities['last_document']
        
        if 'this project' in query_lower and recent_entities.get('current_project'):
            references['this project'] = recent_entities['current_project']
        
        if 'that report' in query_lower and recent_entities.get('last_report'):
            references['that report'] = recent_entities['last_report']
        
        if 'the standard' in query_lower and recent_entities.get('last_standard'):
            references['the standard'] = recent_entities['last_standard']
        
        return references
    
    def _extract_entities_from_history(self, history: List[ConversationTurn]) -> Dict[str, str]:
        """Extract key entities (projects, documents, standards) from history."""
        
        entities = {}
        
        for turn in reversed(history):  # Most recent first
            content = turn.content
            
            # Extract project references
            if not entities.get('current_project'):
                project_match = self._find_project_reference(content)
                if project_match:
                    entities['current_project'] = project_match
            
            # Extract document references
            if not entities.get('last_document'):
                doc_match = self._find_document_reference(content)
                if doc_match:
                    entities['last_document'] = doc_match
            
            # Extract standard references
            if not entities.get('last_standard'):
                standard_match = self._find_standard_reference(content)
                if standard_match:
                    entities['last_standard'] = standard_match
            
            # Extract report references
            if not entities.get('last_report'):
                report_match = self._find_report_reference(content)
                if report_match:
                    entities['last_report'] = report_match
        
        return entities
    
    def _find_project_reference(self, content: str) -> Optional[str]:
        """Find project references in content."""
        
        import re
        
        # Pattern for "Project XXX" or "project number XXX"
        project_patterns = [
            r'[Pp]roject\s+(\d+)',
            r'[Pp]roject\s+([A-Z]\d+)',
            r'[Pp]roject\s+([^.\n,]+)',
        ]
        
        for pattern in project_patterns:
            match = re.search(pattern, content)
            if match:
                return f"Project {match.group(1)}"
        
        return None
    
    def _find_document_reference(self, content: str) -> Optional[str]:
        """Find document references in content."""
        
        import re
        
        # Look for document names in sources or content
        doc_patterns = [
            r'([^/\n]+\.pdf)',
            r'([^/\n]+\.docx?)',
            r'Source \d+:\s*([^\n(]+)',
            r'Document:\s*([^\n(]+)'
        ]
        
        for pattern in doc_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _find_standard_reference(self, content: str) -> Optional[str]:
        """Find NZ Standard references in content."""
        
        import re
        
        # Pattern for NZS references
        nzs_pattern = r'(NZS\s+\d+(?:\.\d+)*(?::\d+)?)'
        match = re.search(nzs_pattern, content)
        
        if match:
            return match.group(1)
        
        return None
    
    def _find_report_reference(self, content: str) -> Optional[str]:
        """Find report references in content."""
        
        import re
        
        report_patterns = [
            r'([^/\n]*[Rr]eport[^/\n]*)',
            r'([^/\n]*[Aa]nalysis[^/\n]*)',
            r'([^/\n]*[Cc]alculation[^/\n]*)'
        ]
        
        for pattern in report_patterns:
            match = re.search(pattern, content)
            if match:
                doc_name = match.group(1).strip()
                if len(doc_name) < 100:  # Reasonable document name length
                    return doc_name
        
        return None
    
    def _extract_topics(self, history: List[ConversationTurn]) -> List[str]:
        """Extract main topics from conversation history."""
        
        topics = []
        
        # Engineering topic keywords
        engineering_topics = [
            'foundation', 'structural', 'seismic', 'load', 'concrete', 'steel',
            'wind', 'earthquake', 'building code', 'compliance', 'design',
            'analysis', 'calculation', 'geotechnical', 'soil'
        ]
        
        for turn in history:
            content_lower = turn.content.lower()
            for topic in engineering_topics:
                if topic in content_lower and topic not in topics:
                    topics.append(topic)
        
        return topics[:5]  # Limit to top 5 topics
    
    def _extract_previous_sources(self, history: List[ConversationTurn]) -> List[Dict[str, str]]:
        """Extract information about previously referenced sources."""
        
        sources = []
        
        for turn in history:
            if turn.role == 'assistant' and turn.metadata:
                # Extract source information from metadata
                if 'sources' in turn.metadata:
                    for source in turn.metadata['sources'][:3]:  # Last 3 sources
                        sources.append({
                            'filename': source.get('filename', ''),
                            'project': source.get('project_name', ''),
                            'relevance': 'previous_query'
                        })
        
        return sources[-5:]  # Last 5 sources
    
    def _format_history_for_llm(self, history: List[ConversationTurn]) -> List[Dict[str, str]]:
        """Format conversation history for LLM context."""
        
        formatted = []
        
        for turn in history[-6:]:  # Last 3 exchanges
            formatted.append({
                'role': turn.role,
                'content': turn.content[:500] if len(turn.content) > 500 else turn.content  # Truncate long content
            })
        
        return formatted
    
    def _create_context_summary(self, history: List[ConversationTurn]) -> str:
        """Create a summary of the conversation context."""
        
        if not history:
            return ""
        
        recent_user_queries = [
            turn.content for turn in history[-4:]
            if turn.role == 'user'
        ]
        
        if not recent_user_queries:
            return ""
        
        # Simple summary based on recent queries
        if len(recent_user_queries) == 1:
            return f"User is asking about: {recent_user_queries[0][:100]}..."
        else:
            return f"User is in a conversation about engineering topics, most recently asking: {recent_user_queries[-1][:100]}..."
    
    def clear_session(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        
        if session_id in self.conversations:
            del self.conversations[session_id]
            logger.info("Cleared conversation history", session_id=session_id)
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of the conversation session."""
        
        if session_id not in self.conversations:
            return {'exists': False}
        
        turns = self.conversations[session_id]
        
        return {
            'exists': True,
            'turn_count': len(turns),
            'start_time': turns[0].timestamp.isoformat() if turns else None,
            'last_activity': turns[-1].timestamp.isoformat() if turns else None,
            'topics': self._extract_topics(turns),
            'user_queries': len([t for t in turns if t.role == 'user']),
            'bot_responses': len([t for t in turns if t.role == 'assistant'])
        }


# Global conversation manager instance
conversation_manager = ConversationContextManager()
