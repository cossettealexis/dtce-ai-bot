"""
Universal AI Handler - Orchestrates the complete RAG pipeline
"""

from typing import Dict, List, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

# Import the services we just created
from .semantic_search import SemanticSearchService
from .intent_classifier import IntentClassifier
from .folder_structure_service import FolderStructureService
from .query_normalizer import QueryNormalizer
from .google_docs_service import GoogleDocsService
from .project_context_service import ProjectContextService
from .prompt_builder import PromptBuilder
from .document_formatter import DocumentFormatter
from .specialized_search_service import SpecializedSearchService

logger = structlog.get_logger(__name__)


class UniversalAIHandler:
    """
    Universal AI Handler that orchestrates the complete RAG pipeline.
    Implements the comprehensive RAG system as described in the requirements.
    
    This is the main orchestrator that:
    1. Classifies user intent
    2. Normalizes queries
    3. Executes specialized search
    4. Formats documents optimally
    5. Builds category-specific prompts
    6. Generates comprehensive responses
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        
        # Initialize all RAG services
        self.intent_classifier = IntentClassifier(openai_client, model_name)
        self.semantic_search = SemanticSearchService(search_client, openai_client, model_name)
        self.folder_structure = FolderStructureService()
        self.query_normalizer = QueryNormalizer(openai_client, model_name)
        self.google_docs = GoogleDocsService()
        self.project_context = ProjectContextService()
        self.prompt_builder = PromptBuilder()
        self.document_formatter = DocumentFormatter()
        self.specialized_search = SpecializedSearchService(search_client, openai_client, model_name)
    
    async def process_comprehensive_query(
        self, 
        question: str, 
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Process a query through the complete RAG pipeline.
        
        This implements the full RAG system:
        1. Data Preparation (query normalization)
        2. Retrieval (hybrid search with intent routing)
        3. Generation (category-specific prompt engineering)
        
        Args:
            question: User's question
            conversation_history: Previous conversation context
            
        Returns:
            Complete response with answer, sources, and metadata
        """
        try:
            logger.info("Starting comprehensive RAG processing", question=question)
            
            # STEP 1: Intent Classification and Query Analysis
            intent_result = await self.intent_classifier.classify_query(question)
            category = intent_result['category']
            search_strategy = intent_result['search_strategy']
            
            logger.info("Intent classified", category=category, confidence=intent_result['confidence'])
            
            # STEP 2: Query Normalization and Enhancement
            normalized_query = await self.query_normalizer.normalize_query(question)
            enhanced_question = normalized_query['final_query']
            
            # STEP 3: Project Context Extraction
            project_context = self.project_context.extract_project_context(question)
            if project_context['has_project_reference']:
                enhanced_question = self.project_context.enhance_query_with_project_context(
                    enhanced_question, project_context
                )
            
            # STEP 4: Multi-Source Retrieval
            if search_strategy.get('needs_dtce_search', True):
                # Execute specialized search based on category
                documents = await self.specialized_search.execute_specialized_search(
                    enhanced_question, search_strategy
                )
                
                # Apply folder-based filtering if needed
                if search_strategy.get('search_folders'):
                    documents = self.folder_structure.filter_documents_by_relevance(
                        documents, category, max_results=10
                    )
                
                # Get Google Docs knowledge base content
                knowledge_content = self.google_docs.get_contextual_knowledge(question, category)
                
            else:
                # General engineering - no document search needed
                documents = []
                knowledge_content = ""
            
            # STEP 5: Document Formatting and Optimization
            if documents:
                formatted_content = self.document_formatter.format_documents_for_rag(
                    documents, question, category, include_metadata=True
                )
            else:
                formatted_content = "No specific DTCE documents found."
            
            # Add knowledge base content
            if knowledge_content:
                formatted_content += f"\n\n**DTCE Knowledge Base:**\n{knowledge_content}"
            
            # STEP 6: Prompt Engineering and Generation
            additional_context = {
                'project_info': project_context,
                'technical_terms': normalized_query.get('technical_terms', []),
                'confidence_level': intent_result['confidence']
            }
            
            prompts = self.prompt_builder.build_prompt(
                category=category,
                question=question,
                retrieved_content=formatted_content,
                additional_context=additional_context
            )
            
            # Optimize prompts for token limits
            optimized_prompts = self.prompt_builder.optimize_for_token_limit(prompts, max_tokens=3500)
            
            # STEP 7: LLM Generation
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": optimized_prompts['system']},
                    {"role": "user", "content": optimized_prompts['user']}
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=2500,
                top_p=0.9
            )
            
            answer = response.choices[0].message.content
            
            # STEP 8: Post-processing and Source Formatting
            sources = self._format_sources(documents) if documents else []
            
            # Add SuiteFiles links if not already included
            if documents and "SuiteFiles" not in answer:
                answer = self._add_suitefiles_links(answer, documents)
            
            # STEP 9: Compile Final Response
            final_response = {
                'answer': answer,
                'sources': sources,
                'confidence': self._calculate_overall_confidence(intent_result, documents),
                'documents_searched': len(documents),
                'rag_type': 'comprehensive_rag',
                'category': category,
                'search_strategy': search_strategy,
                'query_enhancements': {
                    'normalized': normalized_query['final_query'],
                    'technical_terms': normalized_query.get('technical_terms', []),
                    'project_context': project_context
                },
                'response_metadata': {
                    'model_used': self.model_name,
                    'search_method': 'specialized_hybrid',
                    'prompt_category': category
                }
            }
            
            logger.info("Comprehensive RAG processing completed", 
                       category=category, 
                       documents_found=len(documents),
                       confidence=final_response['confidence'])
            
            return final_response
            
        except Exception as e:
            logger.error("Comprehensive RAG processing failed", error=str(e))
            return await self._handle_processing_error(question, str(e))
    
    def _format_sources(self, documents: List[Dict]) -> List[Dict]:
        """
        Format document sources for the response.
        """
        sources = []
        
        for doc in documents[:5]:  # Limit to top 5 sources
            source = {
                'filename': doc.get('filename', 'Unknown'),
                'title': doc.get('filename', 'Unknown'),
                'folder': self._extract_folder_path(doc.get('blob_url', '')),
                'url': doc.get('blob_url', ''),
                'relevance_score': doc.get('@search.score', 0)
            }
            
            # Add project information if available
            project_info = self._extract_project_from_blob_url(doc.get('blob_url', ''))
            if project_info:
                source['project'] = project_info
            
            sources.append(source)
        
        return sources
    
    def _extract_folder_path(self, blob_url: str) -> str:
        """
        Extract meaningful folder path from blob URL.
        """
        if not blob_url:
            return ""
        
        # Extract path after dtce-documents
        if '/dtce-documents/' in blob_url:
            path_part = blob_url.split('/dtce-documents/')[1]
            # Remove filename and get folder path
            folder_path = '/'.join(path_part.split('/')[:-1])
            return folder_path
        
        return ""
    
    def _extract_project_from_blob_url(self, blob_url: str) -> Optional[str]:
        """
        Extract project number from blob URL if it's a project document.
        """
        import re
        project_match = re.search(r'/Projects/\d{3}/(\d{6})/', blob_url, re.IGNORECASE)
        if project_match:
            return project_match.group(1)
        return None
    
    def _add_suitefiles_links(self, answer: str, documents: List[Dict]) -> str:
        """
        Add SuiteFiles links to the answer if not already present.
        """
        if not documents:
            return answer
        
        # Create sources section
        sources_section = "\n\n## Sources\n"
        
        for doc in documents[:5]:
            filename = doc.get('filename', 'Unknown')
            blob_url = doc.get('blob_url', '')
            
            if blob_url:
                # Convert to SuiteFiles URL (simplified)
                if '/dtce-documents/' in blob_url:
                    path_part = blob_url.split('/dtce-documents/')[1]
                    from urllib.parse import quote
                    encoded_path = quote(path_part, safe='/')
                    suitefiles_url = f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#{encoded_path}"
                    sources_section += f"- [{filename}]({suitefiles_url})\n"
                else:
                    sources_section += f"- {filename}\n"
            else:
                sources_section += f"- {filename}\n"
        
        return answer + sources_section
    
    def _calculate_overall_confidence(self, intent_result: Dict, documents: List[Dict]) -> str:
        """
        Calculate overall confidence in the response.
        """
        intent_confidence = intent_result.get('confidence', 0.5)
        doc_count = len(documents)
        
        if intent_confidence > 0.8 and doc_count >= 3:
            return 'high'
        elif intent_confidence > 0.6 and doc_count >= 1:
            return 'medium'
        elif doc_count == 0:
            return 'general_knowledge'
        else:
            return 'low'
    
    async def _handle_processing_error(self, question: str, error: str) -> Dict[str, Any]:
        """
        Handle errors gracefully with fallback response.
        """
        fallback_prompts = self.prompt_builder.build_fallback_prompt(question, error)
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": fallback_prompts['system']},
                    {"role": "user", "content": fallback_prompts['user']}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            
        except Exception as e:
            logger.error("Fallback response generation failed", error=str(e))
            answer = f"""I apologize, but I encountered an error while processing your question: "{question}". 

Please try rephrasing your question or contact support if the issue persists. 

For immediate assistance, you can:
1. Check SuiteFiles directly for relevant documents
2. Consult with colleagues or supervisors
3. Review relevant NZ Standards or procedures"""
        
        return {
            'answer': answer,
            'sources': [],
            'confidence': 'error',
            'documents_searched': 0,
            'rag_type': 'error_fallback',
            'error_details': error
        }
