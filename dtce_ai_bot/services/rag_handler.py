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
                    if not project_name:
                        # Try to extract from filename if available
                        project_from_filename = self._extract_project_from_filename(filename_for_project)
                        if project_from_filename:
                            project_name = project_from_filename
                    
                    suitefiles_link = self._get_safe_suitefiles_url(blob_url)
                    
                    # Format document information in structured way for GPT
                    if project_name:
                        doc_result = f"""📄 **DOCUMENT FOUND:**
- **File Name:** {filename}
- **Project:** {project_name}
- **SuiteFiles Link:** {suitefiles_link}
- **Content Preview:** {content[:800]}...

"""
                    else:
                        doc_result = f"""📄 **DOCUMENT FOUND:**
- **File Name:** {filename}
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

🎯 CRITICAL FIRST STEP - DETERMINE USER INTENT:
BEFORE answering, you must first determine the user's intent:
- Does this question require knowledge from SuiteFiles (specific projects, templates, past work, company documents)?
- Does this question require general engineering knowledge (standards, best practices, theory, calculations)?
- Does this question require BOTH SuiteFiles knowledge AND general knowledge?
- Is the user's intent UNCLEAR or does it fall into NEITHER category clearly?

Based on your determination, follow these linking guidelines:

📁 IF SUITEFILES KNOWLEDGE ONLY: Use the retrieved SuiteFiles content and ALWAYS include SuiteFiles links as formatted below
🌐 IF GENERAL KNOWLEDGE ONLY: Provide general engineering knowledge and include relevant online links to:
   - Official standards organizations (Standards New Zealand, ISO, AISC, ASCE, etc.)
   - Research institutions and technical papers  
   - Professional engineering bodies (Engineering New Zealand, etc.)
   - Industry guidelines and technical resources
   - Government regulations and building codes
   - Any credible online forums, studies, or publications you reference

🔄 IF BOTH: Include both SuiteFiles links for relevant documents AND online links for general knowledge aspects
❓ IF NEITHER/UNCLEAR: Provide both SuiteFiles links (if relevant documents found) AND general knowledge with online resources

Your task is to:
1. FIRST determine the user's intent (SuiteFiles Only, General Only, Both, or Neither/Unclear)
2. Analyze the retrieved content I'm providing below from SuiteFiles
3. Based on your intent determination:
   - SuiteFiles Only: Use only SuiteFiles documents and links
   - General Only: Use general knowledge and include online resources/links
   - Both: Use SuiteFiles documents + general knowledge + both types of links
   - Neither/Unclear: Default to providing BOTH SuiteFiles links AND online resources
4. Apply the correct linking strategy consistently throughout your response
5. Always be comprehensive - if in doubt, include both types of resources

ℹ️ Reference Example (rag.txt)
You may refer to the following example file — rag.txt — which contains example question-answer formats showing how the AI could respond to different structural engineering and project-related queries.
However, do not copy from this file or rely on its content directly. It is only a reference to help you understand the style and expectations of the response. You must still follow the actual question, the user's intent, and the retrieved documents.

📎 Retrieved content from SuiteFiles:
{retrieved_content}

✅ Final Task:
Based on your intent determination and the above content, provide a helpful, relevant, and human-like response.

🔗 CRITICAL FORMATTING INSTRUCTIONS:

FOR SUITEFILES REFERENCES:
When you reference ANY document from the retrieved content above, you MUST format it exactly like this:
**Referenced Document:** [Document Name] (📁 Project: [Project Name])
**SuiteFiles Link:** [The actual clickable link provided above]

FOR GENERAL KNOWLEDGE REFERENCES:
When you use general knowledge, include relevant online links like this:
**Additional Resources:**
- [Resource Name]: [URL or description]
- [Study/Paper Name]: [URL if available]

Example Combined Response (for Both/Neither/Unclear cases):
**Referenced Document:** Manual for Design and Detailing (📁 Project: Project 220294)
**SuiteFiles Link:** https://dtce.suitefiles.com/suitefileswebdav/DTCE%20SuiteFiles/Projects/220/220294/...

**Additional Resources:**
- Standards New Zealand: https://www.standards.govt.nz/
- NZS 3101 Concrete Structures Standard: [Official publication]

IMPORTANT GUIDELINES:
- Use content from the retrieved documents only if applicable and relevant
- ALWAYS include appropriate links based on your intent determination
- For questions about standards/codes: Include BOTH SuiteFiles documents AND official online sources
- If intent is unclear or could be both: Default to providing BOTH types of resources
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
- When referencing documents, use this EXACT format:
  
  **Referenced Document:** [Document Name] (📁 Project: [Project Name])
  [Document Name as clickable link text](Full URL)

- Keep it simple - just the document name as clickable link text
- Use proper line breaks between sections
- Ensure links are complete and not truncated
- Maintain professional formatting throughout

Example:
**Referenced Document:** Manual for Design and Detailing (📁 Project: Project 220294)
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
