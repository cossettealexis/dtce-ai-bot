"""
Microsoft Teams bot implementation for DTCE AI Assistant.
"""

from botbuilder.core import ActivityHandler, TurnContext, MessageFactory, CardFactory
from botbuilder.core.conversation_state import ConversationState
from botbuilder.core.user_state import UserState
from botbuilder.schema import ChannelAccount, Activity, ActivityTypes, Attachment
import json
import asyncio
import structlog
from typing import List, Optional

from ..services.document_qa import DocumentQAService

logger = structlog.get_logger(__name__)


class DTCETeamsBot(ActivityHandler):
    """Microsoft Teams bot for DTCE AI Assistant."""
    
    def __init__(self, conversation_state: ConversationState, user_state: UserState, 
                 search_client, qa_service: DocumentQAService):
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.search_client = search_client
        self.qa_service = qa_service
        
    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages from users."""
        
        user_message = turn_context.activity.text.strip()
        user_name = turn_context.activity.from_property.name if turn_context.activity.from_property else "User"
        
        logger.info("Received Teams message", user=user_name, message=user_message)
        
        # Handle basic greetings
        if user_message.lower() in ['hi', 'hello', 'hey', 'hi there', 'hello there']:
            await self._send_welcome_message(turn_context)
            return
        
        # Check for special commands
        if user_message.lower() in ['/help', 'help', '/start', 'start']:
            await self._send_welcome_message(turn_context)
            return
        
        if user_message.lower() in ['/health', 'health', 'status']:
            await self._send_health_status(turn_context)
            return
            
        if user_message.lower().startswith('/projects') or user_message.lower() == 'projects':
            await self._send_projects_list(turn_context)
            return
        
        # Handle search commands
        if user_message.lower().startswith('/search ') or user_message.lower().startswith('search '):
            query = user_message.split(' ', 1)[1] if ' ' in user_message else ""
            if query:
                await self._handle_search(turn_context, query)
            else:
                await turn_context.send_activity("Please provide a search query. Example: `/search bridge calculations`")
            return
        
        # Handle ask commands  
        if user_message.lower().startswith('/ask ') or user_message.lower().startswith('ask '):
            question = user_message.split(' ', 1)[1] if ' ' in user_message else ""
            if question:
                await self._handle_question(turn_context, question)
            else:
                await turn_context.send_activity("Please provide a question. Example: `/ask What are the seismic requirements?`")
            return
        
        # Default: treat as a question
        if len(user_message) > 5:  # Minimum question length
            await self._handle_question(turn_context, user_message)
        else:
            await self._send_welcome_message(turn_context)

    async def _send_welcome_message(self, turn_context: TurnContext):
        """Send welcome message with available commands."""
        
        welcome_text = """
🤖 **Welcome to DTCE AI Assistant!**

I can help you find information from engineering documents and project files.

**Available Commands:**
• `/help` - Show this help message
• `/search [query]` - Search documents (e.g., `/search bridge calculations`)
• `/ask [question]` - Ask questions about documents (e.g., `/ask What are the seismic requirements?`)
• `/projects` - List available projects
• `/health` - Check system status

**Quick Examples:**
• "What projects do we have?"
• "Show me structural calculations for project 222"
• "What were the conclusions in the final report?"

Just type your question and I'll search through your engineering documents to help! 🔍
        """
        
        await turn_context.send_activity(MessageFactory.text(welcome_text.strip()))

    async def _send_health_status(self, turn_context: TurnContext):
        """Send system health status."""
        
        try:
            # Check if QA service is available
            if self.qa_service:
                status_text = "✅ **System Status: HEALTHY**\n\n"
                status_text += "• Document search: Available\n"
                status_text += "• AI Q&A service: Available\n"
                status_text += "• Teams integration: Active\n"
            else:
                status_text = "⚠️ **System Status: DEGRADED**\n\n"
                status_text += "• Document search: Unavailable\n"
                status_text += "• AI Q&A service: Unavailable\n"
                status_text += "• Teams integration: Active\n"
                
            await turn_context.send_activity(MessageFactory.text(status_text))
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            await turn_context.send_activity("❌ **System Status: ERROR** - Unable to check system health")

    async def _send_projects_list(self, turn_context: TurnContext):
        """Send list of available projects."""
        
        try:
            if not self.qa_service:
                await turn_context.send_activity("❌ Document service unavailable")
                return
                
            # Get document summary to show available projects
            summary = await self.qa_service.get_document_summary()
            
            if "error" in summary:
                await turn_context.send_activity(f"❌ Error getting projects: {summary['error']}")
                return
            
            projects = summary.get('projects', [])
            total_docs = summary.get('total_documents', 0)
            
            if projects:
                projects_text = f"📋 **Available Projects** ({total_docs} total documents):\n\n"
                for project in projects[:10]:  # Show first 10 projects
                    projects_text += f"• {project}\n"
                    
                if len(projects) > 10:
                    projects_text += f"... and {len(projects) - 10} more projects\n"
                    
                projects_text += f"\nUse `/search project [number]` to find specific project documents."
            else:
                projects_text = "📋 No projects found in the document index."
                
            await turn_context.send_activity(MessageFactory.text(projects_text))
            
        except Exception as e:
            logger.error("Projects list failed", error=str(e))
            await turn_context.send_activity("❌ Error retrieving projects list")

    async def _handle_search(self, turn_context: TurnContext, query: str):
        """Handle search requests."""
        
        try:
            if not self.qa_service:
                await turn_context.send_activity("❌ Search service unavailable")
                return
            
            # Send typing indicator
            await turn_context.send_activity(Activity(type=ActivityTypes.typing))
            
            # Perform search using the QA service
            result = await self.qa_service.answer_question(f"Find documents about: {query}")
            
            if result['documents_searched'] == 0:
                await turn_context.send_activity(f"🔍 No documents found for: **{query}**")
                return
            
            # Format search results
            response_text = f"🔍 **Search Results for:** {query}\n\n"
            response_text += f"Found {result['documents_searched']} relevant documents:\n\n"
            
            for i, source in enumerate(result['sources'][:5], 1):
                response_text += f"**{i}. {source['filename']}**\n"
                response_text += f"Project: {source['project_id']}\n"
                if source.get('excerpt'):
                    response_text += f"Preview: {source['excerpt'][:100]}...\n"
                response_text += "\n"
            
            await turn_context.send_activity(MessageFactory.text(response_text))
            
        except Exception as e:
            logger.error("Search failed", error=str(e), query=query)
            await turn_context.send_activity(f"❌ Search failed: {str(e)}")

    async def _handle_question(self, turn_context: TurnContext, question: str):
        """Handle Q&A requests."""
        
        try:
            if not self.qa_service:
                await turn_context.send_activity("❌ Q&A service unavailable")
                return
            
            # Send typing indicator
            await turn_context.send_activity(Activity(type=ActivityTypes.typing))
            
            # Get answer from QA service
            result = await self.qa_service.answer_question(question)
            
            # Format response
            if result['confidence'] == 'error':
                await turn_context.send_activity(f"❌ Error: {result['answer']}")
                return
            
            confidence_emoji = {
                'high': '🎯',
                'medium': '🤔', 
                'low': '❓'
            }.get(result['confidence'], '❓')
            
            response_text = f"💬 **Question:** {question}\n\n"
            response_text += f"{confidence_emoji} **Answer:** {result['answer']}\n\n"
            
            if result['sources']:
                response_text += "📚 **Sources:**\n"
                for source in result['sources'][:3]:
                    response_text += f"• {source['filename']} (Project: {source['project_id']})\n"
            
            response_text += f"\n🔍 Searched {result['documents_searched']} documents"
            
            await turn_context.send_activity(MessageFactory.text(response_text))
            
        except Exception as e:
            logger.error("Q&A failed", error=str(e), question=question)
            await turn_context.send_activity(f"❌ Failed to answer question: {str(e)}")

    async def on_members_added_activity(self, members_added: List[ChannelAccount], turn_context: TurnContext):
        """Welcome new members."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome_message(turn_context)
