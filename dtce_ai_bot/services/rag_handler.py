"""
RAG (Retrieval-Augmented Generation) Handler for DTCE AI Bot
UNIFIED SEMANTIC SEARCH FLOW - No pattern matching, direct search for ALL questions
"""

import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class RAGHandler:
    """Handles RAG processing with unified semantic search flow for ALL questions."""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def process_rag_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        UNIFIED SEMANTIC SEARCH FLOW - No pattern matching, direct search for ALL questions:
        
        The user has asked the following question: "{user_question}"
        You will now perform the following steps:
        1. Search the user's question in SuiteFiles using semantic + OR-based keyword query
        2. From SuiteFiles, retrieve the most relevant documents or excerpts related to the question
        3. Read and understand the user's intent
        4. Use the retrieved content to construct a helpful and natural-sounding answer, only if the content is relevant to the user's query
        5. If the retrieved documents are not relevant, answer the question based on your general knowledge instead
        """
        try:
            logger.info("Processing ALL questions with unified semantic search", question=question)
            
            # STEP 1: Search user's question using SEMANTIC SEARCH for better intent understanding
            documents = await self._search_documents(question, project_filter, use_semantic=True)
            
            # If semantic search doesn't find enough results, also try keyword OR search
            if len(documents) < 5:
                logger.info("Enhancing results with keyword search")
                search_words = [word.strip() for word in question.split() if len(word.strip()) > 2]
                keyword_query = ' OR '.join(search_words)
                keyword_docs = await self._search_documents(keyword_query, project_filter, use_semantic=False)
                
                # Combine and deduplicate results
                seen_ids = {doc.get('id') for doc in documents}
                for doc in keyword_docs:
                    if doc.get('id') not in seen_ids:
                        documents.append(doc)
                        seen_ids.add(doc.get('id'))
            
            logger.info("Unified semantic + keyword search results", 
                       total_documents=len(documents),
                       sample_filenames=[doc.get('filename', 'Unknown') for doc in documents[:3]])
            
            # STEP 2: Retrieve most relevant documents from index
            if documents:
                # Format retrieved content from SuiteFiles with proper structure
                index_results = []
                for doc in documents[:10]:  # Top 10 most relevant
                    filename = doc.get('filename', 'Unknown')
                    content = doc.get('content', '')
                    
                    # Try different possible field names for blob URL
                    blob_url = (doc.get('blob_url') or 
                               doc.get('blobUrl') or 
                               doc.get('url') or 
                               doc.get('source_url') or 
                               doc.get('metadata_storage_path') or 
                               doc.get('metadata_storage_name') or
                               doc.get('sourcePage') or
                               doc.get('source') or '')
                    
                    # Also try to extract project from filename if blob_url fails
                    filename_for_project = filename if filename else ''
                    
                    # Debug logging to see what we're getting
                    logger.info("Document fields for project extraction", 
                               filename=filename,
                               blob_url=blob_url,
                               doc_keys=list(doc.keys()),
                               all_doc_values={k: str(v)[:200] for k, v in doc.items()})  # Truncate long values
                    
                    # Extract project information from blob_url or fallback to filename
                    project_name = self._extract_project_name_from_blob_url(blob_url)
                    if project_name == "Unknown Project":
                        # Try to extract from filename if available
                        project_from_filename = self._extract_project_from_filename(filename_for_project)
                        if project_from_filename != "Unknown Project":
                            project_name = project_from_filename
                    
                    suitefiles_link = self._get_safe_suitefiles_url(blob_url)
                    
                    # Format document information in structured way for GPT
                    doc_result = f"""📄 **DOCUMENT FOUND:**
- **File Name:** {filename}
- **Project:** {project_name}
- **SuiteFiles Link:** {suitefiles_link}
- **Content Preview:** {content[:800]}...

"""
                    index_results.append(doc_result)
                
                retrieved_content = "\n".join(index_results)
            else:
                retrieved_content = "No relevant documents found in SuiteFiles."
            
            # STEP 3: GPT analyzes user intent and constructs natural answer
            prompt = f"""The user has asked the following question: "{question}"

I have ALREADY searched SuiteFiles and retrieved the most relevant content for you.

Your task is to:
1. Read and understand the user's intent from their question
2. Analyze the retrieved content I'm providing below from SuiteFiles
3. Use the retrieved content to construct a helpful and natural-sounding answer, ONLY if the content is relevant to the user's query
4. If the retrieved documents are not relevant to the user's question, answer based on your general engineering knowledge instead

ℹ️ Reference Example (rag.txt)
You may refer to the following example file — rag.txt — which contains example question-answer formats showing how the AI could respond to different structural engineering and project-related queries.
However, do not copy from this file or rely on its content directly. It is only a reference to help you understand the style and expectations of the response. You must still follow the actual question, the user's intent, and the retrieved documents.

📎 Retrieved content from SuiteFiles:
{retrieved_content}

✅ Final Task:
Based on the above retrieved content from SuiteFiles and the user's intent, provide a helpful, relevant, and human-like response.

🔗 CRITICAL FORMATTING INSTRUCTIONS:
When you reference ANY document from the retrieved content above, you MUST format it exactly like this:

**Referenced Document:** [Document Name] (📁 Project: [Project Name])
**SuiteFiles Link:** [The actual clickable link provided above]

Example:
**Referenced Document:** Manual for Design and Detailing (📁 Project: Project 220294)
**SuiteFiles Link:** https://dtce.suitefiles.com/suitefileswebdav/DTCE%20SuiteFiles/Projects/220/220294/...

- Use content from the retrieved documents only if applicable and relevant
- ALWAYS format document references with the project name and clickable link as shown above
- If documents do not help answer the user's specific question, use your own general knowledge
- Your goal is to be informative and context-aware, not robotic or overly reliant on past formats
- Focus on practical engineering guidance for New Zealand conditions when applicable"""
            
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
            
            # Add document type filter if specified
            if doc_types:
                doc_filter = ' or '.join([f"search.ismatch('*.{ext}', 'filename')" for ext in doc_types])
                search_params['filter'] = doc_filter
                logger.info("Added document type filter", filter=doc_filter)
            
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
        """Extract project name/number from blob URL path."""
        if not blob_url:
            logger.warning("No blob URL provided for project extraction")
            return "Unknown Project"
        
        try:
            logger.info("Extracting project name from blob URL", blob_url=blob_url)
            
            # Try different patterns that might exist in the blob URLs
            patterns_to_try = [
                "/dtce-documents/Projects/",
                "/dtce-ai-documents/Projects/", 
                "/Projects/",
                "Projects/",
                "/projects/",  # lowercase
                "projects/"    # lowercase
            ]
            
            path_part = None
            matched_pattern = None
            for pattern in patterns_to_try:
                if pattern in blob_url:
                    path_part = blob_url.split(pattern)[1]
                    matched_pattern = pattern
                    logger.info(f"Found pattern '{pattern}'", path_part=path_part, blob_url=blob_url)
                    break
            
            if not path_part:
                # Try regex patterns for more flexible matching
                import re
                # Look for any variation of Projects folder
                match = re.search(r'/([Pp]rojects?)/(.+)', blob_url)
                if match:
                    path_part = match.group(2)
                    matched_pattern = f"/{match.group(1)}/"
                    logger.info(f"Found regex pattern '{matched_pattern}'", path_part=path_part, blob_url=blob_url)
            
            if path_part:
                # Remove query parameters
                if "?" in path_part:
                    path_part = path_part.split("?")[0]
                
                # Remove URL encoding
                from urllib.parse import unquote
                path_part = unquote(path_part)
                
                logger.info("Clean path part", path_part=path_part)
                
                # Split path and get project info - typically 220/220294/... 
                path_segments = [seg for seg in path_part.split('/') if seg]  # Filter out empty segments
                logger.info("Path segments", segments=path_segments)
                
                if len(path_segments) >= 2:
                    # Get project number (second segment, like "220294")
                    project_number = path_segments[1]
                    logger.info("Extracted project number from second segment", project_number=project_number)
                    return f"Project {project_number}"
                elif len(path_segments) >= 1:
                    # Get first segment if available
                    project_number = path_segments[0]
                    logger.info("Extracted project number from first segment", project_number=project_number)
                    return f"Project {project_number}"
            else:
                logger.warning("No recognized project pattern found in blob URL", blob_url=blob_url)
                    
        except Exception as e:
            logger.warning("Failed to extract project name from blob URL", error=str(e), blob_url=blob_url)
            
        return "Unknown Project"

    def _extract_project_from_filename(self, filename: str) -> str:
        """Extract project number from filename if it contains project patterns."""
        if not filename:
            return "Unknown Project"
        
        try:
            import re
            # Look for patterns like: 220294, P-220294, Project220294, etc.
            patterns = [
                r'(?:^|[^0-9])([2-3][0-9]{5})(?:[^0-9]|$)',  # 6-digit project numbers starting with 2 or 3
                r'P-([2-3][0-9]{5})',  # P-220294 format
                r'Project\s*([2-3][0-9]{5})',  # Project 220294 format
                r'([2-3][0-9]{4})',  # 5-digit project numbers
            ]
            
            for pattern in patterns:
                match = re.search(pattern, filename, re.IGNORECASE)
                if match:
                    project_number = match.group(1)
                    logger.info("Extracted project from filename", filename=filename, project_number=project_number)
                    return f"Project {project_number}"
                    
        except Exception as e:
            logger.warning("Failed to extract project from filename", filename=filename, error=str(e))
            
        return "Unknown Project"
    
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
                
                # Remove URL encoding
                from urllib.parse import unquote
                path_part = unquote(path_part)
                
                # Build SharePoint URL - use the documents.aspx format
                # Base SharePoint URL for SuiteFiles
                base_url = "https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#"
                suitefiles_url = f"{base_url}/{path_part}"
                
                logger.info("Converted to SharePoint SuiteFiles URL", suitefiles_url=suitefiles_url)
                return suitefiles_url
            else:
                logger.warning("Could not find dtce-documents in blob URL", blob_url=blob_url)
                
        except Exception as e:
            logger.error("Failed to convert blob URL to SuiteFiles SharePoint URL", error=str(e), blob_url=blob_url)
            
        return None
        """Convert Azure blob URL to SuiteFiles URL."""
        if not blob_url:
            return None
        
        try:
            logger.info("Converting blob URL to SuiteFiles SharePoint URL", blob_url=blob_url)
            
            # Extract path from blob URL - handle different patterns
            path_part = None
            
            if "/dtce-documents/" in blob_url:
                path_part = blob_url.split("/dtce-documents/")[1]
                logger.info("Found dtce-documents in URL", path_part=path_part)
            
            if path_part:
                # Remove any query parameters
                if "?" in path_part:
                    path_part = path_part.split("?")[0]
                
                # Remove URL encoding
                from urllib.parse import unquote
                path_part = unquote(path_part)
                
                # Build SharePoint URL - use the documents.aspx format
                base_url = "https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#"
                suitefiles_url = f"{base_url}/{path_part}"
                
                logger.info("Converted to SharePoint SuiteFiles URL", suitefiles_url=suitefiles_url)
                return suitefiles_url
            else:
                logger.warning("Could not find dtce-documents in blob URL", blob_url=blob_url)
                
        except Exception as e:
            logger.error("Failed to convert blob URL to SuiteFiles", error=str(e), blob_url=blob_url)
            
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
- When referencing documents, use this EXACT format with proper line breaks:
  
  **Referenced Document:** [Document Name]
  **Project:** [Project Name]  
  **SuiteFiles Link:** [Full Clickable Link]

- Always include complete, clickable SuiteFiles links
- Use proper line breaks between sections
- Ensure links are not truncated
- Maintain professional formatting throughout

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
