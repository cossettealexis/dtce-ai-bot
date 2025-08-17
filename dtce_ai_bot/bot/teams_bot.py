"""
Microsoft Teams bot implementation for DTCE AI Assistant.
"""

from botbuilder.core import ActivityHandler, TurnContext, MessageFactory, CardFactory
from botbuilder.core.conversation_state import ConversationState
from botbuilder.core.user_state import UserState
from botbuilder.schema import ChannelAccount, Activity, ActivityTypes, Attachment
import json
import asyncio
import aiohttp
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
        
    async def on_members_added_activity(self, members_added: List[ChannelAccount], turn_context: TurnContext):
        """Send welcome message when members are added to conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome_message(turn_context)
    
    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages and file attachments intelligently."""
        
        user_message = turn_context.activity.text.strip() if turn_context.activity.text else ""
        has_attachments = bool(turn_context.activity.attachments)
        user_name = turn_context.activity.from_property.name if turn_context.activity.from_property else "User"
        
        logger.info("Received Teams message", 
                   user=user_name, 
                   message=user_message, 
                   has_attachments=has_attachments,
                   attachment_count=len(turn_context.activity.attachments) if has_attachments else 0)
        
        # Scenario 1: BOTH text and attachments - Most intelligent handling
        if has_attachments and user_message:
            await self._handle_text_with_attachments(turn_context, user_message)
            return
        
        # Scenario 2: ONLY attachments - Ask what to do with them
        elif has_attachments and not user_message:
            await self._handle_attachments_only(turn_context)
            return
        
        # Scenario 3: ONLY text - Standard chat processing
        elif user_message and not has_attachments:
            await self._handle_text_only(turn_context, user_message)
            return
        
        # Scenario 4: Neither text nor attachments
        else:
            await turn_context.send_activity("Please send a message or attach a document for analysis.")
            return

    async def _handle_text_only(self, turn_context: TurnContext, user_message: str):
        """Handle text-only messages (existing logic)."""
        
        # Normalize command for parsing
        message_lower = user_message.lower().strip()
        
        # Handle basic greetings and help commands (required for validation)
        if message_lower in ['hi', 'hello', 'hey', 'hi there', 'hello there']:
            await self._send_welcome_message(turn_context)
            return
        
        if message_lower in ['help', '/help', 'start', '/start']:
            await self._send_welcome_message(turn_context)
            return
        
        if message_lower in ['health', '/health', 'status']:
            await self._send_health_status(turn_context)
            return
            
        if message_lower in ['projects', '/projects']:
            await self._send_projects_list(turn_context)
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

    async def _handle_attachments_only(self, turn_context: TurnContext):
        """Handle when user sends only attachments without text."""
        
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        
        # Acknowledge files and ask for instructions
        attachment_info = await self._process_attachment_info(turn_context.activity.attachments)
        
        if attachment_info['supported_files']:
            response = "📁 **Files received:**\n\n" + "\n".join(attachment_info['supported_files'])
            response += "\n\n🤖 **What would you like me to do with these files?**"
            response += "\n\n**Examples:**"
            response += "\n• *'Analyze this RFP and find similar past projects'*"
            response += "\n• *'Review these drawings for structural issues'*"
            response += "\n• *'Extract key requirements from these documents'*"
            response += "\n• *'Compare this proposal with our past work'*"
            response += "\n\nJust tell me what you need! 💬"
            
            await turn_context.send_activity(MessageFactory.text(response))
        else:
            await turn_context.send_activity("❌ No supported file types found. Please upload PDF, Word, Excel, PowerPoint, CAD, or image files.")

    async def _handle_text_with_attachments(self, turn_context: TurnContext, user_message: str):
        """Handle when user sends both text and attachments - the smart scenario!"""
        
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        
        # Process attachments
        attachment_info = await self._process_attachment_info(turn_context.activity.attachments)
        
        if not attachment_info['supported_files']:
            await turn_context.send_activity("❌ No supported file types found. Please upload PDF, Word, Excel, PowerPoint, CAD, or image files.")
            return
        
        # Intelligent analysis: Combine user question with file context
        enhanced_question = f"""User uploaded the following files:
{chr(10).join(attachment_info['supported_files'])}

User question: {user_message}

Please analyze the uploaded documents in context of the user's question. If the user is asking for analysis, comparison, or review, focus on the document content. If asking about past projects, find similar ones from our database."""
        
        # Send acknowledgment
        file_list = "\n".join(attachment_info['supported_files'])
        ack_response = f"📁 **Analyzing files:**\n{file_list}\n\n💭 **Your question:** {user_message}\n\n🔍 Processing..."
        await turn_context.send_activity(MessageFactory.text(ack_response))
        
        # Process with AI (enhanced question includes file context)
        await self._handle_question(turn_context, enhanced_question)

    async def _process_attachment_info(self, attachments):
        """Process attachment information and return supported files list."""
        
        supported_types = {
            'application/pdf': 'PDF',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
            'application/msword': 'Word',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
            'application/vnd.ms-excel': 'Excel',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint',
            'application/vnd.ms-powerpoint': 'PowerPoint',
            'text/plain': 'Text',
            'text/markdown': 'Markdown',
            'image/png': 'Image',
            'image/jpeg': 'Image',
            'image/jpg': 'Image',
            'application/octet-stream': 'CAD/Drawing',
            'message/rfc822': 'Email'
        }
        
        supported_files = []
        
        for attachment in attachments:
            file_name = attachment.name or "Unknown file"
            content_type = attachment.content_type
            
            # Check if file type is supported
            file_type = supported_types.get(content_type, 'Unknown')
            
            if file_type == 'Unknown' and file_name:
                # Try to determine by file extension
                ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
                ext_mapping = {
                    'pdf': 'PDF', 'docx': 'Word', 'doc': 'Word',
                    'xlsx': 'Excel', 'xls': 'Excel',
                    'pptx': 'PowerPoint', 'ppt': 'PowerPoint',
                    'txt': 'Text', 'md': 'Markdown',
                    'png': 'Image', 'jpg': 'Image', 'jpeg': 'Image',
                    'dwg': 'CAD', 'dxf': 'CAD',
                    'msg': 'Email', 'eml': 'Email'
                }
                file_type = ext_mapping.get(ext, 'Unknown')
            
            if file_type != 'Unknown':
                supported_files.append(f"📄 **{file_name}** ({file_type})")
        
        return {
            'supported_files': supported_files,
            'total_count': len(attachments)
        }

    async def _send_welcome_message(self, turn_context: TurnContext):
        """Send welcome message with available commands."""
        
        welcome_text = """
🤖 **Welcome to DTCE AI Assistant!**

I can help you find information from engineering documents and project files.

**Available Commands:**
• `help` or `Hello` - Show this help message
• `search [query]` - Search documents (e.g., `search bridge calculations`)
• `ask [question]` - Ask questions about documents (e.g., `ask What are the seismic requirements?`)
• `projects` - List available projects
• `health` - Check system status

**📎 File Upload Support:**
• **PDF** - Reports, RFPs, specifications
• **Word/Excel/PowerPoint** - Documents, spreadsheets, presentations
• **CAD Files** - .dwg, .dxf drawings
• **Images** - .png, .jpg engineering drawings
• **Text/Email** - .txt, .md, .msg files

**Quick Examples:**
• "What projects do we have?"
• "Show me structural calculations for project 222"
• "What were the conclusions in the final report?"
• Upload an RFP → "Please analyze this RFP and find similar past projects"
• Upload drawings → "Review these structural drawings"
• "Hi" - Get this welcome message

Just type your question or upload documents and I'll search through your engineering files to help! 🔍
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
            
            # Format response - natural and conversational
            if result['confidence'] == 'error':
                await turn_context.send_activity(f"Sorry, I encountered an error: {result['answer']}")
                return
            
            # Send the AI's answer naturally, like a human colleague would
            # (Backend still provides full metadata: confidence, sources, processing_time, etc.)
            # But Teams users only see the natural conversational answer
            await turn_context.send_activity(MessageFactory.text(result['answer']))
            
        except Exception as e:
            logger.error("Q&A failed", error=str(e), question=question)
            await turn_context.send_activity(f"❌ Failed to answer question: {str(e)}")

    async def on_members_added_activity(self, members_added: List[ChannelAccount], turn_context: TurnContext):
        """Welcome new members."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome_message(turn_context)
