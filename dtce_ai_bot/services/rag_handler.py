"""
RAG (Retrieval-Augmented Generation) Handler for DTCE AI Bot
UNIFIED SEMANTIC SEARCH FLOW with Folder Structure Awareness
"""

import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
from .folder_structure_service import FolderStructureService

logger = structlog.get_logger(__name__)


class RAGHandler:
    """Handles RAG processing with unified semantic search flow and folder structure awareness."""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        self.folder_service = FolderStructureService()
    
    async def process_rag_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        UNIFIED SEMANTIC SEARCH FLOW with Folder Structure Awareness:
        
        1. Interpret user question to understand folder context
        2. Search using folder-aware filtering
        3. Retrieve relevant documents with proper context
        4. Generate answer with folder structure understanding
        """
        try:
            logger.info("Processing question with folder structure awareness", question=question)
            
            # STEP 1: Interpret user query for folder context
            folder_context = self.folder_service.interpret_user_query(question)
            
            # STEP 2: Enhanced search with folder awareness
            enhanced_query = self.folder_service.enhance_search_query(question, folder_context)
            folder_filter = self.folder_service.get_folder_filter_query(folder_context)
            
            logger.info("Folder-aware search context",
                       original_query=question,
                       enhanced_query=enhanced_query,
                       query_type=folder_context["query_type"],
                       suggested_folders=folder_context["suggested_folders"],
                       folder_filter=folder_filter)
            
            # STEP 3: Search with folder context
            documents = await self._search_documents_with_folder_context(
                enhanced_query, 
                project_filter, 
                folder_context,
                folder_filter
            )
            
            logger.info("Folder-aware search results", 
                       total_documents=len(documents),
                       sample_filenames=[doc.get('filename', 'Unknown') for doc in documents[:3]])
            
            # STEP 4: Generate response with folder context
            if documents:
                # Format context information for AI
                ai_folder_context = self.folder_service.format_folder_context_for_ai(folder_context)
                
                # Generate answer with folder understanding
                retrieved_content = self._format_documents_with_folder_context(documents, folder_context)
                
                # Use the complete intelligent prompt system instead of simple prompt
                result = await self._process_rag_with_full_prompt(question, retrieved_content, documents)
                
                # Add folder context to the result
                result.update({
                    'rag_type': 'folder_aware_semantic_search',
                    'folder_context': folder_context,
                    'query_interpretation': {
                        'type': folder_context['query_type'],
                        'suggested_folders': folder_context['suggested_folders'],
                        'year_context': folder_context.get('year_context'),
                        'enhanced_query': enhanced_query
                    }
                })
                
                return result
            else:
                # No documents found - provide general response with folder guidance
                return await self._handle_no_documents_with_folder_guidance(question, folder_context)
                
        except Exception as e:
            logger.error("Folder-aware RAG processing failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while processing your question: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'rag_type': 'error'
            }
    
    async def _search_documents_with_folder_context(
        self, 
        query: str, 
        project_filter: Optional[str], 
        folder_context: Dict[str, Any],
        folder_filter: Optional[str]
    ) -> List[Dict]:
        """Search documents with folder structure awareness."""
        
        # Start with semantic search
        documents = await self._search_documents(query, project_filter, use_semantic=True, folder_filter=folder_filter)
        
        # If semantic search doesn't find enough results, try keyword search
        if len(documents) < 5:
            logger.info("Enhancing folder-aware results with keyword search")
            search_words = [word.strip() for word in query.split() if len(word.strip()) > 2]
            keyword_query = ' OR '.join(search_words)
            keyword_docs = await self._search_documents(keyword_query, project_filter, use_semantic=False, folder_filter=folder_filter)
            
            # Combine and deduplicate results
            seen_ids = {doc.get('id') for doc in documents}
            for doc in keyword_docs:
                if doc.get('id') not in seen_ids:
                    documents.append(doc)
                    seen_ids.add(doc.get('id'))
        
        # Filter out documents from excluded folders
        filtered_documents = []
        for doc in documents:
            blob_name = doc.get('blob_name', '') or doc.get('filename', '')
            if not self.folder_service.should_exclude_folder(blob_name):
                filtered_documents.append(doc)
            else:
                logger.debug("Excluded document from superseded/archive folder", blob_name=blob_name)
        
        return filtered_documents
    
    def _format_documents_with_folder_context(self, documents: List[Dict], folder_context: Dict[str, Any]) -> str:
        """Format documents with folder structure context."""
        formatted_docs = []
        
        for doc in documents[:10]:  # Top 10 most relevant
            filename = doc.get('filename', 'Unknown')
            content = doc.get('content', '')
            blob_name = doc.get('blob_name', '')
            
            # Extract folder information
            folder_info = self._extract_folder_info(blob_name)
            
            # Get SuiteFiles link
            blob_url = self._get_blob_url_from_doc(doc)
            suitefiles_link = self._get_safe_suitefiles_url(blob_url)
            
            # Check if this is actually a real project document
            project_name = doc.get('project_name', '')
            is_real_project = self._is_real_project_document(blob_name, project_name)
            
            # Format document info - only show project info if it's a real project
            if is_real_project and folder_info['project'] and folder_info['year']:
                doc_info = f"""DOCUMENT: {filename}
                Folder: {folder_info['folder_path']}
                Year: {folder_info['year']} | Project: {folder_info['project']}
                Link: {suitefiles_link}
                Content: {content[:600]}...
                ---"""
            else:
                # Non-project document - don't show project info
                doc_info = f"""DOCUMENT: {filename}
                Folder: {folder_info['folder_path']}
                Link: {suitefiles_link}
                Content: {content[:600]}...
                ---"""
            
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
            # Try to extract year from folder code
            for part in parts:
                if hasattr(self.folder_service, 'year_mappings') and part in self.folder_service.year_mappings:
                    year = self.folder_service.year_mappings[part]
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
        return (doc.get('blob_url') or 
                doc.get('blobUrl') or 
                doc.get('url') or 
                doc.get('source_url') or 
                doc.get('metadata_storage_path') or 
                doc.get('metadata_storage_name') or
                doc.get('sourcePage') or
                doc.get('source') or '')
    
    async def _handle_no_documents_with_folder_guidance(self, question: str, folder_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cases where no documents are found, with folder structure guidance."""
        
        query_type = folder_context.get('query_type', 'general')
        suggested_folders = folder_context.get('suggested_folders', [])
        year_context = folder_context.get('year_context')
        
        guidance_parts = []
        
        if year_context:
            years = year_context.get('years', [])
            guidance_parts.append(f"I looked for documents from {', '.join(years)} but didn't find specific matches.")
        
        if query_type != 'general':
            guidance_parts.append(f"This appears to be a {query_type}-related question.")
        
        if suggested_folders:
            guidance_parts.append(f"I searched in relevant folders: {', '.join(suggested_folders)}")
        
        guidance = " ".join(guidance_parts) if guidance_parts else "I couldn't find specific documents matching your question."
        
        # Generate a helpful response with folder guidance
        fallback_prompt = f"""The user asked: "{question}"

                {guidance}

                Based on DTCE's folder structure and general engineering knowledge, provide a helpful response that:
                1. Acknowledges that specific documents weren't found
                2. Provides general guidance based on the question type
                3. Suggests where they might look in SuiteFiles (mention relevant folder types)
                4. Offers to help with related questions

                Be helpful and specific about DTCE's document organization."""
        
        answer = await self._generate_fallback_response(fallback_prompt)
        
        return {
            'answer': answer,
            'sources': [],
            'confidence': 'low',
            'documents_searched': 0,
            'rag_type': 'folder_aware_fallback',
            'folder_guidance': guidance_parts
        }

    async def _generate_fallback_response(self, prompt: str) -> str:
        """Generate fallback response when no documents are found."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful structural engineering AI assistant for DTCE. Provide practical guidance for New Zealand conditions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Fallback response generation failed", error=str(e))
            return "I'm having trouble generating a response at the moment. Please try rephrasing your question or contact support if the issue persists."

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
                    
                    # Only show project name if it's actually from a Projects folder and has a proper project structure
                    is_real_project = self._is_real_project_document(blob_name, project_name)
                    
                    if is_real_project and project_name and project_name.strip():
                        doc_result = "[DOCUMENT] **DOCUMENT FOUND:**\n- **File Name:** " + filename + "\n- **Project:** " + project_name + "\n- **SuiteFiles Link:** " + suitefiles_link + "\n- **Content Preview:** " + content[:800] + "...\n\n"
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
        """Process RAG query with the complete intelligent prompt system."""
        try:
            # Build the complete intelligent prompt
            prompt = "The user has asked the following question: \"" + question + "\"\n\n"
            prompt += "I have ALREADY searched SuiteFiles and retrieved the most relevant content for you.\n\n"
            prompt += "CRITICAL FIRST STEP - DETERMINE USER INTENT:\n"
            prompt += "BEFORE answering, you must first determine the user's intent:\n\n"
            prompt += "SPECIAL NOTE FOR POLICY DOCUMENTS:\n"
            prompt += "- Some policy documents (e.g., Wellbeing Policy) may appear in search results but have minimal extracted content\n"
            prompt += "- If you find policy documents with limited content, acknowledge the document exists and provide general guidance about the topic\n"
            prompt += "- For wellbeing/wellness queries: Explain that DTCE has wellbeing policies and suggest contacting HR for detailed information\n"
            prompt += "- Always provide the SuiteFiles link even if content is limited\n\n"
            prompt += "SUITEFILES KNOWLEDGE INDICATORS - Questions that REQUIRE SuiteFiles data:\n"
            prompt += "- Contains pronouns: \"we\", \"we've\", \"our\", \"us\", \"DTCE has\", \"company\", \"past projects\"\n"
            prompt += "- Scenario-based technical queries: \"Show me examples of...\", \"What have we used for...\", \"Find projects where...\"\n"
            prompt += "- Problem-solving & lessons learned: \"What issues have we run into...\", \"lessons learned from projects...\"\n"
            prompt += "- Regulatory & consent precedents: \"projects where council questioned...\", \"How have we approached...\"\n"
            prompt += "- Cost & time insights: \"How long does it typically take...\", \"What's the typical cost range...\"\n"
            prompt += "- Best practices & templates: \"What's our standard approach...\", \"Show me our best example...\"\n"
            prompt += "- Materials & methods comparisons: \"When have we chosen...\", \"What have we specified...\"\n"
            prompt += "- Internal knowledge mapping: \"Which engineers have experience...\", \"Who has documented expertise...\"\n\n"
            prompt += "GENERAL KNOWLEDGE INDICATORS - Questions requiring external/standards knowledge:\n"
            prompt += "- Standards and codes references: \"NZS requirements\", \"building code\", \"AS/NZS standards\"\n"
            prompt += "- General engineering theory: \"How do I calculate...\", \"What is the formula for...\"\n"
            prompt += "- Industry best practices (not DTCE specific): \"Best practices for...\", \"Standard approach to...\"\n\n"
            prompt += "MIXED REQUIREMENTS - Questions needing BOTH SuiteFiles AND general knowledge:\n"
            prompt += "- DTCE experience + standards compliance\n"
            prompt += "- Past projects + current code requirements\n"
            prompt += "- Company templates + industry standards\n\n"
            prompt += "Based on your determination, follow these linking guidelines:\n\n"
            prompt += "IF SUITEFILES KNOWLEDGE (especially if contains \"we\"/\"our\"/\"DTCE\"): Use the retrieved SuiteFiles content and ALWAYS include SuiteFiles links\n"
            prompt += "IF GENERAL KNOWLEDGE ONLY: Provide general engineering knowledge and include relevant online links\n"
            prompt += "IF BOTH: Include both SuiteFiles links for relevant documents AND online links for general knowledge aspects\n"
            prompt += "IF NEITHER/UNCLEAR: Default to providing BOTH SuiteFiles links AND online resources\n\n"
            prompt += "Your task is to:\n"
            prompt += "1. FIRST determine the user's intent based on language indicators above\n"
            prompt += "2. Analyze the retrieved content I'm providing below from SuiteFiles\n"
            prompt += "3. For COMPLEX ANALYSIS QUESTIONS (scenarios, lessons learned, cost insights, comparisons):\n"
            prompt += "   - Search across multiple projects to find patterns and examples\n"
            prompt += "   - Aggregate information from similar projects or situations\n"
            prompt += "   - Summarize trends, common issues, and solutions\n"
            prompt += "   - Provide specific project examples with SuiteFiles links\n"
            prompt += "   - Extract quantitative data when available (costs, timelines, specifications)\n"
            prompt += "4. Apply the correct linking strategy consistently throughout your response\n"
            prompt += "5. Always be comprehensive - if in doubt, include both types of resources\n\n"
            prompt += "SPECIAL HANDLING FOR COMPLEX QUERIES:\n"
            prompt += "When users ask for cross-project analysis (examples, patterns, comparisons, lessons learned):\n"
            prompt += "- Look for multiple relevant documents across different projects\n"
            prompt += "- Identify common themes, solutions, and approaches\n"
            prompt += "- Provide specific examples with project numbers and SuiteFiles links\n"
            prompt += "- Summarize patterns and trends from the retrieved documents\n"
            prompt += "- Extract specific technical details (materials, methods, costs, timelines)\n"
            prompt += "- If limited SuiteFiles data, acknowledge limitations and provide general guidance\n\n"
            prompt += "Reference Example (rag.txt)\n"
            prompt += "You may refer to the following example file — rag.txt — which contains example question-answer formats showing how the AI could respond to different structural engineering and project-related queries.\n"
            prompt += "However, do not copy from this file or rely on its content directly. It is only a reference to help you understand the style and expectations of the response. You must still follow the actual question, the user's intent, and the retrieved documents.\n\n"
            prompt += "Retrieved content from SuiteFiles:\n" + retrieved_content + "\n\n"
            prompt += "Final Task:\n"
            prompt += "Based on your intent determination and the above content, provide a helpful, relevant, and human-like response.\n\n"
            prompt += "CRITICAL FORMATTING INSTRUCTIONS:\n\n"
            prompt += "FOR SUITEFILES REFERENCES:\n"
            prompt += "When you reference ANY document from the retrieved content above, you MUST format it exactly like this:\n"
            prompt += "**Referenced Document:** [Document Name] (Project: [Project Name])\n"
            prompt += "**SuiteFiles Link:** [The actual clickable link provided above]\n\n"
            prompt += "FOR GENERAL KNOWLEDGE REFERENCES:\n"
            prompt += "When you use general knowledge, include relevant online links like this:\n"
            prompt += "**Additional Resources:**\n"
            prompt += "- [Resource Name]: [URL or description]\n"
            prompt += "- [Study/Paper Name]: [URL if available]\n\n"
            prompt += "Example Combined Response (for Both/Neither/Unclear cases):\n"
            prompt += "**Referenced Document:** Manual for Design and Detailing (Project: Project 220294)\n"
            prompt += "**SuiteFiles Link:** https://dtce.suitefiles.com/suitefileswebdav/DTCE%20SuiteFiles/Projects/220/220294/...\n\n"
            prompt += "**Additional Resources:**\n"
            prompt += "- Standards New Zealand: https://www.standards.govt.nz/\n"
            prompt += "- NZS 3101 Concrete Structures Standard: [Official publication]\n\n"
            prompt += "IMPORTANT GUIDELINES:\n"
            prompt += "- Use content from the retrieved documents only if applicable and relevant\n"
            prompt += "- ALWAYS include appropriate links based on your intent determination\n"
            prompt += "- For questions about standards/codes: Include BOTH SuiteFiles documents AND official online sources\n"
            prompt += "- If intent is unclear or could be both: Default to providing BOTH types of resources\n"
            prompt += "- Your goal is to be informative and context-aware, not robotic or overly reliant on past formats\n"
            prompt += "- Focus on practical engineering guidance for New Zealand conditions when applicable\n\n"
            prompt += "CRITICAL: DO NOT MENTION YOUR INTENT ANALYSIS TO THE USER\n"
            prompt += "- Never say \"Based on the user's query...\" or \"The user's question appears to require...\"\n"
            prompt += "- Never explain your reasoning about intent determination\n"
            prompt += "- Never mention that you are analyzing what type of knowledge is needed\n"
            prompt += "- Just answer the question naturally and directly\n"
            prompt += "- Start with helpful information, not meta-commentary about the question type\n\n"
            prompt += "RESPONSE GUIDELINES FOR COMPLEX QUERIES:\n"
            prompt += "- For \"Show me examples...\" → Provide specific project examples with numbers and links\n"
            prompt += "- For \"What have we used...\" → List specific materials/methods with project references\n"
            prompt += "- For \"What issues have we run into...\" → Summarize problems and solutions from multiple projects\n"
            prompt += "- For \"How long does it typically take...\" → Extract timeline data from project documents\n"
            prompt += "- For \"Which engineers have experience...\" → Look for author/engineer names in documents\n"
            prompt += "- For cross-project comparisons → Analyze multiple projects and highlight differences/similarities\n"
            
            answer = await self._generate_project_answer_with_links(prompt, retrieved_content)
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents) if documents else [],
                'confidence': 'high' if documents else 'medium',
                'documents_searched': len(documents),
                'rag_type': 'unified_semantic_search'
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
                              doc_types: Optional[List[str]] = None, use_semantic: bool = True, 
                              folder_filter: Optional[str] = None) -> List[Dict]:
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
            
            # Add document type filter if specified
            if doc_types:
                doc_filter = ' or '.join([f"search.ismatch('*.{ext}', 'filename')" for ext in doc_types])
                filters.append(f"({doc_filter})")
                logger.info("Added document type filter", filter=doc_filter)
            
            # Add folder filter if specified (simplified to avoid syntax errors)
            if folder_filter:
                # For now, skip complex folder filters to avoid Azure Search syntax errors
                # TODO: Fix folder filter syntax in folder_structure_service.py
                logger.info("Skipping complex folder filter to avoid syntax errors", folder_filter=folder_filter)
            
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
                    
                    logger.info("Keyword search fallback completed", 
                               documents_found=len(documents),
                               filenames=[doc.get('filename', 'Unknown') for doc in documents[:5]])
                else:
                    raise semantic_error
            
            return documents
            
        except Exception as e:
            logger.error("Document search failed", error=str(e), search_query=search_query)
            return []
    
    def _get_safe_suitefiles_url(self, blob_url: str, link_type: str = "file") -> str:
        """Get SuiteFiles URL or fallback message if conversion fails."""
        if not blob_url:
            return "Document available in SuiteFiles"
        
        suitefiles_url = self._convert_to_suitefiles_url(blob_url, link_type)
        return suitefiles_url or "Document available in SuiteFiles"
    
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
        for doc in documents[:5]:  # Limit to top 5 sources
            source = {
                'filename': doc.get('filename', 'Unknown'),
                'project': doc.get('project_name', 'Unknown'),
                'folder': doc.get('folder', '')
            }
            
            # Add SuiteFiles link if available
            blob_url = doc.get('blob_url', '')
            if blob_url:
                suitefiles_url = self._get_safe_suitefiles_url(blob_url)
                if suitefiles_url and suitefiles_url != "Document available in SuiteFiles":
                    source['suitefiles_url'] = suitefiles_url
            
            sources.append(source)
        
        return sources
    
    async def _generate_project_answer_with_links(self, prompt: str, context: str) -> str:
        """Generate answer using GPT with project context and SuiteFiles links."""
        try:
            # Enhanced system prompt that emphasizes proper formatting
            system_prompt = """You are a helpful structural engineering AI assistant for DTCE. 

IMPORTANT FORMATTING INSTRUCTIONS:
- When referencing documents, use this EXACT format:
  
  **Referenced Document:** [Document Name] (Project: [Project Name])
  [Document Name as clickable link text](Full URL)

- Keep it simple - just the document name as clickable link text
- Use proper line breaks between sections
- Ensure links are complete and not truncated
- Maintain professional formatting throughout

Example:
**Referenced Document:** Manual for Design and Detailing (Project: Project 220294)
[Manual for Design and Detailing](https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/Projects/220/220294/...)

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
