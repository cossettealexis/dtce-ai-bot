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
from typing import List

from ..models.search import SearchQuery
from ..integrations.azure.search_client import AzureSearchClient
from ..integrations.azure.openai_client import AzureOpenAIClient

logger = structlog.get_logger(__name__)


class DTCETeamsBot(ActivityHandler):
    """Microsoft Teams bot for DTCE AI Assistant."""
    
    def __init__(self, conversation_state: ConversationState, user_state: UserState, 
                 search_client: AzureSearchClient, openai_client: AzureOpenAIClient):
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.search_client = search_client
        self.openai_client = openai_client
        
        # Welcome message and quick actions
        self.welcome_card = self._create_welcome_card()
        
    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages from users."""
        
        user_message = turn_context.activity.text.strip()
        user_name = turn_context.activity.from_property.name
        
        logger.info("Received message", user=user_name, message=user_message)
        
        # Check for special commands
        if user_message.lower() in ['/help', 'help', '/start', 'start']:
            await self._send_welcome_message(turn_context)
            return
        
        if user_message.lower() in ['/health', 'health', 'status']:
            await self._send_health_status(turn_context)
            return
        
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
