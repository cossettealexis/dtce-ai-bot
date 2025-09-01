"""
Simple Smart RAG Handler - Fixes the "fucking dumb" problem
- Consistent results for equivalent queries
- Actual content extraction from documents
- Smart routing to correct folders
"""

import structlog
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

from .smart_query_router import SmartQueryRouter
from .semantic_search_new import SemanticSearchService

logger = structlog.get_logger(__name__)


class SmartRAGHandler:
    """Smart RAG Handler that gives consistent, useful answers."""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
        
        # Initialize the smart components
        self.query_router = SmartQueryRouter(openai_client)
        self.search_service = SemanticSearchService(search_client)
    
    async def get_answer(self, user_question: str) -> Dict[str, Any]:
        """
        Get a smart, consistent answer to the user's question.
        
        This is the main method that fixes the "fucking dumb" problem.
        """
        try:
            # Step 1: Route the query intelligently
            logger.info("Processing smart query", question=user_question[:100])
            routing_info = await self.query_router.route_query(user_question)
            
            # Step 2: Search using the router's guidance
            documents = await self.search_service.smart_search(routing_info)
            
            # Step 3: Generate a direct, useful answer
            if documents:
                answer = await self._generate_smart_answer(user_question, documents, routing_info)
            else:
                answer = self._generate_no_results_answer(user_question, routing_info)
            
            return {
                "answer": answer,
                "sources": documents[:5],  # Top 5 sources
                "intent": routing_info.get("intent"),
                "routing_info": routing_info
            }
            
        except Exception as e:
            logger.error("Smart RAG failed", error=str(e), question=user_question[:100])
            return {
                "answer": "I encountered an error processing your question. Please try rephrasing it or contact support.",
                "sources": [],
                "intent": "error",
                "routing_info": {}
            }
    
    async def _generate_smart_answer(self, question: str, documents: List[Dict], routing_info: Dict) -> str:
        """Generate a direct, useful answer based on the found documents."""
        
        intent = routing_info.get("intent", "general")
        
        # Extract content from top documents
        content_chunks = []
        source_links = []
        
        for i, doc in enumerate(documents[:3]):  # Use top 3 documents
            filename = doc.get('filename', 'Unknown Document')
            content = doc.get('content', '')
            
            # Take meaningful content chunk
            content_preview = content[:800] if content else "No content available"
            content_chunks.append(f"Source {i+1} ({filename}):\n{content_preview}")
            
            # Build SuiteFiles link
            blob_url = doc.get('blob_url', '')
            if blob_url and 'blob.core.windows.net' in blob_url:
                suite_link = blob_url.replace('https://dtceprojects.blob.core.windows.net/', 'https://dtceprojects.sharepoint.com/sites/Documents/')
                suite_link = suite_link.replace('dtce-documents/', 'Shared%20Documents/')
                source_links.append(f"📄 [{filename}]({suite_link})")
            else:
                source_links.append(f"📄 {filename}")
        
        # Build context for the AI
        context = "\n\n".join(content_chunks)
        
        # Create a direct, simple prompt
        prompt = f"""You are answering a question about DTCE company documents. Give a direct, helpful answer based on the provided content.

User Question: {question}

Query Intent: {intent}

Relevant Document Content:
{context}

Instructions:
1. Answer the question directly using the content from the documents
2. If it's a policy question, explain what the policy says
3. If it's a procedure question, explain the steps or process
4. Quote specific relevant parts from the documents
5. Be factual and helpful
6. If the documents don't fully answer the question, say what you can find and suggest contacting the relevant department

Keep your answer clear, direct, and useful. Don't be vague or generic."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1
            )
            
            ai_answer = response.choices[0].message.content.strip()
            
            # Add source links
            if source_links:
                sources_section = "\n\n**Sources:**\n" + "\n".join(source_links)
                final_answer = ai_answer + sources_section
            else:
                final_answer = ai_answer
            
            return final_answer
            
        except Exception as e:
            logger.error("Answer generation failed", error=str(e))
            return f"I found relevant documents but had trouble generating an answer. The documents that might help are: {', '.join(doc.get('filename', 'Unknown') for doc in documents[:3])}"
    
    def _generate_no_results_answer(self, question: str, routing_info: Dict) -> str:
        """Generate a helpful response when no documents are found."""
        
        intent = routing_info.get("intent", "general")
        
        if intent == "policy":
            return f"""I couldn't find specific documents answering your question about "{question}". 

For policy-related questions, I recommend:
1. Checking the company intranet or shared drives
2. Contacting HR directly
3. Speaking with your manager

The most common policies are usually found in the HR or company policy folders."""
            
        elif intent == "procedure":
            return f"""I couldn't find specific procedures for "{question}".

For procedural questions, try:
1. Checking the procedures or "How-to" folders
2. Looking for H2H (How to Handbooks) documents
3. Asking a colleague who has done this before
4. Contacting the relevant department"""
            
        elif intent == "standard":
            return f"""I couldn't find the specific engineering standard for "{question}".

For standards queries:
1. Check the NZ Standards folder
2. Visit the Standards New Zealand website
3. Contact the engineering team
4. Check if we have a subscription to the relevant standards"""
            
        elif intent == "project":
            return f"""I couldn't find information about the project "{question}".

For project-related questions:
1. Check the project folders by client or project number
2. Contact the project manager
3. Check the project database or tracking system"""
            
        elif intent == "client":
            return f"""I couldn't find client information for "{question}".

For client queries:
1. Check the CRM system
2. Look in client-specific project folders
3. Contact the account manager
4. Check the contacts database"""
            
        else:
            return f"""I couldn't find documents specifically answering "{question}".

Try:
1. Rephrasing your question
2. Using different keywords
3. Checking the company shared drives directly
4. Contacting the relevant department"""
