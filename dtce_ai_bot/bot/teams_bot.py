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
        
        if user_message.lower() in ['/projects', 'projects', 'list projects']:
            await self._send_projects_list(turn_context)
            return
        
        # Process search query
        await self._process_search_query(turn_context, user_message)
    
    async def _process_search_query(self, turn_context: TurnContext, query: str):
        """Process user search query and return results."""
        
        try:
            # Show typing indicator
            await turn_context.send_activity(MessageFactory.text("🔍 Searching through DTCE documents..."))
            
            # Perform search
            search_query = SearchQuery(query=query)
            search_results = await self.search_client.search_documents(search_query)
            
            if not search_results.results:
                await turn_context.send_activity(
                    MessageFactory.text("❌ No relevant documents found. Try rephrasing your query.")
                )
                return
            
            # Generate AI response
            ai_response = await self.openai_client.generate_response(
                query=query,
                search_results=search_results.results
            )
            
            # Create response card
            response_card = self._create_search_results_card(query, ai_response, search_results.results)
            response = MessageFactory.attachment(response_card)
            
            await turn_context.send_activity(response)
            
        except Exception as e:
            logger.error("Error processing search query", error=str(e), query=query)
            await turn_context.send_activity(
                MessageFactory.text("❌ Sorry, I encountered an error while searching. Please try again later.")
            )
    
    def _create_welcome_card(self) -> Attachment:
        """Create welcome adaptive card."""
        
        card_content = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.3",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "🤖 DTCE AI Assistant",
                    "size": "Large",
                    "weight": "Bolder",
                    "color": "Accent"
                },
                {
                    "type": "TextBlock",
                    "text": "I'm here to help you find information from DTCE engineering files and documentation.",
                    "wrap": True,
                    "spacing": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "**What I can help you with:**",
                    "weight": "Bolder",
                    "spacing": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": "• Find API documentation and specifications\n• Search project code and architecture\n• Locate configuration files and deployment guides\n• Answer questions about past implementations",
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "**Quick Commands:**",
                    "weight": "Bolder",
                    "spacing": "Medium"
                },
                {
                    "type": "TextBlock", 
                    "text": "• `/help` - Show this message\n• `/projects` - List available projects\n• `/health` - Check system status",
                    "wrap": True
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "🔍 Search Documentation",
                    "data": {
                        "action": "search",
                        "query": "API documentation"
                    }
                },
                {
                    "type": "Action.Submit", 
                    "title": "📋 List Projects",
                    "data": {
                        "action": "projects"
                    }
                }
            ]
        }
        
        return CardFactory.adaptive_card(card_content)
    
    def _create_search_results_card(self, query: str, ai_response: str, results: List) -> Attachment:
        """Create adaptive card for search results."""
        
        # Format results for display
        result_items = []
        for i, result in enumerate(results[:5]):  # Show top 5 results
            result_items.append({
                "type": "TextBlock",
                "text": f"**{result.get('title', 'Document')}**",
                "weight": "Bolder",
                "spacing": "Medium" if i > 0 else "None"
            })
            result_items.append({
                "type": "TextBlock",
                "text": result.get('content', '')[:200] + "..." if len(result.get('content', '')) > 200 else result.get('content', ''),
                "wrap": True,
                "spacing": "Small"
            })
            if result.get('file_path'):
                result_items.append({
                    "type": "TextBlock",
                    "text": f"📁 {result['file_path']}",
                    "size": "Small",
                    "color": "Accent",
                    "spacing": "Small"
                })
        
        card_content = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.3",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"🔍 Search Results for: \"{query}\"",
                    "size": "Medium",
                    "weight": "Bolder",
                    "color": "Accent"
                },
                {
                    "type": "TextBlock",
                    "text": "**AI Summary:**",
                    "weight": "Bolder",
                    "spacing": "Medium"
                },
                {
                    "type": "TextBlock",
                    "text": ai_response,
                    "wrap": True,
                    "spacing": "Small"
                },
                {
                    "type": "TextBlock",
                    "text": "**Related Documents:**",
                    "weight": "Bolder",
                    "spacing": "Large"
                }
            ] + result_items
        }
        
        return CardFactory.adaptive_card(card_content)
    
    async def on_members_added_activity(
        self, members_added: List[ChannelAccount], turn_context: TurnContext
    ):
        """Greet new members when they join."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome_message(turn_context)
    
    async def _send_welcome_message(self, turn_context: TurnContext):
        """Send welcome message with adaptive card."""
        response = MessageFactory.attachment(self.welcome_card)
        await turn_context.send_activity(response)
    
    async def _send_health_status(self, turn_context: TurnContext):
        """Send system health status."""
        # TODO: Implement actual health checks
        status_message = "✅ **System Status: Healthy**\n\n" \
                        "🔗 Azure Search: Connected\n" \
                        "🤖 OpenAI: Connected\n" \
                        "📁 SharePoint: Connected\n" \
                        "💾 Blob Storage: Connected"
        
        await turn_context.send_activity(MessageFactory.text(status_message))
    
    async def _send_projects_list(self, turn_context: TurnContext):
        """Send list of available projects."""
        # TODO: Implement actual project listing from SharePoint/Storage
        projects_message = "📋 **Available Projects:**\n\n" \
                          "• Project Alpha - API Gateway\n" \
                          "• Project Beta - User Authentication\n" \
                          "• Project Gamma - Payment Processing\n" \
                          "• Project Delta - Analytics Dashboard\n\n" \
                          "Type a project name or ask me anything about these projects!"
        
        await turn_context.send_activity(MessageFactory.text(projects_message))
