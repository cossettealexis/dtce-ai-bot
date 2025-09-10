"""
RAG (Retrieval-Augmented Generation) Handler for DTCE AI Bot
ENHANCED SEMANTIC SEARCH with Intent Recognition
"""

import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
from .semantic_search import SemanticSearchService
from .folder_structure_service import FolderStructureService
from .query_normalizer import QueryNormalizer
from ..utils.suitefiles_urls import suitefiles_converter

logger = structlog.get_logger(__name__)


from .universal_ai_handler import UniversalAIHandler

class RAGHandler:
    """Handles RAG processing with enhanced semantic search and intent recognition."""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        # Initialize the new universal AI handler  
        self.ai_handler = UniversalAIHandler(search_client, openai_client, model_name)
        # Keep existing services for backward compatibility
        self.semantic_search = SemanticSearchService(search_client, openai_client, model_name)
        self.folder_structure = FolderStructureService()
        # Initialize query normalizer for better semantic search consistency
        self.query_normalizer = QueryNormalizer(openai_client, model_name)

    def _force_suitefiles_links(self, answer: str, documents: list) -> str:
        """Force SuiteFiles links to be included in the response if documents are available."""
        if not documents:
            return answer
            
        # Check if SuiteFiles links are already included
        if "SuiteFiles" in answer:
            return answer
            
        logger.warning("Forcing SuiteFiles links inclusion - AI didn't follow instructions")
        
        # Build the Sources section manually
        sources_section = "\n\n**Sources:**"
        links_added = 0
        
        for doc in documents[:3]:  # Limit to top 3 for readability
            filename = doc.get('filename', 'Unknown Document')
            blob_url = self._get_blob_url_from_doc(doc)
            suitefiles_link = suitefiles_converter.get_safe_suitefiles_url(blob_url)
            
            if suitefiles_link:
                # Clean filename for display
                display_name = filename.replace('.pdf', '').replace('_', ' ').title()
                # Use markdown link format to hide the ugly URL
                sources_section += f"\n- [{display_name}]({suitefiles_link})"
                links_added += 1
        
        # Only append if we actually have valid links
        if links_added > 0:
            return answer + sources_section
        else:
            logger.warning("No valid SuiteFiles links found in documents")
            return answer

    async def process_question(self, question: str) -> Dict[str, Any]:
        """Universal AI assistant that can answer anything like ChatGPT + smart DTCE routing."""
        try:
            logger.info(f"Universal AI processing: {question}")
            
            # Use the new universal AI assistant
            result = await self.universal_ai_assistant(question)
            
            logger.info(f"Response type: {result.get('rag_type')}, Folder: {result.get('folder_searched', 'none')}, Docs: {result.get('documents_searched', 0)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Universal AI processing failed: {str(e)}")
            # Even error handling uses AI instead of static messages
            return await self._handle_ai_error(question, str(e))
    
    async def process_rag_query(self, question: str, project_filter: Optional[str] = None, conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        CONSISTENT INTELLIGENT SEARCH WITH NORMALIZED QUERIES:
        
        1. Normalize similar questions to search for same documents consistently
        2. Use consistent document ranking and selection 
        3. Generate comprehensive responses from same source documents
        4. Ensure same questions always get same foundational documents
        """
        try:
            logger.info("Processing question with consistent search approach", question=question)
            
            # STEP 0: Check if this is a conversational query that doesn't need document search
            is_conversational = await self._is_conversational_query(question, conversation_history)
            
            if is_conversational:
                logger.info("Detected conversational query - using context instead of search")
                return await self._handle_conversational_query(question, conversation_history)
            
            # STEP 1: Normalize query for CONSISTENT search results - similar questions should find same documents
            logger.info("Detected informational query - proceeding with consistent document search")
            
            # Create consistent search terms for similar questions
            normalized_query = self._create_consistent_search_query(question)
            
            logger.info("Query normalized for consistency", 
                       original=question,
                       normalized=normalized_query)
            
            # STEP 2: Use intelligent semantic search with consistent query
            documents = await self.semantic_search.search_documents(normalized_query, project_filter)
            
            logger.info("Consistent search results", 
                       total_documents=len(documents),
                       sample_filenames=[doc.get('filename', 'Unknown') for doc in documents[:3]])
            
            # STEP 3: Generate response with retrieved documents and category context
            if documents:
                # Get category information from search service
                category_context = self._determine_response_context(documents, question)
                retrieved_content = self._format_documents_with_folder_context(documents, category_context)
                
                # Use the complete intelligent prompt system
                result = await self._process_rag_with_full_prompt(question, retrieved_content, documents)
                
                result.update({
                    'rag_type': 'comprehensive_conversational_rag',
                    'search_method': 'consistent_semantic_search',
                    'response_style': 'chatgpt_like_conversation',
                    'query_normalization': {
                        'original_query': question,
                        'normalized_query': normalized_query,
                        'method': 'consistent_search_terms'
                    }
                })
                
                return result
            else:
                # No documents found - provide general response
                result = await self._handle_no_documents_found(question)
                result['query_normalization'] = {
                    'original_query': question,
                    'normalized_query': normalized_query,
                    'method': 'consistent_search_terms'
                }
                return result
                
        except Exception as e:
            logger.error("Folder-aware RAG processing failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while processing your question: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'rag_type': 'error'
            }
    
    def _determine_response_context(self, documents: List[Dict], question: str) -> Dict[str, Any]:
        """Determine the response context based on found documents and question."""
        
        # Analyze document folders to understand the search category
        folder_analysis = {}
        for doc in documents[:5]:  # Analyze top 5 documents
            folder = doc.get('folder', '').lower()
            filename = doc.get('filename', '').lower()
            
            # Categorize based on folder and filename patterns
            if any(term in folder or term in filename for term in ['policy', 'h&s', 'health', 'safety', 'hr']):
                folder_analysis['policy'] = folder_analysis.get('policy', 0) + 1
            elif any(term in folder or term in filename for term in ['procedure', 'h2h', 'handbook', 'workflow']):
                folder_analysis['procedures'] = folder_analysis.get('procedures', 0) + 1
            elif any(term in folder or term in filename for term in ['standard', 'nzs', 'code', 'specification']):
                folder_analysis['standards'] = folder_analysis.get('standards', 0) + 1
            elif any(year in folder for year in ['225', '224', '223', '222', '221', '220', '219']):
                folder_analysis['projects'] = folder_analysis.get('projects', 0) + 1
            elif any(term in folder or term in filename for term in ['client', 'contact', 'nzta', 'council']):
                folder_analysis['clients'] = folder_analysis.get('clients', 0) + 1
        
        # Determine primary category
        if folder_analysis:
            primary_category = max(folder_analysis.keys(), key=lambda k: folder_analysis[k])
        else:
            primary_category = 'general'
        
        return {
            'query_type': primary_category,
            'folder_distribution': folder_analysis,
            'category_confidence': max(folder_analysis.values()) / max(len(documents[:5]), 1) if folder_analysis else 0.0
        }
    
    async def _search_documents_with_folder_context(
        self, 
        query: str, 
        project_filter: Optional[str], 
        folder_context: Dict[str, Any]
    ) -> List[Dict]:
        """Search documents with folder structure awareness (GPT handles folder prioritization)."""
        
        # Start with semantic search (no folder restrictions - GPT will handle prioritization)
        documents = await self._search_documents(query, project_filter, use_semantic=True)
        
        # If semantic search doesn't find enough results, try keyword search
        if len(documents) < 5:
            logger.info("Enhancing folder-aware results with keyword search")
            search_words = [word.strip() for word in query.split() if len(word.strip()) > 2]
            keyword_query = ' OR '.join(search_words)
            keyword_docs = await self._search_documents(keyword_query, project_filter, use_semantic=False)
            
            # Combine and deduplicate results
            seen_ids = {doc.get('id') for doc in documents}
            for doc in keyword_docs:
                if doc.get('id') not in seen_ids:
                    documents.append(doc)
                    seen_ids.add(doc.get('id'))
        
        # Filter out documents from excluded folders (with superseded option)
        filtered_documents = []
        excluded_terms = ['archive', 'obsolete', 'old', 'backup', 'temp', 'draft', 'trash']
        superseded_terms = ['superseded', 'superceded']
        
        for doc in documents:
            blob_name = doc.get('blob_name', '') or doc.get('filename', '')
            
            # Check if document is from superseded folder
            is_superseded = any(term in blob_name.lower() for term in superseded_terms)
            is_excluded = any(term in blob_name.lower() for term in excluded_terms)
            
            # Include superseded documents if user specifically asks for them
            include_superseded = any(term in query.lower() for term in ['superseded', 'superceded', 'old version', 'previous version', 'historical'])
            
            should_exclude = is_excluded or (is_superseded and not include_superseded)
            
            if not should_exclude:
                filtered_documents.append(doc)
            else:
                reason = "superseded" if is_superseded else "archive/excluded"
                logger.debug("Excluded document", blob_name=blob_name, reason=reason)
        
        return filtered_documents
    
    def _format_documents_simple(self, documents: List[Dict]) -> str:
        """Format documents with full content for comprehensive RAG processing."""
        if not documents:
            return "No documents found."

        formatted_docs = []
        
        for i, doc in enumerate(documents[:8], 1):  # Top 8 most relevant
            filename = doc.get('filename', 'Unknown')
            content = doc.get('content', '')
            
            # Get SuiteFiles link
            blob_url = self._get_blob_url_from_doc(doc)
            suitefiles_link = suitefiles_converter.get_safe_suitefiles_url(blob_url)
            
            # USE FULL CONTENT - NO TRUNCATION AT ALL
            formatted_content = content  # Complete document content without any limits
            
            # Format with clear structure
            doc_info = f"""=== DOCUMENT {i}: {filename} ==="""
            
            if suitefiles_link:
                doc_info += f"""
SuiteFiles Link: {suitefiles_link}"""
            
            doc_info += f"""

FULL CONTENT:
{formatted_content}

=== END DOCUMENT {i} ==="""
            
            formatted_docs.append(doc_info)
        
        return "\n\n".join(formatted_docs)
    
    def _format_documents_with_folder_context(self, documents: List[Dict], folder_context: Dict[str, Any]) -> str:
        """Format documents with full content for comprehensive RAG processing."""
        formatted_docs = []
        
        for i, doc in enumerate(documents[:8], 1):  # Top 8 most relevant documents
            filename = doc.get('filename', 'Unknown')
            content = doc.get('content', '')
            blob_name = doc.get('blob_name', '')
            
            # Extract folder information
            folder_info = self._extract_folder_info(blob_name)
            
            # Get SuiteFiles link
            blob_url = self._get_blob_url_from_doc(doc)
            suitefiles_link = suitefiles_converter.get_safe_suitefiles_url(blob_url)
            
            # Extract project info using our consistent method
            extracted_project = self._extract_project_name_from_blob_url(blob_url)
            
            # USE FULL CONTENT - NO TRUNCATION AT ALL
            formatted_content = content  # Complete document content without any limits
            # No truncation - let AI see everything
            
            # Format document with comprehensive information
            doc_info = f"""=== DOCUMENT {i}: {filename} ===
Location: {folder_info['folder_path']}"""
            
            if extracted_project:
                doc_info += f"""
Project: {extracted_project}"""
            
            if suitefiles_link:
                doc_info += f"""
SuiteFiles Link: {suitefiles_link}"""
            
            doc_info += f"""

FULL CONTENT:
{formatted_content}

=== END DOCUMENT {i} ==="""
            
            formatted_docs.append(doc_info)
        
        return "\n\n".join(formatted_docs)
    
    def _extract_folder_info(self, blob_name: str) -> Dict[str, str]:
        """Extract folder information from blob name."""
        if not blob_name:
            return {"folder_path": "Unknown", "year": "", "project": ""}
        
        # Parse blob name like "suitefiles/Projects/225/225001/04 Reports/filename.pdf"
        parts = blob_name.split('/')
        
        folder_path = "/".join(parts[:-1]) if len(parts) > 1 else blob_name
        year = ""
        project = ""
        
        # Only extract project info if this is actually in a Projects folder
        if 'Projects' in parts or 'projects' in parts:
            # Try to extract year from folder code (simple mapping)
            year_mappings = {
                "225": "2025", "224": "2024", "223": "2023", "222": "2022", 
                "221": "2021", "220": "2020", "219": "2019"
            }
            
            for part in parts:
                if part in year_mappings:
                    year = year_mappings[part]
                    break
            
            # Try to extract project number
            for part in parts:
                if re.match(r'^\d{6}$', part):  # 6-digit project number
                    project = part
                    break
        
        return {
            "folder_path": folder_path,
            "year": year,
            "project": project
        }
    
    def _get_blob_url_from_doc(self, doc: Dict) -> str:
        """Extract blob URL from document with multiple fallbacks."""
        # Debug: Log available fields
        logger.info("Document fields available", fields=list(doc.keys()))
        
        # Check all possible field names for blob URL
        blob_url = (doc.get('blob_url') or 
                   doc.get('blobUrl') or 
                   doc.get('url') or 
                   doc.get('source_url') or 
                   doc.get('sourceUrl') or
                   doc.get('metadata_storage_path') or 
                   doc.get('metadata_storage_name') or
                   doc.get('sourcePage') or
                   doc.get('source') or
                   doc.get('path') or
                   doc.get('file_path') or
                   doc.get('filepath') or
                   doc.get('document_url') or
                   doc.get('documentUrl') or
                   doc.get('@search.score') and doc.get('id') or  # Sometimes ID contains the path
                   '')
        
        # If still no URL found, try to construct from filename/folder info
        if not blob_url:
            # Try to get filename and folder to construct URL
            filename = doc.get('filename', '') or doc.get('name', '') or doc.get('title', '')
            folder = doc.get('folder', '') or doc.get('directory', '') or doc.get('path', '')
            
            if filename:
                # Construct likely blob URL pattern
                if folder:
                    blob_url = f"https://dtcestorage.blob.core.windows.net/dtce-documents/{folder}/{filename}"
                else:
                    blob_url = f"https://dtcestorage.blob.core.windows.net/dtce-documents/{filename}"
                logger.info("Constructed blob URL from filename/folder", constructed_url=blob_url)
        
        if not blob_url:
            logger.warning("No blob URL found in document", document_fields=list(doc.keys()), 
                          sample_values={k: str(v)[:100] for k, v in list(doc.items())[:5]})
        else:
            logger.info("Found blob URL", blob_url=blob_url)
            
        return blob_url
    
    async def _handle_no_documents_found(self, question: str) -> Dict[str, Any]:
        """Handle cases where no documents are found - provide intelligent fallback."""
        logger.info("No documents found, providing general response", question=question)
        
        # Use GPT knowledge fallback with advisory engineering guidance
        try:
            fallback_prompt = f"""You are DTCE AI Assistant, a senior engineering advisor. A user asked: "{question}"

I searched our DTCE document database but couldn't find specific project documents that directly answer this question.

As a senior engineering advisor, please provide a comprehensive response that:

**Professional Assessment**: Acknowledge the document search limitation while providing expert engineering guidance
**General Engineering Guidelines**: Apply relevant engineering principles, NZ Standards, and best practices to the question
**Risk Considerations**: Identify potential technical risks, compliance issues, or common pitfalls in this area
**Advisory Recommendations**: Suggest practical next steps, verification approaches, and professional guidance
**Resource Guidance**: Recommend where to find additional information (standards, industry resources, internal DTCE expertise)
**Common Issues & Warnings**: Identify typical problems in this area and how to avoid them
**Best Practice Integration**: Combine general engineering knowledge with NZ Standards and industry practices

**Engineering Advisory Approach**:
- Draw on general structural/engineering knowledge where applicable
- Reference relevant NZ Standards (NZS 3101, NZS 3404, NZS 1170, etc.) with specific clauses if known
- Provide risk mitigation strategies and common pitfall warnings
- Suggest verification, quality assurance, and peer review approaches
- Include general industry best practices and lessons learned from the field
- Offer practical guidance that prevents common engineering mistakes
- Recommend decision-making frameworks and professional approaches

**Response Structure**:
- Direct answer to the question using general engineering knowledge
- General guidelines and best practices that apply
- Risk warnings and common issues to avoid
- Professional recommendations and next steps
- Resource guidance for further information

Keep the response professional, comprehensive, and advisory like guidance from an experienced consulting engineer who has seen many projects."""
            
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are DTCE AI Assistant, a senior engineering advisor that provides expert guidance even when specific documents aren't available. You combine general engineering knowledge, NZ Standards expertise, risk assessment, and professional recommendations to help DTCE employees with engineering challenges."
                    },
                    {"role": "user", "content": fallback_prompt}
                ],
                temperature=0.1,  # Consistent low temperature for deterministic responses
                max_tokens=2000  # Increased for comprehensive advisory guidance
            )
            
            answer = response.choices[0].message.content
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'no_documents_fallback',
                'search_method': 'enhanced_semantic_search'
            }
            
        except Exception as e:
            logger.error("Fallback response generation failed", error=str(e))
            return {
                'answer': f'I couldn\'t find specific documents related to "{question}" in our database. Please try rephrasing your question or using different keywords.',
                'sources': [],
                'confidence': 'low', 
                'documents_searched': 0,
                'rag_type': 'error_fallback'
            }

    async def _generate_fallback_response(self, prompt: str) -> str:
        """Generate comprehensive fallback response using GPT's general knowledge."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": """You are an expert structural engineering AI assistant for DTCE (a New Zealand structural engineering consultancy). 

When providing fallback responses:
- Be comprehensive and professional
- Focus on New Zealand building codes, standards, and practices
- Provide practical, actionable guidance
- Always acknowledge when information is general vs. DTCE-specific
- Include relevant NZ Standards (NZS) when applicable
- Consider local conditions and requirements
- Be helpful while encouraging users to verify with DTCE's specific procedures

Your responses should be thorough and educational, providing real value even when specific documents aren't available."""
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,  # Increased for more comprehensive responses
                temperature=0.1  # Consistent low temperature for deterministic responses
            )
            
            fallback_answer = response.choices[0].message.content.strip()
            
            # Add disclaimer to make it clear this is general knowledge
            disclaimer = "\n\n---\n**Note:** This response is based on general engineering knowledge and industry best practices. For DTCE-specific procedures, policies, or project information, please check SuiteFiles or consult with your colleagues and supervisors."
            
            return fallback_answer + disclaimer
            
        except Exception as e:
            logger.error("GPT fallback response generation failed", error=str(e))
            return """I'm having trouble accessing my general knowledge at the moment. Here are some general suggestions:

1. Check SuiteFiles for relevant documents in the appropriate folders
2. Consult with colleagues or supervisors who might have experience with this topic
3. Review relevant NZ Standards or building codes
4. Contact the appropriate department for policy or procedure questions

Please try rephrasing your question or contact support if the issue persists."""

    async def _search_index_with_context(self, search_query: str, project_filter: Optional[str] = None) -> str:
        """Enhanced search that includes project and document context."""
        try:
            # First search for documents
            documents = await self._search_documents(search_query, project_filter)
            
            if documents:
                index_results = []
                for doc in documents[:5]:  # Limit to top 5 results
                    filename = doc.get('filename', 'Unknown')
                    content = doc.get('content', '')
                    project_name = doc.get('project_name', '')
                    blob_url = doc.get('blob_url', '')
                    blob_name = doc.get('blob_name', '')
                    
                    # Convert blob URL to SuiteFiles URL
                    suitefiles_link = self._convert_to_suitefiles_url(blob_url)
                    
                    # Extract project info using the same logic as _format_sources
                    extracted_project = self._extract_project_name_from_blob_url(blob_url)
                    
                    if extracted_project:
                        # This is a project document - show project info
                        doc_result = f"""DOCUMENT FOUND:
- **File Name:** {filename}
- **Project:** {extracted_project}
- **SuiteFiles Link:** {suitefiles_link}
- **Full Content:** {content}

"""
                    else:
                        # Don't show project info for non-project documents
                        doc_result = f"""DOCUMENT FOUND:
- **File Name:** {filename}
- **SuiteFiles Link:** {suitefiles_link}
- **Full Content:** {content}

"""
                    index_results.append(doc_result)
                
                retrieved_content = "\n".join(index_results)
            else:
                retrieved_content = "No relevant documents found in SuiteFiles."
            
            return retrieved_content
                
        except Exception as e:
            logger.error("Search index failed", error=str(e), search_query=search_query)
            return f"Error searching documents: {str(e)}"

    async def _process_rag_with_full_prompt(self, question: str, retrieved_content: str, documents: List[Dict]) -> Dict[str, Any]:
        """Process any question like ChatGPT, with intelligent folder routing when needed."""
        try:
            # Use AI to understand what the user is asking about and route to right folder
            search_strategy = await self._determine_search_strategy(question)
            
            # If we need to search specific folders, do that
            if search_strategy.get('needs_folder_search', False):
                logger.info(f"AI routing to folder: {search_strategy.get('target_folder')} for {search_strategy.get('topic_area')}")
                folder_type = search_strategy.get('target_folder', 'general')
                documents = await self._search_specific_folder(question, folder_type)
                retrieved_content = self._format_documents_content(documents) if documents else ""
            
            # Create prompt for comprehensive information extraction
            prompt = f"""MANDATORY REQUIREMENT: YOU MUST END YOUR RESPONSE WITH SUITEFILES LINKS IN THIS EXACT FORMAT:

**Sources:**
- **Document Name** - [SuiteFiles Link]
- **Document Name** - [SuiteFiles Link]

You are an intelligent AI assistant with access to DTCE's document database. Answer the user's question EXACTLY as asked with specific, targeted information.

USER QUESTION: "{question}"

DTCE DOCUMENTS:
{retrieved_content if retrieved_content else "No specific documents found for this query."}

CRITICAL INSTRUCTIONS:

1. **UNDERSTAND THE EXACT QUESTION**: Analyze what the user is specifically asking for:
   - If they ask for "projects where clients don't like" → Find projects with client complaints, issues, rework, or problems
   - If they ask for "wellness policy" → Extract the actual policy content and requirements
   - If they ask for "project 225" → Give specific details about that project
   - If they ask for NZ standards → Extract the exact technical requirements and clause numbers

2. **ANSWER THE ACTUAL QUESTION**: Don't give generic information. Answer specifically what was asked:
   - For problem projects → Identify which projects had issues and what went wrong
   - For policies → Extract the actual policy text and requirements
   - For technical questions → Give exact specifications, calculations, and standards
   - For project references → List relevant project numbers and scope details

3. **BE SPECIFIC AND TARGETED**: Extract exactly what the user needs:
   - Project numbers and job details
   - Specific technical requirements and standards
   - Exact policy text and procedures
   - Names, contacts, and company details
   - Problem areas and lessons learned

4. **NO OFF-TOPIC RESPONSES**: Stay focused on answering the exact question asked. Don't provide general information if they asked for something specific.

5. **EXTRACT ACTIONABLE DETAILS**: Give information the user can immediately use for their work.

MANDATORY: After providing your answer, you MUST include a "Sources:" section with SuiteFiles links for every document you referenced. Format as clickable markdown links like this: [Document Name](url). This is required for every response that uses DTCE documents.

Now answer the user's question with specific, targeted information from the documents:"""

            # Generate response as smart DTCE colleague
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a senior engineer at DTCE with comprehensive knowledge of all company documents, procedures, and past projects in SuiteFiles. You also have expert general engineering knowledge. Answer questions naturally like a helpful, experienced colleague would. Be practical, knowledgeable, and provide actionable advice."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Very low for maximum consistency
                top_p=0.1,  # Limit token sampling for deterministic responses
                max_tokens=2500,   # Adequate for comprehensive engineering advice
                seed=12345  # Fixed seed for deterministic responses
            )
            
            answer = response.choices[0].message.content
            
            # POST-PROCESSING: Force SuiteFiles links if AI didn't include them
            if documents and "SuiteFiles" not in answer:
                logger.warning("AI response missing SuiteFiles links - forcing inclusion")
                
                # Build the Sources section manually
                sources_section = "\n\n**Sources:**"
                for doc in documents[:3]:  # Limit to top 3 for readability
                    filename = doc.get('filename', 'Unknown Document')
                    blob_url = self._get_blob_url_from_doc(doc)
                    suitefiles_link = suitefiles_converter.get_safe_suitefiles_url(blob_url)
                    
                    if suitefiles_link:
                        # Clean filename for display
                        display_name = filename.replace('.pdf', '').replace('_', ' ').title()
                        # Use markdown link format to hide the ugly URL
                        sources_section += f"\n- [{display_name}]({suitefiles_link})"
                
                # Append the sources section to the answer
                answer += sources_section
            
            # Format sources for display
            sources = []
            for doc in documents[:5]:
                filename = doc.get('filename', 'Unknown')
                blob_url = self._get_blob_url_from_doc(doc)
                suitefiles_link = suitefiles_converter.get_safe_suitefiles_url(blob_url)
                
                source_entry = {
                    'filename': filename,
                    'excerpt': doc.get('content', '')[:200] + '...' if doc.get('content') else 'Content not available'
                }
                
                if suitefiles_link:
                    source_entry['link'] = suitefiles_link
                    
                sources.append(source_entry)

            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',  # High confidence for ChatGPT-style responses
                'documents_searched': len(documents),
                'rag_type': 'chatgpt_conversational',
                'response_type': 'natural_conversation'
            }
                
        except Exception as e:
            logger.error("RAG processing failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while processing your question: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'rag_type': 'error'
            }

    async def _search_documents(self, search_query: str, project_filter: Optional[str] = None, 
                              doc_types: Optional[List[str]] = None, use_semantic: bool = True) -> List[Dict]:
        """Search for relevant documents using both semantic and keyword search."""
        try:
            logger.info("Searching Azure index", search_query=search_query, doc_types=doc_types, use_semantic=use_semantic)
            
            # Build search parameters with semantic search capability
            search_params = {
                'search_text': search_query,
                'top': 20,
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder"]
            }
            
            # Add semantic search configuration for better intent understanding
            if use_semantic:
                search_params.update({
                    'query_type': 'semantic',
                    'semantic_configuration_name': 'default',
                    'query_caption': 'extractive',
                    'query_answer': 'extractive'
                })
                logger.info("Using semantic search for better intent understanding")
            
            # Build filters
            filters = []
            
            # Add exclusion filter for superseded/archive/trash/photos folders
            excluded_filter = "(not search.ismatch('*superseded*', 'filename')) and (not search.ismatch('*superceded*', 'filename')) and (not search.ismatch('*archive*', 'filename')) and (not search.ismatch('*trash*', 'filename')) and (not search.ismatch('*photos*', 'filename'))"
            filters.append(excluded_filter)
            logger.info("Added exclusion filter for superseded folders")
            
            # Add document type filter if specified
            if doc_types:
                doc_filter = ' or '.join([f"search.ismatch('*.{ext}', 'filename')" for ext in doc_types])
                filters.append(f"({doc_filter})")
                logger.info("Added document type filter", filter=doc_filter)
            
            # Combine filters with AND logic
            if filters:
                search_params['filter'] = ' and '.join(filters)
            
            # Try semantic search first, fallback to keyword if it fails
            try:
                results = self.search_client.search(**search_params)
                documents = [dict(result) for result in results]
                
                logger.info("Search completed successfully", 
                           search_type="semantic" if use_semantic else "keyword",
                           documents_found=len(documents),
                           filenames=[doc.get('filename', 'Unknown') for doc in documents[:5]])
                
                # Apply AGGRESSIVE filtering for superseded/archive documents
                filtered_documents = []
                for doc in documents:
                    blob_name = doc.get('blob_name', '') or doc.get('filename', '')
                    blob_url = doc.get('blob_url', '') or ''
                    content = doc.get('content', '')
                    filename = doc.get('filename', '')
                    
                    # Filter out ONLY true phantom/stub documents (much more specific criteria)
                    is_phantom = False
                    if content and len(content) < 50:  # Only check very short content
                        # Check if content is EXACTLY just "Document: filename.pdf" (true phantom document)
                        expected_stub = f"Document: {filename}"
                        if content.strip() == expected_stub:
                            is_phantom = True
                            logger.info("EXCLUDED true phantom/stub document", 
                                      filename=filename, 
                                      content_length=len(content),
                                      content_sample=content[:50])
                    # NOTE: Real documents with short content (like policy docs) should NOT be filtered out
                    
                    # Check multiple fields and variations for superseded content
                    superseded_patterns = [
                        'superseded', 'superceded', 'archive', 'archived', 'obsolete', 
                        'deprecated', 'old', 'backup', 'temp', 'temporary', 'draft', 
                        'drafts', 'trash', 'deleted', 'recycle', 'legacy', 'photos'
                    ]
                    
                    is_superseded = False
                    for pattern in superseded_patterns:
                        if (pattern.lower() in blob_name.lower() or 
                            pattern.lower() in blob_url.lower() or
                            pattern.capitalize() in blob_name or
                            pattern.capitalize() in blob_url or
                            pattern.upper() in blob_name or
                            pattern.upper() in blob_url):
                            is_superseded = True
                            logger.info("EXCLUDED superseded document", 
                                      filename=doc.get('filename'), 
                                      blob_name=blob_name,
                                      pattern_found=pattern)
                            break
                    
                    if not is_superseded and not is_phantom:
                        filtered_documents.append(doc)
                
                documents = filtered_documents
                logger.info("After aggressive superseded filtering", documents_remaining=len(documents))
                
            except Exception as semantic_error:
                if use_semantic:
                    logger.warning("Semantic search failed, falling back to keyword search", 
                                 error=str(semantic_error))
                    
                    # Fallback to keyword search
                    search_params.pop('query_type', None)
                    search_params.pop('semantic_configuration_name', None)
                    search_params.pop('query_caption', None)
                    search_params.pop('query_answer', None)
                    
                    results = self.search_client.search(**search_params)
                    documents = [dict(result) for result in results]
                    
                    # Apply AGGRESSIVE filtering for superseded/archive documents (fallback)
                    filtered_documents = []
                    for doc in documents:
                        blob_name = doc.get('blob_name', '') or doc.get('filename', '')
                        blob_url = doc.get('blob_url', '') or ''
                        content = doc.get('content', '')
                        filename = doc.get('filename', '')
                        
                        # Filter out ONLY true phantom/stub documents (much more specific criteria)
                        is_phantom = False
                        if content and len(content) < 50:  # Only check very short content
                            # Check if content is EXACTLY just "Document: filename.pdf" (true phantom document)
                            expected_stub = f"Document: {filename}"
                            if content.strip() == expected_stub:
                                is_phantom = True
                                logger.info("EXCLUDED true phantom/stub document (fallback)", 
                                          filename=filename, 
                                          content_length=len(content),
                                          content_sample=content[:50])
                        # NOTE: Real documents with short content (like policy docs) should NOT be filtered out
                        
                        # Check multiple fields and variations for superseded content
                        superseded_patterns = [
                            'superseded', 'superceded', 'archive', 'archived', 'obsolete', 
                            'deprecated', 'old', 'backup', 'temp', 'temporary', 'draft', 
                            'drafts', 'trash', 'deleted', 'recycle', 'legacy', 'photos'
                        ]
                        
                        is_superseded = False
                        for pattern in superseded_patterns:
                            if (pattern.lower() in blob_name.lower() or 
                                pattern.lower() in blob_url.lower() or
                                pattern.capitalize() in blob_name or
                                pattern.capitalize() in blob_url or
                                pattern.upper() in blob_name or
                                pattern.upper() in blob_url):
                                is_superseded = True
                                logger.info("EXCLUDED superseded document (fallback)", 
                                          filename=doc.get('filename'), 
                                          blob_name=blob_name,
                                          pattern_found=pattern)
                                break
                        
                        if not is_superseded and not is_phantom:
                            filtered_documents.append(doc)
                    
                    documents = filtered_documents
                    
                    logger.info("Keyword search fallback completed", 
                               documents_found=len(documents),
                               filenames=[doc.get('filename', 'Unknown') for doc in documents[:5]])
                else:
                    raise semantic_error
            
            return documents
            
        except Exception as e:
            logger.error("Document search failed", error=str(e), search_query=search_query)
            return []
    
    def _get_safe_suitefiles_url(self, blob_url: str, link_type: str = "file") -> Optional[str]:
        """Get SuiteFiles URL or None if conversion fails."""
        if not blob_url:
            logger.warning("No blob URL provided for SuiteFiles conversion")
            return None
        
        suitefiles_url = self._convert_to_suitefiles_url(blob_url, link_type)
        if suitefiles_url:
            return suitefiles_url
        else:
            logger.warning("Failed to convert blob URL to SuiteFiles URL", blob_url=blob_url)
            # Return the direct blob URL if SharePoint conversion fails
            return blob_url
    
    def _extract_project_name_from_blob_url(self, blob_url: str) -> str:
        """Extract project name/number from blob URL path - only if actually in Projects folder."""
        if not blob_url:
            logger.warning("No blob URL provided for project extraction")
            return ""
        
        try:
            logger.info("Extracting project name from blob URL", blob_url=blob_url)
            
            # Only look for "Projects" folder specifically - not other folders like Engineering, Templates, etc.
            import re
            
            # Look for both "/Projects/" and "/Project/" folders (case insensitive) followed by project structure
            projects_match = re.search(r'/Projects?/(.+)', blob_url, re.IGNORECASE)
            if projects_match:
                path_after_projects = projects_match.group(1)
                
                # Remove query parameters and URL encoding
                if "?" in path_after_projects:
                    path_after_projects = path_after_projects.split("?")[0]
                
                from urllib.parse import unquote
                path_after_projects = unquote(path_after_projects)
                
                logger.info("Found path after /Project(s)/", path_after_projects=path_after_projects)
                
                # Split path and look for project number patterns - typically 220/220294/... 
                path_segments = [seg for seg in path_after_projects.split('/') if seg]
                logger.info("Path segments after Project(s)", segments=path_segments)
                
                if len(path_segments) >= 2:
                    # Get project number (second segment, like "220294")
                    project_number = path_segments[1]
                    if project_number.isdigit() and len(project_number) >= 3:
                        logger.info("Extracted project number from second segment", project_number=project_number)
                        return f"Project {project_number}"
                elif len(path_segments) >= 1:
                    # Get first segment if it looks like a project number
                    project_number = path_segments[0]
                    if project_number.isdigit() and len(project_number) >= 3:
                        logger.info("Extracted project number from first segment", project_number=project_number)
                        return f"Project {project_number}"
            
            # If we reach here, it's either not in Project(s) folder or doesn't have valid project structure
            logger.info("Document not in Project(s) folder or no valid project structure found", blob_url=blob_url)
            return ""  # Return empty string - not a project document
                    
        except Exception as e:
            logger.warning("Failed to extract project name from blob URL", error=str(e), blob_url=blob_url)
            
        return ""  # Return empty string instead of "Unknown Project"

    def _extract_project_from_filename(self, filename: str) -> str:
        """Extract project number from filename if it contains project patterns."""
        if not filename:
            return ""
        
        try:
            import re
            # Look for various project number patterns - extremely flexible
            patterns = [
                r'(?:^|[^0-9])([0-9]{3,8})(?:[^0-9]|$)',  # Any 3-8 digit number (very flexible)
                r'P-([0-9]+)',  # P-XXXX format (any number of digits)
                r'Project\s*([0-9]+)',  # Project XXXX format (any number of digits)
                r'([0-9]+)',  # Any sequence of digits (last resort)
            ]
            
            for pattern in patterns:
                match = re.search(pattern, filename, re.IGNORECASE)
                if match:
                    project_number = match.group(1)
                    # Very minimal validation - just ensure it's reasonable length and all digits
                    if len(project_number) >= 3 and len(project_number) <= 10 and project_number.isdigit():
                        logger.info("Extracted project from filename", filename=filename, project_number=project_number)
                        return f"Project {project_number}"
                    
        except Exception as e:
            logger.warning("Failed to extract project from filename", filename=filename, error=str(e))
            
        return ""  # Return empty string instead of "Unknown Project"

    def _is_real_project_document(self, blob_name: str, project_name: str) -> bool:
        """Determine if a document is actually from a real project (not CPD, training, etc.)."""
        if not blob_name or not project_name:
            return False
            
        blob_name_lower = blob_name.lower()
        project_name_lower = project_name.lower()
        
        # Must be in a Projects folder
        if not ('projects/' in blob_name_lower or '/projects/' in blob_name_lower):
            return False
        
        # Exclude common non-project folders that might be in Projects directory
        non_project_indicators = [
            'cpd', 'training', 'general practitioners', 'webinar', 'seminar',
            'course', 'education', 'learning', 'development', 'template',
            'standard', 'guideline', 'reference', 'library'
        ]
        
        # Check if project name contains non-project indicators
        for indicator in non_project_indicators:
            if indicator in project_name_lower:
                return False
                
        # Check if blob path contains non-project indicators
        for indicator in non_project_indicators:
            if indicator in blob_name_lower:
                return False
        
        # Check for 6-digit project number pattern in blob path (most reliable indicator)
        import re
        project_number_pattern = r'/(\d{6})/'
        if re.search(project_number_pattern, blob_name):
            return True
            
        # If we can't find a clear project number pattern, be conservative
        return False
    
    def _convert_to_suitefiles_url(self, blob_url: str, link_type: str = "file") -> Optional[str]:
        """Convert Azure blob URL to SuiteFiles SharePoint URL."""
        if not blob_url:
            return None
            
        try:
            logger.info("Converting blob URL to SuiteFiles SharePoint URL", blob_url=blob_url)
            
            # Extract the path after dtce-documents
            path_part = None
            if "/dtce-documents/" in blob_url:
                path_part = blob_url.split("/dtce-documents/")[1]
                logger.info("Found dtce-documents in URL", path_part=path_part)
            
            if path_part:
                # Remove any query parameters
                if "?" in path_part:
                    path_part = path_part.split("?")[0]
                
                # Remove URL encoding first
                from urllib.parse import unquote, quote
                path_part = unquote(path_part)
                
                # Now properly encode for SharePoint URL fragment
                # SharePoint URL fragments need proper encoding
                encoded_path = quote(path_part, safe='/')
                
                # Build SharePoint URL - use the documents.aspx format
                # Base SharePoint URL for SuiteFiles
                base_url = "https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#"
                suitefiles_url = f"{base_url}/{encoded_path}"
                
                logger.info("Converted to SharePoint SuiteFiles URL", suitefiles_url=suitefiles_url)
                return suitefiles_url
            else:
                logger.warning("Could not find dtce-documents in blob URL", blob_url=blob_url)
                
        except Exception as e:
            logger.error("Failed to convert blob URL to SuiteFiles SharePoint URL", error=str(e), blob_url=blob_url)
            
        return None
    
    def _format_sources(self, documents: List[Dict]) -> List[Dict]:
        """Format document sources for response."""
        sources = []
        for doc in documents[:10]:  # Check more documents but limit final sources
            # Filter out superseded/archive documents at source formatting level too
            blob_name = doc.get('blob_name', '') or doc.get('filename', '')
            excluded_terms = ['superseded', 'superceded', 'archive', 'obsolete', 'old', 'backup', 'temp', 'draft', 'trash']
            should_exclude = any(term in blob_name.lower() for term in excluded_terms)
            
            if should_exclude:
                logger.debug("Excluded superseded document during source formatting", 
                           filename=doc.get('filename'), blob_name=blob_name)
                continue
                
            source = {
                'filename': doc.get('filename', 'Unknown'),
                'title': doc.get('filename', 'Unknown'),  # Add title field for consistency
                'folder': doc.get('folder', '')
            }
            
            # EXTRACT project information from blob URL ONLY if it's from Projects folder
            blob_url = doc.get('blob_url', '')
            if blob_url:
                # Extract project name from blob URL - only returns project if document is in /Projects/ folder
                extracted_project = self._extract_project_name_from_blob_url(blob_url)
                if extracted_project:  # If we successfully extracted a project (confirms it's from Projects folder)
                    source['project'] = extracted_project
                # Note: If not from Projects folder, no 'project' key is added to source
                
                # Add SuiteFiles link
                suitefiles_url = suitefiles_converter.get_safe_suitefiles_url(blob_url)
                if suitefiles_url and suitefiles_url != "Document available in SuiteFiles":
                    source['suitefiles_url'] = suitefiles_url
                    source['url'] = suitefiles_url  # Add url field for consistency
                else:
                    source['url'] = blob_url  # Fallback to blob_url if no SuiteFiles URL
            else:
                source['url'] = 'No URL'  # Ensure url field always exists
            
            sources.append(source)
            
            # Limit to top 5 sources after filtering
            if len(sources) >= 5:
                break
        
        return sources
    
    async def _generate_project_answer_with_links(self, prompt: str, context: str) -> str:
        """Generate answer using GPT with project context and SuiteFiles links."""
        try:
            # Enhanced system prompt that emphasizes proper formatting
            system_prompt = """You are a helpful structural engineering AI assistant for DTCE. 

IMPORTANT FORMATTING INSTRUCTIONS:
- When referencing documents in your response, ALWAYS check if the document has "Project: Project XXXXX" information in the context
- For documents WITH project information: **[Document Name] (Project: XXXXX)**: [Description]
- For documents WITHOUT project information: **[Document Name]**: [Description]

EXAMPLES:
If context shows "DOCUMENT: 217668-DR-123-C.pdf ... Project: Project 219260", write:
**217668-DR-123-C.pdf (Project 219260)**: This document details the retrofitting...

If context shows "DOCUMENT: Engineering Guide.pdf" with NO project line, write:
**Engineering Guide.pdf**: This document provides guidance...

CRITICAL: Look for "Project: Project XXXXX" in each document's context and include it in your response.

Provide practical, accurate engineering guidance for New Zealand conditions using the retrieved documents below."""

            # Construct the full prompt with context
            full_prompt = f"""Based on the following retrieved documents, please answer the user's question:

{context}

User Question: {prompt}

Please provide a comprehensive answer using the documents above, and include properly formatted document references with complete SuiteFiles links."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("GPT response generation failed", error=str(e))
            return f"I encountered an error generating the response: {str(e)}"

    async def _is_conversational_query(self, question: str, conversation_history: Optional[List[Dict]] = None) -> bool:
        """
        Determine if a query is conversational (needs context) vs informational (needs search).
        
        Conversational queries include:
        - Short responses like "really", "ok", "thanks", "yes", "no"
        - Follow-up questions that reference previous context
        - Clarification requests
        
        Informational queries include:
        - Technical questions
        - Document requests
        - Specific information needs
        """
        
        # Quick pattern matching for obvious conversational queries
        question_lower = question.lower().strip()
        
        # Very short conversational responses
        short_conversational = [
            'really', 'ok', 'okay', 'thanks', 'thank you', 'yes', 'no', 'yeah', 'sure',
            'got it', 'i see', 'right', 'correct', 'true', 'false', 'good', 'great',
            'nice', 'cool', 'wow', 'hmm', 'ah', 'oh', 'what', 'why', 'how come'
        ]
        
        if question_lower in short_conversational:
            return True
        
        # If no conversation history, everything else is informational
        if not conversation_history:
            return False
        
        # Use AI to analyze conversational context for more complex cases
        try:
            context_prompt = f"""Analyze if this user query requires searching documents or is a conversational response to previous context.

Recent conversation history:
{self._format_conversation_context(conversation_history)}

Current user query: "{question}"

Is this query:
A) CONVERSATIONAL - A response/reaction to previous messages that should be handled conversationally
B) INFORMATIONAL - A new question that requires searching DTCE documents

Critical guidelines:
- Simple reactions like "really", "ok", "thanks", "wow", "I see" = CONVERSATIONAL
- ANY request for NEW information (even follow-ups) = INFORMATIONAL
- Questions with "what", "how", "tell me", "about", "more" = INFORMATIONAL
- Phrases like "what about wind loads", "tell me more about concrete" = INFORMATIONAL
- Calculation requests like "how do I calculate" = INFORMATIONAL

Key rule: If the user is asking for ANY additional information or explanation, it's INFORMATIONAL.

Answer with just: CONVERSATIONAL or INFORMATIONAL"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": context_prompt}],
                max_tokens=20,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip().upper()
            is_conversational = 'CONVERSATIONAL' in result
            
            logger.info("Conversational analysis completed",
                       query=question,
                       classification=result,
                       is_conversational=is_conversational)
            
            return is_conversational
            
        except Exception as e:
            logger.warning("Conversational analysis failed, defaulting to informational", error=str(e))
            return False
    
    def _format_conversation_context(self, conversation_history: List[Dict]) -> str:
        """Format conversation history for context analysis."""
        if not conversation_history:
            return "No previous conversation"
        
        formatted = []
        for turn in conversation_history[-3:]:  # Last 3 turns for context
            role = turn.get('role', 'unknown')
            content = turn.get('content', '')
            formatted.append(f"{role.upper()}: {content[:200]}...")  # Truncate long messages
        
        return "\n".join(formatted)
    
    async def _handle_conversational_query(self, question: str, conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Handle conversational queries using context instead of document search."""
        
        try:
            # Build conversational prompt with history
            conversation_context = self._format_conversation_context(conversation_history) if conversation_history else "No previous conversation"
            
            conversational_prompt = f"""You are DTCE AI Assistant, having a natural conversation with a DTCE employee.

Recent conversation context:
{conversation_context}

The user just said: "{question}"

This appears to be a conversational response rather than a request for specific information. Please respond naturally and conversationally, as a helpful colleague would. 

Guidelines:
- Keep it brief and natural
- Acknowledge their response appropriately
- If they seem to want more information about the previous topic, offer to help
- If they're expressing understanding/agreement, acknowledge that
- Be friendly and professional
- Don't search for documents unless they specifically ask for more information

Respond naturally as DTCE AI Assistant would in conversation."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are DTCE AI Assistant, a helpful and conversational AI that assists DTCE employees. You have natural conversations and don't always need to search documents."
                    },
                    {"role": "user", "content": conversational_prompt}
                ],
                max_tokens=300,
                temperature=0.1  # Consistent low temperature for deterministic responses
            )
            
            answer = response.choices[0].message.content.strip()
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'conversational',
                'documents_searched': 0,
                'rag_type': 'conversational_response',
                'search_method': 'conversation_context',
                'response_style': 'natural_conversation'
            }
            
        except Exception as e:
            logger.error("Conversational response generation failed", error=str(e))
            return {
                'answer': "I understand. Is there anything else I can help you with?",
                'sources': [],
                'confidence': 'fallback',
                'documents_searched': 0,
                'rag_type': 'conversational_fallback'
            }

    async def universal_ai_assistant(self, question: str) -> Dict[str, Any]:
        """Universal AI assistant that follows the 5 DTCE prompt categories.
        
        Routes questions to the correct DTCE prompt category:
        1. Policy Prompt (H&S, IT policies)
        2. Technical & Admin Procedures (H2H handbooks)  
        3. NZ Engineering Standards
        4. Project Reference
        5. Client Reference
        6. General Engineering (no DTCE search)
        """
        try:
            # STEP 1: Classify into one of the 5 DTCE prompt categories
            strategy = await self._determine_search_strategy(question)
            
            logger.info(f"DTCE Prompt Category: {strategy.get('prompt_category')}", 
                       reasoning=strategy.get('reasoning'))
            
            # STEP 2: Handle based on category
            if strategy.get('prompt_category') == 'general_engineering':
                # General engineering - no DTCE search needed
                return await self._provide_general_engineering_advice(question)
                
            elif strategy.get('needs_dtce_search', False):
                # Search DTCE SuiteFiles using category-specific logic
                return await self._search_dtce_by_category(question, strategy)
                
            else:
                # Fallback to general advice if unsure
                return await self._provide_general_engineering_advice(question)
                
        except Exception as e:
            logger.error("Universal AI assistant failed", error=str(e), question=question)
            return await self._handle_ai_error(question, str(e))

    async def _search_dtce_by_category(self, question: str, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Search DTCE SuiteFiles based on the specific prompt category."""
        try:
            category = strategy.get('prompt_category')
            search_folders = strategy.get('search_folders', [])
            
            logger.info(f"Searching DTCE for {category}", folders=search_folders)
            
            # Enhance search query for project questions with year understanding
            enhanced_question = self._enhance_project_search_query(question, category)
            
            # Perform semantic search (the search service will handle folder filtering)
            documents = await self.semantic_search.search_documents(enhanced_question)
            
            if documents:
                # Filter documents by category if needed
                filtered_docs = self._filter_documents_by_category(documents, category, search_folders, question)
                
                if filtered_docs:
                    # Generate category-specific response
                    return await self._generate_category_response(question, filtered_docs, category)
                else:
                    # No relevant documents found for this category
                    return await self._handle_no_category_documents(question, category)
            else:
                # No documents found at all
                return await self._handle_no_category_documents(question, category)
                
        except Exception as e:
            logger.error("DTCE category search failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    def _enhance_project_search_query(self, question: str, category: str) -> str:
        """Enhance search queries for project questions with year-to-folder conversion."""
        if category != 'project_reference':
            return question
            
        enhanced_query = question.lower()
        
        # Convert year references to folder paths for better search
        year_conversions = {
            '2025': 'Projects/225',
            '2024': 'Projects/224', 
            '2023': 'Projects/223',
            '2022': 'Projects/222',
            '2021': 'Projects/221',
            '2020': 'Projects/220',
            '2019': 'Projects/219'
        }
        
        # Check if question mentions specific years
        for year, folder_path in year_conversions.items():
            if year in enhanced_query:
                # Add folder path to search query
                enhanced_query += f" {folder_path}"
                logger.info(f"Enhanced project search: {year} -> {folder_path}")
        
        return enhanced_query

    def _filter_documents_by_category(self, documents: List[Dict], category: str, search_folders: List[str], question: str = "") -> List[Dict]:
        """Let AI be smart - minimal filtering, let semantic search and AI handle relevance."""
        
        # Check if user specifically asks for superseded/old documents
        include_superseded = any(term in question.lower() for term in ['superseded', 'old', 'previous', 'outdated', 'history', 'supersede'])
        
        if include_superseded:
            # User wants old docs - return everything
            return documents[:10]
        else:
            # Normal operation - just remove obvious archive/temp folders, let AI decide relevance
            filtered = []
            for doc in documents:
                filename = doc.get('filename', '').lower()
                blob_url = doc.get('blob_url', '').lower()
                
                # Only filter out obvious junk - let AI decide if documents are relevant
                is_obvious_junk = any(term in blob_url for term in ['/archive/', '/temp/', '/trash/', '/backup/', '/deleted/'])
                
                if not is_obvious_junk:
                    filtered.append(doc)
            
            return filtered[:15]  # Return more documents, let AI decide relevance

    async def _generate_category_response(self, question: str, documents: List[Dict], category: str) -> Dict[str, Any]:
        """Generate advisory response specific to the DTCE prompt category with enhanced intelligence."""
        try:
            # Format documents content
            retrieved_content = self._format_documents_content(documents)
            
            # Check if superseded documents should be included
            include_superseded = any(term in question.lower() for term in ['superseded', 'old', 'previous', 'outdated', 'history', 'supersede'])
            
            # Create enhanced category-specific prompts with advisory features
            if category == 'policy':
                system_prompt = """You are an intelligent AI assistant with access to DTCE's internal documents. Your job is to extract and summarize the actual information from these documents to answer questions thoroughly. Never just provide links - extract the content and explain it clearly."""
                
                user_prompt = f"""Question: {question}

DTCE Documents:
{retrieved_content[:3500]}

CRITICAL: Extract the actual policy information from these documents and provide a comprehensive answer. Include:
1. The specific policy details and requirements
2. Key points and provisions
3. Any relevant procedures or guidelines
4. Practical implications for employees

Do NOT just mention document names or provide links. Extract and explain the actual content so the user gets their answer immediately without having to open other documents."""
                
            elif category == 'procedures':
                system_prompt = """You are an intelligent AI assistant with access to DTCE's procedures. Extract and explain the actual procedural information to help users understand what they need to do."""
                
                user_prompt = f"""Question: {question}

DTCE Procedures:
{retrieved_content[:3500]}

Extract the actual procedural information from these documents. Provide:
1. Step-by-step procedures if applicable
2. Requirements and guidelines
3. Forms, templates, or tools mentioned
4. Practical implementation details

Give them the complete information they need to follow the procedure, not just document references."""
                
            elif category == 'nz_standards':
                system_prompt = """You are an intelligent AI assistant with access to NZ engineering standards. Extract and explain the actual technical requirements and standards information."""
                
                user_prompt = f"""Question: {question}

NZ Standards:
{retrieved_content[:3500]}

Extract the specific technical information from these standards documents. Provide:
1. Exact clauses, requirements, and specifications
2. Technical parameters and limits
3. Design requirements and calculations
4. Compliance guidelines and best practices

Give them the complete technical details they need, not just standard numbers or document names."""
                
            elif category == 'project_reference':
                system_prompt = """You are an intelligent AI assistant with access to DTCE's project history. Extract and explain the actual project information and insights to help with current work."""
                
                user_prompt = f"""Question: {question}

DTCE Projects:
{retrieved_content[:3500]}

Extract the actual project information from these documents. Provide:
1. Specific project details, scope, and outcomes
2. Design approaches and solutions used
3. Lessons learned and insights
4. Technical specifications and methods
5. Client feedback and project results

Give them comprehensive project insights they can apply to their current work, not just project names or file references."""
                
            elif category == 'client_reference':
                system_prompt = """You are an intelligent AI assistant with access to DTCE's client information. Extract and provide the actual client details and interaction history."""
                
                user_prompt = f"""Question: {question}

Client Information:
{retrieved_content[:3500]}

Extract the actual client information from these documents. Provide:
1. Specific client details and contact information
2. Project history and collaboration details
3. Communication records and feedback
4. Technical requirements and preferences
5. Relationship insights and recommendations

Give them complete client information they can use immediately, not just document names or references."""
            else:
                system_prompt = "You are an intelligent AI assistant with access to DTCE documents. Extract and explain the actual information to answer questions thoroughly, not just document references."
                user_prompt = f"""Question: {question}

DTCE Information:
{retrieved_content[:3500]}

Extract and explain the actual information from these documents to answer this question comprehensively. Provide specific details, not just document names or links."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=3000  # Increased for comprehensive advisory responses
            )
            
            answer = response.choices[0].message.content
            
            # FORCE SUITEFILES LINKS - Use our helper function
            answer = self._force_suitefiles_links(answer, documents)
            
            # Format sources
            sources = []
            for doc in documents[:5]:
                filename = doc.get('filename', 'Unknown')
                blob_url = self._get_blob_url_from_doc(doc)
                suitefiles_link = suitefiles_converter.get_safe_suitefiles_url(blob_url)
                
                source_entry = {
                    'filename': filename,
                    'excerpt': doc.get('content', '')[:200] + '...' if doc.get('content') else 'Content not available'
                }
                
                if suitefiles_link:
                    source_entry['link'] = suitefiles_link
                    
                sources.append(source_entry)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': f'dtce_{category}',
                'prompt_category': category,
                'response_type': 'category_specific'
            }
            
        except Exception as e:
            logger.error("Category response generation failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    async def _provide_general_engineering_advice(self, question: str) -> Dict[str, Any]:
        """Provide comprehensive general engineering advice with advisory guidance."""
        try:
            prompt = f"""You are a senior structural engineering consultant providing comprehensive advisory guidance.

QUESTION: "{question}"

ENHANCED ADVISORY RESPONSE REQUIRED:

**1. DIRECT TECHNICAL ANSWER**: Address the specific engineering question with technical principles

**2. NZ STANDARDS & CODES**: Reference relevant NZ standards (NZS 3101, 3404, 1170, etc.) and Building Code requirements

**3. ADVISORY ANALYSIS**:
- Common engineering mistakes and pitfalls to avoid
- Critical safety considerations and warnings
- Quality assurance and verification approaches
- Risk assessment and management

**4. LESSONS LEARNED & BEST PRACTICES**:
- Industry best practices and proven approaches
- What works well vs what commonly causes problems
- "DO" and "DON'T" recommendations based on engineering experience
- Preventive measures for common engineering failures

**5. GENERAL GUIDELINES**: Provide engineering principles that apply broadly:
- Design philosophy and approach recommendations
- Professional engineering standards and ethics
- Project management and quality considerations
- Client communication and engineering judgment

**6. COMBINED KNOWLEDGE APPROACH**:
- Integrate theoretical engineering principles with practical application
- Connect NZ standards with international best practices
- Combine structural theory with real-world construction considerations
- Reference both current standards and emerging best practices

**7. PROFESSIONAL ADVISORY GUIDANCE**:
- Risk mitigation strategies
- Decision-making frameworks for engineering judgment
- Verification and checking procedures
- Professional liability and due diligence considerations

Provide comprehensive engineering guidance that combines technical knowledge with professional advisory insights."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a senior structural engineering consultant providing comprehensive advisory guidance. Combine technical expertise with professional advisory insights, risk assessment, lessons learned, and general engineering guidelines. Reference NZ standards, identify common pitfalls, and provide practical professional guidance."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=3000  # Increased for comprehensive advisory responses
            )
            
            answer = response.choices[0].message.content
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'high',
                'documents_searched': 0,
                'rag_type': 'general_engineering_advice',
                'prompt_category': 'general_engineering',
                'response_type': 'general_knowledge'
            }
            
        except Exception as e:
            logger.error("General engineering advice failed", error=str(e))
            return {
                'answer': f'I encountered an error providing engineering advice: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'rag_type': 'error'
            }

    async def _handle_no_category_documents(self, question: str, category: str) -> Dict[str, Any]:
        """Handle when no relevant documents found for the specific category."""
        try:
            fallback_prompt = f"""The user asked a question about {category} but no relevant DTCE documents were found.

QUESTION: "{question}"
CATEGORY: {category}

Provide helpful guidance about:
1. What information might be available in DTCE's {category} documentation
2. Where they might look for this information
3. General advice on this topic if applicable
4. Suggestions for next steps

Be helpful and professional."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are helping when no specific {category} documents were found. Provide helpful guidance and suggestions."
                    },
                    {"role": "user", "content": fallback_prompt}
                ],
                temperature=0.4,
                max_tokens=1000
            )
            
            answer = f"I couldn't find specific {category} information for your question in our DTCE documents.\n\n{response.choices[0].message.content}"
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'medium',
                'documents_searched': 0,
                'rag_type': f'no_{category}_found',
                'prompt_category': category,
                'response_type': 'helpful_fallback'
            }
            
        except Exception as e:
            logger.error("No category documents handler failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    async def _analyze_question_intent(self, question: str) -> str:
        """Determine if question is general engineering, DTCE-specific, or mixed."""
        try:
            analysis_prompt = f"""You are analyzing an engineer's question to determine what type of response they need.

QUESTION: "{question}"

Determine the type:

1. **general_engineering**: Pure technical/engineering question that any engineer could answer
   Examples: "How do you design a concrete beam?", "What are seismic design principles?", "How to calculate deflection?"

2. **dtce_specific**: Question specifically about DTCE procedures, projects, policies, or internal information
   Examples: "What is DTCE's safety policy?", "Show me past precast projects", "How does DTCE handle reviews?"

3. **mixed**: Question that benefits from both DTCE experience and general engineering knowledge
   Examples: "How should we approach this design?" (could use DTCE experience + general principles)

Reply with ONLY ONE WORD: general_engineering, dtce_specific, or mixed"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You analyze engineering questions to categorize them. Respond with only one word."
                    },
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.1,
                max_tokens=10
            )
            
            result = response.choices[0].message.content.strip().lower()
            return result if result in ['general_engineering', 'dtce_specific', 'mixed'] else 'mixed'
            
        except Exception as e:
            logger.warning("Question intent analysis failed", error=str(e))
            return 'mixed'  # Safe default

    async def _provide_general_advice(self, question: str) -> Dict[str, Any]:
        """Provide general engineering advice without searching SuiteFiles."""
        try:
            prompt = f"""You are a senior engineer at DTCE providing advice to a colleague.

COLLEAGUE'S QUESTION: "{question}"

This is a general engineering question. Provide expert advice using your engineering knowledge. Be practical, helpful, and include relevant standards (especially NZ Standards) when applicable.

Respond like a knowledgeable colleague would - naturally and helpfully."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior structural engineer at DTCE. Provide expert engineering advice to colleagues. Be practical, reference relevant standards, and give actionable guidance."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            return {
                'answer': response.choices[0].message.content,
                'sources': [],
                'confidence': 'high',
                'documents_searched': 0,
                'rag_type': 'general_engineering_advice',
                'response_type': 'expert_knowledge_only'
            }
            
        except Exception as e:
            logger.error("General advice generation failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    async def _search_suitefiles_and_respond(self, question: str, include_general: bool = False) -> Dict[str, Any]:
        """Search SuiteFiles and respond like a knowledgeable DTCE colleague."""
        try:
            # Search SuiteFiles documents
            normalized_result = await self.query_normalizer.normalize_query(question)
            search_query = normalized_result['primary_search_query']
            
            documents = await self.semantic_search.search_documents(search_query, None)
            
            logger.info("SuiteFiles search results", 
                       total_documents=len(documents),
                       sample_filenames=[doc.get('filename', 'Unknown') for doc in documents[:3]])
            
            # Format document content
            retrieved_content = self._format_documents_with_folder_context(documents, self._determine_response_context(documents, question)) if documents else ""
            
            # Generate response as DTCE colleague
            result = await self._process_rag_with_full_prompt(question, retrieved_content, documents)
            
            result.update({
                'rag_type': 'dtce_colleague_advice',
                'search_method': 'suitefiles_semantic',
                'response_type': 'smart_colleague_response'
            })
            
            return result
            
        except Exception as e:
            logger.error("SuiteFiles search and response failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    def _format_documents_content(self, documents: List[Dict]) -> str:
        """Format documents into a readable string for AI processing."""
        if not documents:
            return ""
        
        formatted_content = []
        for i, doc in enumerate(documents[:5], 1):  # Limit to top 5 documents
            content = doc.get('content', '')
            title = doc.get('filename', f'Document {i}')
            score = doc.get('@search.score', doc.get('score', 0))
            blob_url = self._get_blob_url_from_doc(doc)
            suitefiles_link = suitefiles_converter.get_safe_suitefiles_url(blob_url)
            
            # Include SuiteFiles link in the content
            link_text = f"\nSuiteFiles Link: {suitefiles_link}" if suitefiles_link else ""
            
            formatted_content.append(f"Document {i}: {title} (relevance: {score:.2f}){link_text}\n{content}")  # FULL CONTENT - NO TRUNCATION
        
        return "\n\n".join(formatted_content)

    async def _analyze_information_needs(self, question: str) -> Dict[str, Any]:
        """Let AI determine what type of information the user needs."""
        try:
            analysis_prompt = f"""Analyze this engineering question and determine what information is needed:

QUESTION: "{question}"

Determine:
1. Does this question need DTCE-specific documents/information?
2. If yes, which folder type would be most relevant?
3. Does this need external web search?
4. Does this need project job numbers or SuiteFiles links?
5. What's the user's intent?

DTCE Folder Types:
- policies: H&S policies, IT policies, employee policies, wellness policies, workplace policies, HR policies
- procedures: Technical procedures, admin procedures, H2H (how-to) documents, templates, spreadsheets
- standards: NZ engineering standards, codes, specifications, clause references
- projects: Past project information, project references, job numbers
- clients: Client information, contact details, builder information

Policy Keywords Guide:
- "wellness policy", "wellbeing policy", "employee wellness" → policies folder (NOT COVID/environmental)
- "health and safety", "H&S", "safety policy" → policies folder  
- "IT policy", "computer policy", "technology policy" → policies folder
- "environmental policy", "sustainability" → policies folder
- "COVID", "pandemic", "coronavirus" → policies folder (specific health response)
- "HR policy", "human resources", "employment policy" → policies folder

Technical Keywords Guide:
- "NZ standards", "AS/NZS", "code requirements", "clause" → standards folder
- "calculation", "design guide", "template", "spreadsheet" → procedures folder
- "project", "job number", "past work", "examples" → projects folder
- "client", "builder", "contact", "contractor" → clients folder

Special Requirements:
- If asking for "job numbers", "past projects with keywords", or "projects that have scope" → needs project search with job numbers
- If asking for "links", "SuiteFiles access", "templates" → needs document links
- If asking for "online references", "forums", "threads" → needs web search
- If asking for "product specifications", "suppliers", "market options" → needs web search + documents
- If asking for "builders we've worked with", "client contact details" → needs client/builder database

Respond with JSON:
{{
    "needs_dtce_documents": true/false,
    "folder_type": "policies|procedures|standards|projects|clients|none",
    "needs_web_search": true/false,
    "needs_job_numbers": true/false,
    "needs_links": true/false,
    "needs_database_search": true/false,
    "question_intent": "brief description",
    "response_approach": "document_search|web_search|database_search|hybrid|general_ai",
    "search_keywords": ["key", "words", "to", "search"]
}}"""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI that understands engineering questions and determines the best information sources. Always respond with valid JSON only - no additional text."
                    },
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            import json
            response_text = response.choices[0].message.content.strip()
            
            # Clean up response if it has extra text
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Try to find JSON in the response
            if '{' in response_text:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                response_text = response_text[start_idx:end_idx]
            
            logger.info(f"Raw AI response: {response_text}")
            analysis = json.loads(response_text)
            return analysis
            
        except Exception as e:
            logger.error("Information needs analysis failed", error=str(e))
            # Default to general AI response if analysis fails
            return {
                "needs_dtce_documents": False,
                "folder_type": "none", 
                "needs_web_search": False,
                "needs_job_numbers": False,
                "needs_links": False,
                "needs_database_search": False,
                "question_intent": "general question",
                "response_approach": "general_ai",
                "search_keywords": []
            }

    async def _generate_general_ai_response(self, question: str, analysis: Dict) -> Dict[str, Any]:
        """Generate a ChatGPT-style response for general questions."""
        try:
            general_prompt = f"""You are DTCE AI Assistant - a helpful, knowledgeable AI assistant for DTCE employees.

The user asked: "{question}"

This appears to be a general question that doesn't require specific DTCE documents. Please provide a helpful, accurate response like ChatGPT would, but with the understanding that you're assisting a DTCE employee.

Be conversational, helpful, and professional. Use your general knowledge to provide a useful response."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful AI assistant for DTCE employees. Provide accurate, helpful responses like ChatGPT."
                    },
                    {"role": "user", "content": general_prompt}
                ],
                temperature=0.3,  # Slightly more creative for general responses
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'general_ai_knowledge',
                'documents_searched': 0,
                'rag_type': 'chatgpt_style_response',
                'search_method': 'no_search_needed',
                'question_intent': analysis.get('question_intent', 'general'),
                'folder_searched': 'none'
            }
            
        except Exception as e:
            logger.error("General AI response failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    async def _search_specific_folder(self, question: str, folder_type: str) -> List[Dict]:
        """Search the specific Azure folder based on question type."""
        try:
            # Map folder types to actual Azure index filters or search parameters
            folder_mapping = {
                'policies': 'policies',
                'procedures': 'procedures', 
                'standards': 'standards',
                'projects': 'projects',
                'clients': 'clients'
            }
            
            folder_filter = folder_mapping.get(folder_type, '')
            
            # Perform Azure search with folder filtering
            search_results = self.search_client.search(
                search_text=question,
                top=10,
                select=["id", "filename", "content", "blob_url", "project_name", "folder"]
            )
            
            documents = []
            # Convert SearchItemPaged to list first, then process
            for result in search_results:
                documents.append({
                    'content': result.get('content', ''),
                    'filename': result.get('filename', ''),
                    'blob_url': result.get('blob_url', ''),
                    'score': result.get('@search.score', 0),
                    'project_name': result.get('project_name', ''),
                    'folder': result.get('folder', '')
                })
            
            return documents
            
        except Exception as e:
            # Ensure folder_type is a string for logging
            folder_name = str(folder_type) if not isinstance(folder_type, str) else folder_type
            logger.error(f"Folder search failed for {folder_name}", error=str(e))
            return []

    async def _generate_contextual_response(self, question: str, content: str, documents: List[Dict], analysis: Dict) -> Dict[str, Any]:
        """Generate response using DTCE documents as context."""
        try:
            folder_type = analysis.get('folder_type', 'unknown')
            
            contextual_prompt = f"""You are DTCE AI Assistant. The user asked a question that requires DTCE-specific information.

QUESTION: "{question}"
FOLDER TYPE: {folder_type}
CONTEXT FROM DTCE DOCUMENTS:
{content[:2000] if content else "No specific documents found"}

Please provide a helpful response using the DTCE document context when available. If the documents don't fully answer the question, supplement with your general knowledge while being clear about what comes from DTCE documents vs general knowledge.

Be conversational and helpful like ChatGPT, but grounded in the DTCE context."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are DTCE AI Assistant. Use DTCE document context when available, supplement with general knowledge when helpful."
                    },
                    {"role": "user", "content": contextual_prompt}
                ],
                temperature=0.2,
                max_tokens=1500
            )
            
            answer = response.choices[0].message.content
            
            return {
                'answer': answer,
                'sources': documents[:5],
                'confidence': 'dtce_contextual_response',
                'documents_searched': len(documents),
                'rag_type': 'contextual_ai_response',
                'search_method': f'{folder_type}_folder_search',
                'question_intent': analysis.get('question_intent', 'dtce_specific'),
                'folder_searched': folder_type
            }
            
        except Exception as e:
            logger.error("Contextual response generation failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    async def _handle_ai_error(self, question: str, error_details: str) -> Dict[str, Any]:
        """Handle errors gracefully with AI-generated responses."""
        try:
            error_prompt = f"""The user asked: "{question}"

I encountered a technical issue, but I should still try to be helpful. Please provide a useful response based on general knowledge, and apologize for any limitations."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful AI assistant. Even when you have technical issues, try to be useful."
                    },
                    {"role": "user", "content": error_prompt}
                ],
                temperature=0.2,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            
        except Exception:
            answer = f"I apologize, but I'm having technical difficulties right now. Your question '{question}' is important - please try again in a moment."
        
        return {
            'answer': answer,
            'sources': [],
            'confidence': 'error_recovery',
            'documents_searched': 0,
            'rag_type': 'error_response',
            'error_details': error_details
        }

    async def _determine_search_strategy(self, question: str) -> Dict[str, Any]:
        """Determine which of the 5 DTCE prompt categories this question fits."""
        try:
            routing_prompt = f"""Analyze this question and determine which DTCE prompt category it belongs to:

QUESTION: "{question}"

THE 5 DTCE PROMPT CATEGORIES:

1. **Policy Prompt (incl H&S)** - searches H&S, IT, Employment policy folders
   - Questions about company policies that employees MUST follow
   - Health & Safety procedures, compliance requirements
   - Examples: "What's our safety policy?", "COVID protocols?", "IT security requirements?"

2. **Technical & Admin Procedures Prompt** - searches H2H (How to Handbooks) procedures folder
   - How to do things at DTCE, best practices, not as strict as policies
   - Technical procedures, admin processes
   - Examples: "How do I use the wind speed spreadsheet?", "How to submit timesheets?", "Design workflow?"

3. **NZ Engineering Standards Prompt** - searches NZ Standards folder (PDFs)
   - Questions about specific engineering codes and standards
   - NZ building codes, structural standards
   - Examples: "NZS 3101 requirements?", "Wind load calculations?", "Seismic design standards?"

4. **Project Reference** - searches project folders for past project information
   - Questions about DTCE's past projects, project details, history
   - SPECIAL CASES:
     * "projects where clients don't like" = search for projects with complaints/issues/problems
     * "problem projects" = search for projects with rework/client complaints
     * "lessons learned" = search for projects with issues/failures
   - IMPORTANT: DTCE uses folder structure Projects/YYY where YYY = last 3 digits of year:
     * "projects in 2025" = search Projects/225/ folder
     * "projects in 2024" = search Projects/224/ folder  
     * "projects in 2023" = search Projects/223/ folder
     * "2022 projects" = search Projects/222/ folder
   - Examples: "Past precast projects?", "Projects in Auckland?", "What projects in 2025?", "2024 building projects?"

5. **Client Reference** - searches project folders for client information
   - Questions about client details, contact info, client project history
   - Examples: "Contact details for ABC Company?", "Projects with XYZ Client?", "Client relationship history?"

6. **General Engineering** - NO DTCE search needed, use general AI knowledge
   - General engineering questions not specific to DTCE
   - Examples: "How to design reinforced concrete?", "What is structural analysis?", "General wind engineering?"

SPECIAL ATTENTION FOR PROBLEM PROJECTS:
If the question asks about "clients don't like", "problem projects", "issues", "complaints", or "lessons learned", classify as "project_reference" but note this is seeking PROBLEMATIC projects specifically.

Respond with JSON:
{{
    "prompt_category": "policy|procedures|nz_standards|project_reference|client_reference|general_engineering",
    "topic_area": "brief description",
    "needs_dtce_search": true/false,
    "search_folders": ["folder1", "folder2"] or [],
    "search_intent": "normal|problem_projects|lessons_learned|client_issues",
    "reasoning": "why this category was chosen",
    "confidence": "high|medium|low"
}}"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a DTCE question classifier. Classify questions into the 5 DTCE prompt categories exactly as specified. Always respond with valid JSON."
                    },
                    {"role": "user", "content": routing_prompt}
                ],
                temperature=0.1,
                max_tokens=400
            )
            
            import json
            strategy = json.loads(response.choices[0].message.content)
            return strategy
            
        except Exception as e:
            logger.error("DTCE prompt categorization failed", error=str(e))
            return {
                "prompt_category": "general_engineering",
                "topic_area": "general inquiry", 
                "needs_dtce_search": False,
                "search_folders": [],
                "reasoning": "error fallback",
                "confidence": "low"
            }

    async def _perform_targeted_search(self, question: str, folder_filter: str) -> List[Dict]:
        """Perform search with folder-specific filtering."""
        try:
            # Enhance the question with folder-specific terms
            enhanced_query = f"{question} {folder_filter}"
            
            # Use the search client to find relevant documents
            search_results = self.search_client.search(
                search_text=enhanced_query,
                top=10,
                include_total_count=True
            )
            
            return list(search_results)
            
        except Exception as e:
            logger.error("Targeted search failed", error=str(e))
            return []

    async def _analyze_user_intent(self, question: str) -> Dict[str, Any]:
        """Use AI to understand what the user is actually asking for."""
        try:
            intent_prompt = f"""Analyze this engineering question and determine the user's intent:

QUESTION: "{question}"

Determine:
1. Is this asking for specific technical requirements/standards?
2. Is this asking for a direct factual answer?
3. Is this asking for general advice or exploration?
4. What type of response would best serve the user?

Respond with JSON:
{{
    "intent_type": "direct_technical|advisory_guidance|general_exploration",
    "requires_direct_answer": true/false,
    "question_focus": "brief description of what they're asking",
    "response_style": "factual_standards|comprehensive_advice|exploratory_discussion"
}}"""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an AI that understands engineering questions and user intent. Always respond with valid JSON."
                    },
                    {"role": "user", "content": intent_prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            import json
            intent = json.loads(response.choices[0].message.content)
            return intent
            
        except Exception as e:
            logger.error("Intent analysis failed", error=str(e))
            # Fallback: assume it needs comprehensive advice
            return {
                "intent_type": "advisory_guidance",
                "requires_direct_answer": False,
                "question_focus": "engineering question",
                "response_style": "comprehensive_advice"
            }

    async def _handle_basic_technical_question(self, question: str, retrieved_content: str, documents: List[Dict], intent: Dict = None) -> Dict[str, Any]:
        """Handle questions requiring direct technical answers based on AI intent analysis."""
        try:
            # Use AI-determined intent to craft the right response
            intent_type = intent.get('intent_type', 'direct_technical') if intent else 'direct_technical'
            question_focus = intent.get('question_focus', 'technical requirement') if intent else 'technical requirement'
            
            # Build a smart prompt based on the AI's understanding of user intent
            direct_prompt = f"""You are a senior structural engineer. The user is asking: "{question}"

The AI analysis indicates this is a {intent_type} question focused on: {question_focus}

PROVIDE A DIRECT, PRACTICAL ANSWER THAT:
1. Directly answers what they're asking for
2. Gives specific values, requirements, or specifications from NZ Standards
3. References exact clause numbers when applicable
4. Is concise but complete

AVAILABLE CONTEXT:
{retrieved_content[:1000] if retrieved_content else "No specific documents found"}

For concrete cover questions specifically, use NZS 3101:2006 requirements:
- Beams/Columns: 20mm minimum
- Slabs: 15mm minimum  
- Foundations: 40mm minimum
- Walls: 15mm (interior), 20mm (exterior)
- Environmental adjustments: +5-35mm based on exposure class

Be direct and helpful - answer exactly what they asked."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a practical structural engineer who gives direct, accurate answers to technical questions."
                    },
                    {"role": "user", "content": direct_prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            answer = response.choices[0].message.content
            
            return {
                'answer': answer,
                'sources': documents[:3] if documents else [],
                'confidence': 'ai_intent_based',
                'documents_searched': len(documents),
                'rag_type': 'intelligent_direct_answer',
                'search_method': 'ai_intent_analysis',
                'response_style': intent.get('response_style', 'direct_technical') if intent else 'direct_technical',
                'detected_intent': intent_type
            }
            
        except Exception as e:
            logger.error("AI-powered technical question handler failed", error=str(e))
            # Let the AI handle the fallback too - no hardcoded answers!
            try:
                fallback_prompt = f"""The user asked: "{question}"

Even though I couldn't access the full document database, I'm a knowledgeable engineering AI. Please provide a helpful response based on general engineering knowledge and NZ Standards that I'm trained on.

Be helpful, accurate, and professional. If I don't have specific information, I'll be honest about limitations but still provide useful guidance."""

                fallback_response = await self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a knowledgeable structural engineer AI assistant. Provide helpful responses based on your training knowledge."
                        },
                        {"role": "user", "content": fallback_prompt}
                    ],
                    temperature=0.2,
                    max_tokens=800
                )
                
                answer = fallback_response.choices[0].message.content
                
            except Exception as fallback_error:
                logger.error("Even AI fallback failed", error=str(fallback_error))
                answer = f"I apologize, but I'm having technical difficulties right now. Your question about '{question}' is important - please try again in a moment or contact a senior engineer for immediate assistance."
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'ai_fallback',
                'documents_searched': 0,
                'rag_type': 'intelligent_fallback',
                'detected_intent': 'fallback_handling'
            }

    async def _handle_database_search(self, question: str, analysis: Dict) -> Dict[str, Any]:
        """Handle client/builder database searches."""
        try:
            search_keywords = analysis.get('search_keywords', [])
            
            # Search the client/builder database
            database_results = await self._search_client_builder_database(search_keywords)
            
            database_prompt = f"""The user asked: "{question}"

SEARCH RESULTS FROM DTCE CLIENT/BUILDER DATABASE:
{database_results}

Please provide a helpful response that:
1. Lists relevant clients/builders found
2. Includes contact details when available
3. Mentions project history and performance
4. Provides recommendations based on the search criteria

Be specific and helpful."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are DTCE AI Assistant helping with client and builder information searches."
                    },
                    {"role": "user", "content": database_prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            return {
                'answer': response.choices[0].message.content,
                'sources': [],
                'confidence': 'database_search',
                'search_method': 'client_builder_database',
                'rag_type': 'database_response'
            }
            
        except Exception as e:
            logger.error("Database search failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    async def _handle_web_search(self, question: str, analysis: Dict) -> Dict[str, Any]:
        """Handle external web searches for forums, products, specifications."""
        try:
            search_keywords = analysis.get('search_keywords', [])
            
            # Search external web sources
            web_results = await self._search_external_web(search_keywords, question)
            
            web_prompt = f"""The user asked: "{question}"

WEB SEARCH RESULTS:
{web_results}

Please provide a comprehensive response that:
1. Summarizes relevant findings from the web search
2. Includes specific links when available
3. Prioritizes reputable engineering sources
4. Provides alternative options when relevant

Be helpful and include actionable information."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are DTCE AI Assistant helping with external web research for engineering topics."
                    },
                    {"role": "user", "content": web_prompt}
                ],
                temperature=0.3,
                max_tokens=1200
            )
            
            return {
                'answer': response.choices[0].message.content,
                'sources': [],
                'confidence': 'web_search',
                'search_method': 'external_web_search',
                'rag_type': 'web_enhanced_response'
            }
            
        except Exception as e:
            logger.error("Web search failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    async def _handle_dtce_document_search(self, question: str, analysis: Dict) -> Dict[str, Any]:
        """Handle DTCE document searches with enhanced features."""
        try:
            folder_type = analysis.get('folder_type', 'general')
            needs_job_numbers = analysis.get('needs_job_numbers', False)
            needs_links = analysis.get('needs_links', False)
            
            logger.info(f"Searching DTCE {folder_type} folder for: {question}")
            
            # Perform Azure search in the specific folder
            documents = await self._search_specific_folder(question, folder_type)
            retrieved_content = self._format_documents_content(documents)
            
            # Enhanced prompt for different needs
            if needs_job_numbers:
                enhanced_prompt = f"""The user asked: "{question}"

CONTEXT FROM DTCE PROJECT DOCUMENTS:
{retrieved_content[:2000] if retrieved_content else "No specific documents found"}

This question requires project job numbers and references. Please provide:
1. Specific job numbers related to the keywords
2. Project descriptions and scope details
3. SuiteFiles folder paths when available
4. Similar projects that match the criteria

Format job numbers clearly (e.g., "Job #12345") and provide actionable project references."""
                
            elif needs_links:
                enhanced_prompt = f"""The user asked: "{question}"

CONTEXT FROM DTCE DOCUMENTS:
{retrieved_content[:2000] if retrieved_content else "No specific documents found"}

This question requires document links and templates. Please provide:
1. Specific template names and locations
2. SuiteFiles folder paths
3. Direct access instructions
4. Alternative sources if DTCE documents not available

Be specific about how to access the requested documents."""
                
            else:
                enhanced_prompt = f"""The user asked: "{question}"

CONTEXT FROM DTCE DOCUMENTS:
{retrieved_content[:2000] if retrieved_content else "No specific documents found"}

CRITICAL INSTRUCTION: First evaluate if the retrieved documents actually answer the user's question.

If the documents are RELEVANT and helpful:
- Provide a comprehensive response using the DTCE document context
- Include specific details, clause numbers, requirements when available
- Reference the document names and SuiteFiles links

If the documents are IRRELEVANT or don't answer the question:
- Acknowledge that the specific information wasn't found in DTCE documents
- Provide general guidance based on your knowledge
- Suggest alternative approaches or where they might find the information
- Be honest about what information is not available

Example for irrelevant results:
"I searched DTCE's policy documents but didn't find a specific wellness policy. The search returned some COVID-19 and environmental policies, but these don't address general employee wellness programs. 

For comprehensive employee wellness policies, DTCE may need to:
1. Develop a dedicated wellness policy document
2. Consult HR best practices for wellness programs
3. Check if wellness guidelines are included in other HR documents

I'd recommend contacting DTCE's HR department directly for current wellness policy information."

Be helpful, honest, and actionable in your response."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are DTCE AI Assistant. Evaluate document relevance first, then provide honest, helpful responses. If documents don't match the user's question, acknowledge this and provide alternative guidance."
                    },
                    {"role": "user", "content": enhanced_prompt}
                ],
                temperature=0.2,
                max_tokens=1500
            )
            
            return {
                'answer': response.choices[0].message.content,
                'sources': documents[:5],
                'confidence': 'enhanced_dtce_search',
                'documents_searched': len(documents),
                'rag_type': 'enhanced_document_response',
                'search_method': f'{folder_type}_enhanced_search',
                'needs_job_numbers': needs_job_numbers,
                'needs_links': needs_links,
                'folder_searched': folder_type
            }
            
        except Exception as e:
            logger.error("Enhanced DTCE document search failed", error=str(e))
            return await self._handle_ai_error(question, str(e))

    async def _search_client_builder_database(self, keywords: List[str]) -> str:
        """Search the client/builder database (placeholder for actual implementation)."""
        # This would integrate with your actual database
        return f"""DATABASE SEARCH RESULTS for keywords: {keywords}
        
BUILDERS (Recent 3 years, good performance):
- ABC Construction Ltd (Contact: John Smith, 04-123-4567)
  Specialties: Steel retrofits, brick building upgrades
  Recent Projects: Job #12345 (Steel structure retrofit, brick building)
  Performance: Excellent, minimal construction issues
  
- Wellington Steel Works (Contact: Jane Doe, 04-987-6543)
  Specialties: Structural steel, heritage building retrofits
  Recent Projects: Job #12346 (Heritage building strengthening)
  Performance: Very good, reliable execution

CLIENTS:
- Wellington City Council (Contact: Planning Dept, 04-555-1234)
- Seatoun Development Ltd (Contact: Mike Brown, 04-444-5678)
- Various residential clients in Seatoun area

PROJECT MATCHES:
- Job #12347: Steel cantilever design, corner windows (similar scope)
- Job #12348: Double cantilever structural support system

Note: For full database access, contact DTCE admin."""

    async def _search_external_web(self, keywords: List[str], question: str) -> str:
        """Search external web sources (placeholder for actual implementation)."""
        # This would integrate with Bing Search API, Google Custom Search, etc.
        return f"""WEB SEARCH RESULTS for: {keywords}

ENGINEERING FORUMS & DISCUSSIONS:
- StructuralEng.org: Discussions on {question}
- SESOC (NZ): Professional engineering guidelines
- Engineering.com: Technical forum threads

PRODUCT SPECIFICATIONS:
- NZ Building Suppliers: Relevant product catalogs
- Specialist Suppliers: Contact details and specifications
- Price lists and availability information

NZ STANDARDS & REFERENCES:
- Standards New Zealand: Official NZ building codes
- MBIE Building Performance: Current guidelines
- Professional engineering resources

LINKS:
[Placeholder - Real implementation would include actual URLs]

Note: For live web search, integrate with search APIs."""

    def _create_consistent_search_query(self, question: str) -> str:
        """Create consistent search terms for similar questions to ensure same documents are found."""
        
        # Normalize the question to lowercase for consistent matching
        question_lower = question.lower().strip()
        
        # Define consistent search term mappings for common question variations
        consistent_mappings = {
            # Wellness/Wellbeing Policy variations
            'wellness': ['wellness policy', 'wellbeing policy', 'wellness', 'wellbeing', 'employee wellness', 'staff wellbeing'],
            'wellbeing': ['wellness policy', 'wellbeing policy', 'wellness', 'wellbeing', 'employee wellness', 'staff wellbeing'],
            'wellness policy': ['wellness policy', 'wellbeing policy', 'employee wellness policy'],
            'wellbeing policy': ['wellness policy', 'wellbeing policy', 'employee wellness policy'],
            
            # Health & Safety variations
            'health and safety': ['health safety policy', 'H&S policy', 'health and safety'],
            'h&s': ['health safety policy', 'H&S policy', 'health and safety'],
            'safety policy': ['health safety policy', 'H&S policy', 'safety'],
            
            # Project variations
            'project 225': ['project 225', '225', 'project job 225'],
            'project 224': ['project 224', '224', 'project job 224'],
            'project 223': ['project 223', '223', 'project job 223'],
            
            # Client issues variations
            'clients don\'t like': ['client complaints', 'client issues', 'problem projects', 'client dissatisfaction', 'rework'],
            'client complaints': ['client complaints', 'client issues', 'problem projects', 'client dissatisfaction'],
            'problem projects': ['client complaints', 'client issues', 'problem projects', 'client dissatisfaction', 'rework'],
            
            # NZ Standards variations  
            'nzs': ['NZ standards', 'New Zealand standards', 'building codes'],
            'clear cover': ['concrete cover', 'clear cover requirements', 'concrete protection'],
            'beam design': ['structural beam', 'beam detailing', 'beam requirements'],
            
            # Template variations
            'ps1 template': ['PS1 form', 'producer statement', 'PS1 template'],
            'timber beam': ['timber design', 'timber beam spreadsheet', 'timber calculations'],
        }
        
        # Check for exact matches first
        for key, search_terms in consistent_mappings.items():
            if key in question_lower:
                # Return the primary search term (first in list) for consistency
                return search_terms[0]
        
        # If no specific mapping found, return the original question
        return question
