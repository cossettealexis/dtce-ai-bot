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
from ..services.project_scoping import get_project_scoping_service

logger = structlog.get_logger(__name__)


class DTCETeamsBot(ActivityHandler):
    """Microsoft Teams bot for DTCE AI Assistant."""
    
    def __init__(self, conversation_state: ConversationState, user_state: UserState, 
                 search_client, qa_service: DocumentQAService):
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.search_client = search_client
        self.qa_service = qa_service
        self.project_scoping_service = get_project_scoping_service()

    def _format_teams_text(self, text: str) -> str:
        """Format text for Teams to ensure proper line breaks and readability."""
        if not text:
            return text
            
        # Fix common Teams formatting issues
        formatted = text
        
        # Ensure double line breaks between major sections
        formatted = formatted.replace('\n\n', '\n\n')  # Keep existing double breaks
        
        # Add extra line breaks before section headers (emoji + **text**)
        import re
        formatted = re.sub(r'(\n|^)(🔗|📝|⚠️|📋|✅|💡|🔍)\s*\*\*', r'\1\n\2 **', formatted)
        
        # Ensure bullet points have proper spacing
        formatted = re.sub(r'\n•\s*', '\n\n• ', formatted)
        
        # Add spacing before Requirements/Notes sections
        formatted = re.sub(r'\n(⚠️\s*\*\*Requirements)', r'\n\n\1', formatted)
        formatted = re.sub(r'\n(💡\s*\*\*)', r'\n\n\1', formatted)
        formatted = re.sub(r'\n(📝\s*\*\*)', r'\n\n\1', formatted)
        
        # Clean up any triple+ line breaks
        formatted = re.sub(r'\n{3,}', '\n\n', formatted)
        
        return formatted.strip()

    async def _send_teams_message(self, turn_context: TurnContext, text: str):
        """Send a message to Teams with proper formatting."""
        # Format the text for Teams
        formatted_text = self._format_teams_text(text)
        
        # Check if message is too long or has many sections
        if len(formatted_text) > 2000 or formatted_text.count('\n') > 15:
            # Split into smaller chunks at logical breaks
            chunks = self._split_teams_message(formatted_text)
            
            for chunk in chunks:
                await turn_context.send_activity(MessageFactory.text(chunk))
                # Small delay between chunks to ensure proper order
                await asyncio.sleep(0.1)
        else:
            # Send as single message
            await turn_context.send_activity(MessageFactory.text(formatted_text))
    
    def _split_teams_message(self, text: str) -> List[str]:
        """Split long messages into logical chunks for Teams."""
        chunks = []
        lines = text.split('\n')
        
        current_chunk = []
        current_length = 0
        
        for line in lines:
            # Check if this line starts a new major section
            if line.strip().startswith(('🔗', '📝', '⚠️', '📋')) and current_chunk and current_length > 500:
                # Start new chunk for this section
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_length = len(line)
            elif current_length + len(line) > 1800 and current_chunk:
                # Split at current point
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_length = len(line)
            else:
                current_chunk.append(line)
                current_length += len(line) + 1  # +1 for newline
        
        # Add remaining chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
            
        return chunks

    def _create_teams_message(self, text: str) -> MessageFactory:
        """Create a properly formatted Teams message that handles line breaks correctly."""
        # For Teams, we need to split long messages or use plain text format
        # Teams doesn't handle \n\n well in single messages
        message = MessageFactory.text(text)
        return message
        
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
        
        # Normalize command for parsing (syntax verified)
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
                return
        
        # Handle project scoping analysis commands
        if user_message.lower().startswith('/analyze ') or user_message.lower().startswith('analyze '):
            scoping_text = user_message.split(' ', 1)[1] if ' ' in user_message else ""
            if scoping_text:
                await self._handle_project_scoping_analysis(turn_context, scoping_text)
                return
        
        # Check for project scoping keywords in message
        scoping_keywords = [
            'please review this request', 'rfp', 'request for proposal', 
            'similar past projects', 'design philosophy', 'marquee', 
            'certification', 'quote for ps1', 'similar projects'
        ]
        
        if any(keyword in user_message.lower() for keyword in scoping_keywords):
            await self._handle_project_scoping_analysis(turn_context, user_message)
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
            
            message = MessageFactory.text(response)
            message.text_format = "markdown"
            await turn_context.send_activity(message)
        else:
            error_message = MessageFactory.text("❌ No supported file types found. Please upload PDF, Word, Excel, PowerPoint, CAD, or image files.")
            error_message.text_format = "markdown"
            await turn_context.send_activity(error_message)

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
        ack_message = MessageFactory.text(ack_response)
        ack_message.text_format = "markdown"
        await turn_context.send_activity(ack_message)
        
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

I can help you find information from engineering documents, analyze project requests, and provide design guidance based on our past experience.

**Available Commands:**
• `help` or `Hello` - Show this help message
• `search [query]` - Search documents (e.g., `search bridge calculations`)
• `ask [question]` - Ask questions about documents (e.g., `ask What are the seismic requirements?`)
• `analyze [project request]` - Analyze project scoping requests
• `projects` - List available projects
• `health` - Check system status

**📎 File Upload Support:**
• **PDF** - Reports, RFPs, specifications, scoping documents
• **Word/Excel/PowerPoint** - Documents, spreadsheets, presentations
• **CAD Files** - .dwg, .dxf drawings
• **Images** - .png, .jpg engineering drawings
• **Text/Email** - .txt, .md, .msg files

**🎯 Project Scoping & Analysis:**
I can analyze client requests and RFPs to:
• Find similar past projects for reference
• Identify potential issues and solutions
• Generate design philosophy recommendations
• Provide compliance guidance (PS1, building consent)
• Warn about risks based on past experience

**Quick Examples:**
• "What projects do we have?"
• "Show me structural calculations for project 222"
• "What were the conclusions in the final report?"
• "Please review this request for our services from our client..."
• Upload an RFP → "Please analyze this RFP and find similar past projects"
• Upload drawings → "Review these structural drawings"
• "Hi" - Get this welcome message

        Just type your question, paste a client request, or upload documents and I'll search through your engineering files to help! 🔍
        """
        
        await self._send_teams_message(turn_context, welcome_text.strip())

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
                
            status_message = MessageFactory.text(status_text)
            status_message.text_format = "markdown"
            await turn_context.send_activity(status_message)
            
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
                
            projects_message = MessageFactory.text(projects_text)
            projects_message.text_format = "markdown"
            await turn_context.send_activity(projects_message)
            
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
            
            # Clean the answer to remove any sources information that might be embedded
            answer = result['answer']
            
            # Remove sources section if it exists in the answer
            import re
            answer = re.sub(r'📄\s*Sources:.*?(?=\n\n|\Z)', '', answer, flags=re.DOTALL | re.IGNORECASE)
            
            # Use the new Teams message sending method
            await self._send_teams_message(turn_context, answer)
            
        except Exception as e:
            logger.error("Q&A failed", error=str(e), question=question)
            await turn_context.send_activity(f"❌ Failed to answer question: {str(e)}")

    async def _handle_project_scoping_analysis(self, turn_context: TurnContext, scoping_text: str):
        """Handle project scoping analysis requests."""
        try:
            logger.info("Processing project scoping analysis", text_length=len(scoping_text))
            
            # Send acknowledgment
            status_message = MessageFactory.text("🔍 **Analyzing your project request...**\n\n" +
                                               "• Extracting project characteristics\n" +
                                               "• Finding similar past projects\n" +
                                               "• Analyzing potential issues\n" +
                                               "• Generating design recommendations\n\n" +
                                               "⏳ This may take a moment...")
            status_message.text_format = "markdown"
            await turn_context.send_activity(status_message)
            
            # Perform the analysis using the existing project scoping service
            analysis_result = await self.project_scoping_service.analyze_project_request(scoping_text)
            
            if 'error' in analysis_result:
                await turn_context.send_activity(f"❌ Analysis failed: {analysis_result.get('error', 'Unknown error')}")
                return
            
            # Format and send the comprehensive analysis
            response = self._format_project_scoping_response(analysis_result)
            response_message = MessageFactory.text(response)
            response_message.text_format = "markdown"
            await turn_context.send_activity(response_message)
            
        except Exception as e:
            logger.error("Project scoping analysis failed", error=str(e))
            await turn_context.send_activity(f"❌ Failed to analyze project request: {str(e)}")

    def _format_project_scoping_response(self, analysis_result: dict) -> str:
        """Format the project scoping analysis result for Teams display."""
        try:
            response = "# 📋 Project Analysis Report\n\n"
            
            # Add the main analysis (from the project scoping service)
            if analysis_result.get('analysis'):
                response += analysis_result['analysis']
                response += "\n\n"
            
            # Add characteristics summary if available
            characteristics = analysis_result.get('characteristics', {})
            if characteristics and not characteristics.get('error'):
                response += "## 📊 Project Characteristics\n\n"
                
                if characteristics.get('project_type'):
                    response += f"**Type:** {characteristics['project_type']}\n"
                if characteristics.get('dimensions'):
                    response += f"**Dimensions:** {characteristics['dimensions']}\n"
                if characteristics.get('location'):
                    response += f"**Location:** {characteristics['location']}\n"
                if characteristics.get('loads'):
                    response += f"**Loads:** {characteristics['loads']}\n"
                if characteristics.get('compliance'):
                    response += f"**Compliance:** {characteristics['compliance']}\n"
                if characteristics.get('materials'):
                    response += f"**Materials:** {characteristics['materials']}\n"
                
                response += "\n"
            
            # Add similar projects summary
            similar_projects = analysis_result.get('similar_projects', [])
            if similar_projects:
                response += f"## 🔍 Found {len(similar_projects)} Similar Projects\n\n"
                for i, project in enumerate(similar_projects[:3], 1):  # Top 3
                    title = project.get('title', 'Unknown Project')
                    project_id = project.get('project', 'N/A')
                    similarity = project.get('similarity_score', 0)
                    response += f"**{i}.** {title} (Project {project_id}) - {similarity:.1%} similarity\n"
                response += "\n"
            
            # Add footer
            response += "---\n"
            response += "*This analysis is based on our project database and engineering experience. " \
                       "For detailed quotes and technical specifications, please provide additional project details.*"
            
            return response
            
        except Exception as e:
            logger.error("Failed to format project scoping response", error=str(e))
            return f"Analysis completed but formatting failed: {str(e)}"

    async def on_members_added_activity(self, members_added: List[ChannelAccount], turn_context: TurnContext):
        """Welcome new members."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome_message(turn_context)
