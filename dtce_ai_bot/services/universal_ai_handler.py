"""
Universal AI Assistant Handler - Simple ChatGPT-style with smart folder routing
"""

import logging
from typing import List, Dict, Any
import json

logger = logging.getLogger(__name__)

class UniversalAIHandler:
    """Universal AI handler that can answer anything, with smart DTCE folder routing."""
    
    def __init__(self, search_client, openai_client, model_name):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def answer_anything(self, question: str) -> Dict[str, Any]:
        """Answer any question like ChatGPT, with smart folder routing when needed."""
        try:
            # Step 1: Determine if we need to search DTCE folders
            search_strategy = await self._route_to_folder(question)
            
            # Step 2: Search specific folder if needed
            dtce_content = ""
            documents = []
            
            if search_strategy.get('search_dtce', False):
                logger.info(f"Searching DTCE folder: {search_strategy.get('folder')} for: {search_strategy.get('topic')}")
                dtce_content, documents = await self._search_dtce_folder(question, search_strategy['folder'])
            
            # Step 3: Generate ChatGPT-style response
            answer = await self._generate_universal_response(question, dtce_content, search_strategy)
            
            return {
                'answer': answer,
                'sources': documents[:5],
                'topic': search_strategy.get('topic', 'general'),
                'folder_searched': search_strategy.get('folder', 'none'),
                'documents_found': len(documents)
            }
            
        except Exception as e:
            logger.error(f"Universal AI handler failed: {str(e)}")
            # Fallback to basic response
            return await self._basic_fallback_response(question)
    
    async def _route_to_folder(self, question: str) -> Dict[str, Any]:
        """Use AI to determine which DTCE folder (if any) to search."""
        try:
            routing_prompt = f"""You are a smart router. Analyze this question and determine if it needs DTCE internal documents:

QUESTION: "{question}"

DTCE FOLDERS AVAILABLE:
- policy: Company policies, H&S procedures, IT policies (things employees must follow)
- procedures: How-to guides, technical procedures, best practices (H2H handbooks)  
- standards: NZ engineering standards, codes, technical specifications
- projects: Past DTCE projects, project history, client work
- clients: Client information, contact details, past client projects

OTHER: General knowledge questions (weather, news, general engineering theory, etc.)

Response JSON:
{{
    "topic": "brief description of question topic",
    "search_dtce": true/false,
    "folder": "policy|procedures|standards|projects|clients|none",
    "reasoning": "why this folder or general knowledge"
}}"""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You route questions to the right information source. Always respond with valid JSON."},
                    {"role": "user", "content": routing_prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Routing failed: {str(e)}")
            return {"topic": "general", "search_dtce": False, "folder": "none", "reasoning": "routing failed"}
    
    async def _search_dtce_folder(self, question: str, folder: str) -> tuple:
        """Search the specified DTCE folder."""
        try:
            # Map folders to search terms
            folder_terms = {
                'policy': 'policy OR safety OR h&s OR it',
                'procedures': 'procedure OR handbook OR h2h OR how to',
                'standards': 'nzs OR standard OR code OR engineering',
                'projects': 'project OR site OR construction',
                'clients': 'client OR contact'
            }
            
            search_terms = folder_terms.get(folder, '')
            if not search_terms:
                return "", []
            
            # Enhanced search query
            enhanced_query = f"{question} {search_terms}"
            
            # Search the index
            search_results = self.search_client.search(
                search_text=enhanced_query,
                top=8,
                include_total_count=True
            )
            
            # Format results
            content_parts = []
            documents = []
            
            for result in search_results:
                content_parts.append(result.get('content', ''))
                documents.append({
                    'title': result.get('title', 'Unknown'),
                    'source': result.get('source', 'Unknown'),
                    'score': result.get('@search.score', 0)
                })
            
            return "\n\n".join(content_parts[:3]), documents
            
        except Exception as e:
            logger.error(f"DTCE folder search failed: {str(e)}")
            return "", []
    
    async def _generate_universal_response(self, question: str, dtce_content: str, strategy: Dict) -> str:
        """Generate a universal ChatGPT-style response."""
        try:
            # Build the prompt
            if dtce_content:
                prompt = f"""You are DTCE AI Assistant - a helpful AI like ChatGPT, but with access to DTCE's internal documents.

USER QUESTION: "{question}"

TOPIC: {strategy.get('topic', 'General inquiry')}

RELEVANT DTCE INFORMATION:
{dtce_content[:2000]}

Instructions:
- Answer the question naturally and helpfully like ChatGPT
- Incorporate the DTCE information if relevant
- For general questions, use your knowledge
- Be conversational and practical
- Provide specific details when available

Answer:"""
            else:
                prompt = f"""You are DTCE AI Assistant - a helpful AI assistant like ChatGPT.

USER QUESTION: "{question}"

This appears to be a general question about: {strategy.get('topic', 'general topic')}

Answer this naturally and helpfully like ChatGPT would, using your general knowledge."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant like ChatGPT. Be natural, conversational, and helpful."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Response generation failed: {str(e)}")
            return f"I'd be happy to help with your question about {strategy.get('topic', 'this topic')}. Could you provide a bit more context or rephrase your question?"
    
    async def _basic_fallback_response(self, question: str) -> Dict[str, Any]:
        """Basic fallback when everything fails."""
        return {
            'answer': f"I'd be happy to help with your question: '{question}'. Could you provide a bit more context or try rephrasing?",
            'sources': [],
            'topic': 'general',
            'folder_searched': 'none',
            'documents_found': 0
        }
