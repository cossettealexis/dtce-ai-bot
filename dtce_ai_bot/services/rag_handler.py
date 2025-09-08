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

logger = structlog.get_logger(__name__)


class RAGHandler:
    """Handles RAG processing with enhanced semantic search and intent recognition."""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        # Initialize semantic search with intelligent routing
        self.semantic_search = SemanticSearchService(search_client, openai_client, model_name)
        self.folder_structure = FolderStructureService()
        # Initialize query normalizer for better semantic search consistency
        self.query_normalizer = QueryNormalizer(openai_client, model_name)
    
    async def process_rag_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        INTELLIGENT FOLDER-ROUTED SEARCH:
        
        1. Classify user intent and route to appropriate folder
        2. Execute semantic search within targeted folder category  
        3. Retrieve and rank relevant documents from right context
        4. Generate specialized answer based on document category
        """
        try:
            logger.info("Processing question with intelligent folder routing", question=question)
            
            # STEP 1: Normalize query for consistent semantic search results
            logger.info("Normalizing query for better semantic search")
            normalized_result = await self.query_normalizer.normalize_query(question)
            
            # Use normalized query for semantic search
            search_query = normalized_result['primary_search_query']
            logger.info("Query normalized", 
                       original=question,
                       normalized=search_query,
                       confidence=normalized_result['confidence'])
            
            # STEP 2: Use intelligent semantic search with folder routing
            documents = await self.semantic_search.search_documents(search_query, project_filter)
            
            logger.info("Intelligent search results", 
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
                    'search_method': 'ai_semantic_with_full_content',
                    'response_style': 'chatgpt_like_conversation',
                    'query_normalization': {
                        'original_query': question,
                        'normalized_query': search_query,
                        'confidence': normalized_result['confidence'],
                        'semantic_concepts': normalized_result.get('semantic_concepts', []),
                        'document_terms': normalized_result.get('document_terms', []),
                        'method': normalized_result.get('method', 'unknown'),
                        'reasoning': normalized_result.get('reasoning', '')
                    }
                })
                
                return result
            else:
                # No documents found - provide general response with normalization info
                result = await self._handle_no_documents_found(question)
                result['query_normalization'] = {
                    'original_query': question,
                    'normalized_query': search_query,
                    'confidence': normalized_result['confidence'],
                    'semantic_concepts': normalized_result.get('semantic_concepts', []),
                    'document_terms': normalized_result.get('document_terms', []),
                    'method': normalized_result.get('method', 'unknown'),
                    'reasoning': normalized_result.get('reasoning', '')
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
        
        # Filter out documents from excluded folders (simple direct filtering)
        filtered_documents = []
        excluded_terms = ['superseded', 'superceded', 'archive', 'obsolete', 'old', 'backup', 'temp', 'draft', 'trash']
        
        for doc in documents:
            blob_name = doc.get('blob_name', '') or doc.get('filename', '')
            
            # Check if document should be excluded
            should_exclude = any(term in blob_name.lower() for term in excluded_terms)
            
            if not should_exclude:
                filtered_documents.append(doc)
            else:
                logger.debug("Excluded document from superseded/archive folder", blob_name=blob_name)
        
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
            suitefiles_link = self._get_safe_suitefiles_url(blob_url)
            
            # Use FULL content for better RAG processing
            max_content_length = 3000  # Much longer content for comprehensive answers
            formatted_content = content[:max_content_length]
            if len(content) > max_content_length:
                formatted_content += "... [Content continues]"
            
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
            suitefiles_link = self._get_safe_suitefiles_url(blob_url)
            
            # Extract project info using our consistent method
            extracted_project = self._extract_project_name_from_blob_url(blob_url)
            
            # Use FULL content for better RAG - don't truncate unless absolutely necessary
            max_content_length = 3000  # Increased from 600 to 3000 characters
            formatted_content = content[:max_content_length]
            if len(content) > max_content_length:
                formatted_content += "... [Content continues]"
            
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
        
        # Use GPT knowledge fallback with conversational tone
        try:
            fallback_prompt = f"""You are DTCE AI Assistant. A user asked: "{question}"

I searched our DTCE document database but couldn't find specific documents that directly answer this question.

Please provide a helpful, conversational response that:
1. Acknowledges I couldn't find specific DTCE documents on this topic
2. If it's a general business/engineering question, provide helpful general guidance
3. Suggest alternative ways the user could find this information at DTCE
4. Be friendly and professional, like a helpful colleague

Keep the response conversational and practical. Don't just say "I don't know" - try to be genuinely helpful."""
            
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are DTCE AI Assistant, a helpful and friendly AI that assists DTCE employees. When you can't find specific documents, you provide helpful guidance and suggestions in a conversational manner."
                    },
                    {"role": "user", "content": fallback_prompt}
                ],
                temperature=0.3,
                max_tokens=600
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
                temperature=0.3
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
- **Content Preview:** {content[:800]}...

"""
                    else:
                        # Don't show project info for non-project documents
                        doc_result = f"""DOCUMENT FOUND:
- **File Name:** {filename}
- **SuiteFiles Link:** {suitefiles_link}
- **Content Preview:** {content[:800]}...

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
        """Process RAG query with comprehensive conversational AI like ChatGPT."""
        try:
            # Build a comprehensive ChatGPT-style prompt for true RAG
            prompt = f"""You are DTCE AI Assistant, a knowledgeable and helpful AI that helps DTCE employees with company information. You have access to DTCE's internal documents and can provide detailed, conversational answers based on the actual content.

USER QUESTION: "{question}"

INSTRUCTIONS FOR RESPONSE:
1. Act like ChatGPT - be conversational, helpful, and comprehensive
2. Read through ALL the document content below and synthesize a complete answer
3. Provide specific details, quotes, procedures, requirements, and numbers from the documents
4. If the user asks about a policy, explain what it says in detail, not just that it exists
5. If they ask about procedures, walk them through the actual steps
6. Give actionable advice and practical information
7. Be thorough but well-organized with clear sections
8. Include SuiteFiles links for reference at the end
9. If information spans multiple documents, synthesize it all together

CONVERSATION TONE:
- Friendly and professional
- Direct and informative
- Like talking to a knowledgeable colleague
- Provide context and background when helpful

Here are the relevant DTCE documents I found:

{retrieved_content}

Now, based on the document content above, provide a comprehensive, conversational answer to the user's question. Structure your response clearly and include all relevant details from the documents:"""

            # Generate comprehensive response with higher token limit
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are DTCE AI Assistant, a helpful and knowledgeable AI that provides comprehensive, conversational answers based on company documents. Always give thorough, well-structured responses with specific details from the document content."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Slightly higher for more natural conversation
                max_tokens=1500   # Increased from 800 to allow comprehensive responses
            )
            
            answer = response.choices[0].message.content
            
            # Format sources
            sources = []
            for doc in documents[:5]:
                filename = doc.get('filename', 'Unknown')
                blob_url = self._get_blob_url_from_doc(doc)
                suitefiles_link = self._get_safe_suitefiles_url(blob_url)
                
                source_entry = {
                    'filename': filename,
                    'excerpt': doc.get('content', '')[:200] + '...' if doc.get('content') else 'Content not available'
                }
                
                if suitefiles_link:
                    source_entry['link'] = suitefiles_link
                    
                sources.append(source_entry)
            
            # This was the simple prompt system - but we want to use the advanced one below
            # return {
            #     'answer': answer,
            #     'sources': sources,
            #     'confidence': 'high' if len(documents) > 0 else 'low',
            #     'documents_searched': len(documents)
            # }
            
            # Build the advanced prompt with formatting instructions
            prompt = "You are an expert assistant helping with DTCE engineering document queries.\n\n"
            prompt += "- Example: 'DTCE has worked with [Client] on the following projects: [list with details]'\n\n"
            
            prompt += "SMART FOLDER UNDERSTANDING - Let the semantic search find everything, then be intelligent:\n\n"
            prompt += "🔍 **ANALYZE THE QUESTION TYPE**:\n"
            prompt += "- **Policy questions** (safety, compliance, must follow): Prioritize H&S/, IT/, Employment/, Quality/ folder documents\n"
            prompt += "- **Procedure questions** (how to, best practice): Prioritize H2H/, How-to/, Procedure/ folder documents\n"
            prompt += "- **Standards questions** (codes, NZS, regulations): Prioritize Engineering/, Standards/, NZ*/ folder documents\n"
            prompt += "- **Project questions** (past work, examples): Prioritize Project/, 22*/, client/ folder documents\n"
            prompt += "- **Client questions** (contacts, history): Look in Project/ folders for client information\n\n"
            
            prompt += "**BE SMART ABOUT RELEVANCE**:\n"
            prompt += "- If user asks about H&S policy, focus on documents from H&S folders even if other documents mention safety\n"
            prompt += "- If user asks about past precast projects, focus on Project/ folder documents about precast work\n"
            prompt += "- If user asks about wind load calculations, prioritize Standards/ and H2H/ documents over random project mentions\n"
            prompt += "- Use your intelligence to determine what's actually answering their question vs just keyword matches\n\n"
            
            prompt += "Based on your determination, follow these linking guidelines:\n\n"
            prompt += "IF SUITEFILES KNOWLEDGE (especially if contains \"we\"/\"our\"/\"DTCE\"): Use the retrieved SuiteFiles content and ALWAYS include SuiteFiles links\n"
            prompt += "IF GENERAL KNOWLEDGE ONLY: Provide general engineering knowledge and include relevant online links\n"
            prompt += "IF BOTH: Include both SuiteFiles links for relevant documents AND online links for general knowledge aspects\n"
            prompt += "IF NEITHER/UNCLEAR: Default to providing BOTH SuiteFiles links AND online resources\n\n"
            prompt += "Your task is to:\n"
            prompt += "1. FIRST determine the user's intent based on language indicators above\n"
            prompt += "2. Analyze the retrieved content I'm providing below from SuiteFiles\n"
            prompt += "3. **EVALUATE RELEVANCE**: Determine if the primary search results actually help answer the user's question\n"
            prompt += "4. **IF PRIMARY RESULTS ARE GOOD**: Use them to provide a comprehensive answer\n"
            prompt += "5. **CRITICAL FORMATTING RULE**: Format your response with proper paragraph breaks and readable structure. DO NOT dump everything in one long run-on sentence or paragraph!\n"
            prompt += "6. **Use intelligent judgment**: Include 'Alternative that might be helpful' and 'General Engineering Guidance' sections only when they add genuine value to the user's question\n"
            prompt += "7. **IF PRIMARY RESULTS DON'T MAKE SENSE**: Provide intelligent alternatives:\n"
            prompt += "   - Look through ALL the retrieved content for any documents that might be relevant (even from 'ignored' folders)\n"
            prompt += "   - Label these clearly as 'Alternative from SuiteFiles:'\n"
            prompt += "   - Also provide 'General Engineering Guidance:' using your knowledge\n"
            prompt += "   - Explain why the primary search wasn't perfect\n"
            prompt += "8. For COMPLEX ANALYSIS QUESTIONS (scenarios, lessons learned, cost insights, comparisons):\n"
            prompt += "   - Search across multiple projects to find patterns and examples\n"
            prompt += "   - Aggregate information from similar projects or situations\n"
            prompt += "   - Summarize trends, common issues, and solutions\n"
            prompt += "   - Provide specific project examples with SuiteFiles links\n"
            prompt += "   - Extract quantitative data when available (costs, timelines, specifications)\n"
            prompt += "7. Apply the correct linking strategy consistently throughout your response\n"
            prompt += "8. Always be comprehensive - if in doubt, include both types of resources\n\n"
            prompt += "SPECIAL HANDLING FOR PROJECT & CLIENT QUERIES (Most Complex):\n"
            prompt += "Project data is less structured, so use these strategies:\n\n"
            prompt += "**For PROJECT REFERENCE queries:**\n"
            prompt += "- Look for project numbers (225xxx, 224xxx, etc.) to identify specific projects\n"
            prompt += "- Extract client names, addresses, project scope from document names and content\n"
            prompt += "- Look for quantitative data: total hours, costs, timelines, specifications\n"
            prompt += "- Identify lessons learned, challenges encountered, solutions used\n"
            prompt += "- Compare similar projects to find patterns and best practices\n"
            prompt += "- Include folder structure context: Projects/[year]/[project_number]/[document_type]\n\n"
            prompt += "**For CLIENT REFERENCE queries:**\n"
            prompt += "- Aggregate all projects for a specific client across multiple years\n"
            prompt += "- Look for contact details in project documents\n"
            prompt += "- Summarize relationship history and project types\n"
            prompt += "- Include most recent contact information found\n\n"
            prompt += "**Project Data Structure Understanding:**\n"
            prompt += "- DTCE uses folder structure: Projects/[3-digit year]/[6-digit project number]/[document folders]\n"
            prompt += "- Example: Projects/225/225123/01 Admin Documents/ contains project admin files\n"
            prompt += "- Example: Projects/224/224567/03 Drawings/ contains project drawings\n"
            prompt += "- Extract project details from folder names and document titles when content is limited\n\n"
            prompt += "Reference Example (rag.txt)\n"
            prompt += "You may refer to the following example file — rag.txt — which contains example question-answer formats showing how the AI could respond to different structural engineering and project-related queries.\n"
            prompt += "However, do not copy from this file or rely on its content directly. It is only a reference to help you understand the style and expectations of the response. You must still follow the actual question, the user's intent, and the retrieved documents.\n\n"
            prompt += "Retrieved content from SuiteFiles:\n" + retrieved_content + "\n\n"
            
            prompt += "==== MANDATORY RESPONSE FORMAT ====\n"
            prompt += "CRITICAL: Format your response with proper paragraph breaks and readable structure. DO NOT dump everything in one long paragraph!\n\n"
            prompt += "Use this format:\n"
            prompt += "1. Start with a clear introductory sentence\n"
            prompt += "2. Break information into separate paragraphs for readability\n"
            prompt += "3. Use bullet points or numbered lists when listing multiple items\n"
            prompt += "4. Add line breaks between different concepts or sections\n\n"
            prompt += "SPECIAL RULE FOR PROJECT QUERIES: When users ask for 'past projects', 'project examples', or 'projects about X':\n"
            prompt += "- ALWAYS extract and mention the PROJECT NUMBER/JOB NUMBER from document names or content\n"
            prompt += "- Format as: 'Project 224001', 'Job 22345', 'Project Number 23042', etc.\n"
            prompt += "- Users need specific project references they can look up, not generic technical documents\n\n"
            prompt += "RESPONSE STRUCTURE:\n"
            prompt += "1. Start with your answer (NO document references first)\n"
            prompt += "2. Break content into readable paragraphs with proper spacing\n"
            prompt += "3. ALWAYS provide comprehensive sources section with this EXACT format:\n\n"
            prompt += "**Primary Sources:** (If documents contain relevant information)\n"
            prompt += "- **[Document Name] (Project XXXXX)**: [QUOTE specific procedures, requirements, dates, numbers, or key content from this document. For example: 'Contains the lockout/tagout procedure requiring 3-step verification' or 'Specifies infection control measures implemented April 1, 2021 including mandatory temperature checks' or 'Lists the required PPE for electrical work: safety glasses, hard hat, and insulated gloves']\n"
            prompt += "  SuiteFiles Link: [[Document Filename]](EXACT_URL_FROM_LINK_FIELD)\n"
            prompt += "  NOTE: If a document shows 'Project: Project XXXXX' in the retrieved content, include the project number in parentheses after the document name. If no project information is shown, just use **[Document Name]**:\n\n"
            prompt += "**Alternative that might be helpful:** (Include only if there are other relevant documents that add useful context)\n"
            prompt += "- **[Document Name] (Project XXXXX)**: [QUOTE or describe specific sections/content that provide background or related information. For example: 'Section 3.2 covers site safety protocols for contaminated soil' or 'Contains the emergency contact procedures and evacuation routes for the Auckland office']\n"
            prompt += "  SuiteFiles Link: [[Document Filename]](EXACT_URL_FROM_LINK_FIELD)\n"
            prompt += "  NOTE: Include project number if available in the retrieved content\n\n"
            prompt += "**General Engineering Guidance:** (Include when relevant standards, codes, or guidance apply)\n"
            prompt += "- [Resource]: [SPECIFIC standards, codes, or guidance that directly relate to the question]\n\n"
            prompt += "EXAMPLES OF GOOD vs BAD descriptions:\n"
            prompt += "BAD: 'Details DTCE's commitment to health and safety'\n"
            prompt += "GOOD: 'Specifies the updated infection control measures effective April 1, 2021, including site access restrictions, mandatory hand sanitizing, and social distancing requirements for project meetings'\n"
            prompt += "BAD: 'Contains safety information'\n"
            prompt += "GOOD: 'Section 4.1 outlines the electrical safety lockout/tagout procedure requiring three-point verification and supervisor sign-off before re-energizing circuits'\n\n"
            prompt += "NEVER use generic phrases like 'commitment to', 'outlines', 'details', 'highlights' - instead describe the ACTUAL CONTENT!\n\n"
            prompt += "FORMATTING EXAMPLES - GOOD vs BAD:\n"
            prompt += "BAD FORMATTING (one long paragraph):\n"
            prompt += "The wellness policy at Don Thomson Consulting Engineers (DTCE) is detailed in the \"Health and Safety Policy\" document. Here is the specific content related to the wellness policy: \"DTCE Ltd. takes its Health and Safety responsibilities very seriously and is continuing its efforts to eliminate, isolate, and minimise risk. Safety in Design has become a priority for DTCE, and we continue to liaise with clients and designers throughout the entire design process to consider all relevant risk associated with projects we undertake.\" Additionally, the document states: \"DTCE is committed to the protection of its employees, its property and other people from accidental injury or damage from work conditions.\"\n\n"
            prompt += "GOOD FORMATTING (proper paragraph breaks):\n"
            prompt += "The wellness policy at Don Thomson Consulting Engineers (DTCE) is detailed in the \"Health and Safety Policy\" document.\n\n"
            prompt += "Key aspects of DTCE's wellness policy include:\n\n"
            prompt += "- **Risk Management**: DTCE takes its Health and Safety responsibilities very seriously and is continuing its efforts to eliminate, isolate, and minimise risk.\n\n"
            prompt += "- **Safety in Design**: This has become a priority for DTCE, with ongoing liaison with clients and designers throughout the entire design process to consider all relevant risk associated with projects.\n\n"
            prompt += "- **Employee Protection**: DTCE is committed to the protection of its employees, its property and other people from accidental injury or damage from work conditions.\n\n"
            prompt += "CRITICAL: ONLY use the EXACT SuiteFiles links provided in the retrieved content above. DO NOT construct your own links or modify the provided URLs. If a document is mentioned in the retrieved content, use its exact link. If no link is provided for a document in the retrieved content, do not include it in your sources.\n\n"
            prompt += "CRITICAL RULES FOR COMPREHENSIVE RESPONSES:\n"
            prompt += "1. NEVER write '[Link not provided in the retrieved content]' - this is FORBIDDEN\n"
            prompt += "2. NEVER write 'SuiteFiles Link: [link]' - this is FORBIDDEN\n"
            prompt += "3. Include 'Primary Sources' section if any relevant documents are retrieved\n"
            prompt += "4. Include 'Alternative that might be helpful' ONLY if there are genuinely useful related documents\n"
            prompt += "5. Include 'General Engineering Guidance' ONLY when relevant standards or codes apply\n"
            prompt += "6. Provide DETAILED responses but don't force sections that don't add value\n"
            prompt += "7. ALWAYS use Markdown link format: [Document Filename](exact_url)\n"
            prompt += "8. Extract the filename from the document name and use it as the link text\n"
            prompt += "9. If you cannot find a 'Link: https://...' for a document, DO NOT include that document\n"
            prompt += "10. EXAMPLE: If you see 'DOCUMENT: Health & Safety Policy.pdf' and 'Link: https://dtcestorage.blob.core.windows.net/suitefiles/Health%20%26%20Safety%20Policy.pdf', format as: [Health & Safety Policy.pdf](https://dtcestorage.blob.core.windows.net/suitefiles/Health%20%26%20Safety%20Policy.pdf)\n\n"
            prompt += "LINK EXAMPLES - DO THIS:\n"
            prompt += "CORRECT: SuiteFiles Link: [Health & Safety Policy.pdf](https://dtcestorage.blob.core.windows.net/suitefiles/Health%20%26%20Safety%20Policy.pdf)\n"
            prompt += "WRONG: SuiteFiles Link: [link]\n"
            prompt += "WRONG: SuiteFiles Link: https://dtcestorage.blob.core.windows.net/suitefiles/Health%20%26%20Safety%20Policy.pdf\n"
            prompt += "WRONG: SuiteFiles Link: [Link not provided in the retrieved content]\n\n"
            prompt += "ABSOLUTE RULE - NO DOCUMENT HALLUCINATION:\n"
            prompt += "You MUST ONLY reference documents that appear in the 'Retrieved content from SuiteFiles' section above.\n"
            prompt += "Each document in the retrieved content starts with 'DOCUMENT: [exact filename]'.\n"
            prompt += "You are FORBIDDEN from inventing, creating, or mentioning any document names that do not appear in the retrieved content.\n"
            prompt += "If you reference a document, it MUST be copied EXACTLY from a 'DOCUMENT: [filename]' line above.\n"
            prompt += "DO NOT create or assume the existence of any documents that are not explicitly listed in the retrieved content.\n\n"
            
            # Send the full prompt directly to GPT instead of using the secondary prompt system
            try:
                response = await self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1500,
                    temperature=0.3
                )
                
                answer = response.choices[0].message.content.strip()
                
            except Exception as e:
                logger.error("GPT response generation failed", error=str(e))
                answer = f"I encountered an error generating the response: {str(e)}"
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents) if documents else [],
                'confidence': 'high',  # High confidence for comprehensive RAG responses
                'documents_searched': len(documents),
                'rag_type': 'comprehensive_conversational_rag',
                'response_type': 'detailed_synthesis'
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
                suitefiles_url = self._get_safe_suitefiles_url(blob_url)
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
