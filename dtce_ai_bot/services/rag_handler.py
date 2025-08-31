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

logger = structlog.get_logger(__name__)


class RAGHandler:
    """Handles RAG processing with enhanced semantic search and intent recognition."""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        self.semantic_search = SemanticSearchService(search_client)
    
    async def process_rag_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        ENHANCED SEMANTIC SEARCH with Intent Recognition:
        
        1. Classify user intent for targeted search
        2. Execute semantic search with intent-based optimization  
        3. Retrieve and rank relevant documents intelligently
        4. Generate answer with proper context understanding
        """
        try:
            logger.info("Processing question with intent recognition", question=question)
            
            # STEP 1: Use enhanced semantic search with intent recognition
            documents = await self.semantic_search.search_documents(question, project_filter)
            
            logger.info("Enhanced semantic search results", 
                       total_documents=len(documents),
                       sample_filenames=[doc.get('filename', 'Unknown') for doc in documents[:3]])
            
            # STEP 2: Generate response with retrieved documents
            if documents:
                # Format documents into retrieved content (use existing method without folder context)
                retrieved_content = self._format_documents_simple(documents)
                
                # Use the complete intelligent prompt system
                result = await self._process_rag_with_full_prompt(question, retrieved_content, documents)
                
                result.update({
                    'rag_type': 'enhanced_semantic_search',
                    'search_method': 'intent_based_semantic'
                })
                
                return result
            else:
                # No documents found - provide general response
                return await self._handle_no_documents_found(question)
                
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
        
        # Filter out documents from excluded folders
        filtered_documents = []
        for doc in documents:
            blob_name = doc.get('blob_name', '') or doc.get('filename', '')
            if not self.folder_service.should_exclude_folder(blob_name):
                filtered_documents.append(doc)
            else:
                logger.debug("Excluded document from superseded/archive folder", blob_name=blob_name)
        
        return filtered_documents
    
    def _format_documents_simple(self, documents: List[Dict]) -> str:
        """Format documents for AI prompt without folder context."""
        if not documents:
            return "No documents found."
        
        formatted_content = ""
        for i, doc in enumerate(documents[:10], 1):  # Limit to top 10 documents
            filename = doc.get('filename', 'Unknown file')
            content = doc.get('content', 'No content available')
            
            # Truncate very long content
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            formatted_content += f"\n--- Document {i}: {filename} ---\n{content}\n"
        
        return formatted_content
    
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
            
            # Extract project info using our consistent method
            extracted_project = self._extract_project_name_from_blob_url(blob_url)
            
            # Format document info - only show project info if it's from Projects folder
            if extracted_project:
                doc_info = f"""DOCUMENT: {filename}
                Folder: {folder_info['folder_path']}
                Project: {extracted_project}
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
    
    async def _handle_no_documents_found(self, question: str) -> Dict[str, Any]:
        """Handle cases where no documents are found - provide intelligent fallback."""
        logger.info("No documents found, providing general response", question=question)
        
        # Use GPT knowledge fallback
        try:
            fallback_prompt = f"""I searched our DTCE document database but couldn't find specific documents related to: "{question}"

This could mean:
1. The information might be in documents I don't have access to
2. It might be stored under different terms or file names
3. It might be general knowledge that doesn't require specific documents

Please provide a helpful response acknowledging that I couldn't find specific documents, and if appropriate, provide general guidance or suggest alternative search terms the user could try.

Question: {question}"""
            
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": fallback_prompt}],
                temperature=0.3,
                max_tokens=500
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
        """Handle cases where no documents are found, using GPT's general knowledge as fallback."""
        
        suggested_folders = folder_context.get('suggested_folders', [])
        year_context = folder_context.get('year_context')
        
        # Build simple context about what was searched
        search_context = []
        if year_context:
            years = year_context.get('years', [])
            search_context.append(f"searched in {', '.join(years)} project folders")
        if suggested_folders:
            search_context.append(f"looked in {', '.join(suggested_folders)} folders")
        
        search_info = " and ".join(search_context) if search_context else "searched SuiteFiles"
        
        # Simple, intelligent GPT fallback
        fallback_prompt = f"""The user asked: "{question}"

I {search_info} but didn't find specific documents in DTCE's SuiteFiles system.

Please provide a comprehensive, helpful answer using your general knowledge. Consider:
- If this is about DTCE policies/procedures: acknowledge no specific documents found, provide general guidance
- If this is technical/engineering: provide relevant NZ standards, best practices, and professional advice
- If this is about projects/clients: provide general project management or industry insights
- If this is about processes/templates: suggest typical approaches and what to include

Be thorough, professional, and acknowledge when this is general vs. company-specific guidance.
Focus on New Zealand conditions and structural engineering practices where relevant."""
        
        answer = await self._generate_fallback_response(fallback_prompt)
        
        return {
            'answer': answer,
            'sources': [],
            'confidence': 'medium',
            'documents_searched': 0,
            'rag_type': 'gpt_knowledge_fallback',
            'search_attempted': search_info,
            'fallback_reason': 'No documents found in SuiteFiles, using GPT general knowledge'
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
        """Process RAG query with the complete intelligent prompt system."""
        try:
            # Build the complete intelligent prompt
            prompt = "The user has asked the following question: \"" + question + "\"\n\n"
            prompt += "I have ALREADY searched SuiteFiles and retrieved the most relevant content for you.\n\n"
            prompt += "CRITICAL FIRST STEP - DETERMINE USER INTENT:\n"
            prompt += "BEFORE answering, you must first determine the user's intent:\n\n"
            prompt += "FOLDER STRUCTURE UNDERSTANDING:\n"
            prompt += "DTCE's document system is organized into distinct categories. Understanding these is CRITICAL for providing accurate responses:\n\n"
            prompt += "1. **POLICY DOCUMENTS** (Policy/H&S/, Policy/IT/, etc.):\n"
            prompt += "   - Mandatory rules and procedures that employees MUST follow\n"
            prompt += "   - Use case: Employee compliance, safety procedures, company rules\n"
            prompt += "   - When users ask about 'safety rules', 'policies', 'procedures' → ONLY reference Policy documents\n"
            prompt += "   - Do NOT mix with project-specific safety plans\n\n"
            prompt += "2. **PROCEDURES/H2H (How-to Handbooks)** (Procedures/, H2H/):\n"
            prompt += "   - Best practices and 'how we do things at DTCE'\n"
            prompt += "   - Less strict than policies, more guidance-oriented\n"
            prompt += "   - Use case: 'How do I use the wind speed spreadsheet?', technical procedures\n\n"
            prompt += "3. **NZ ENGINEERING STANDARDS** (Engineering/, Standards/):\n"
            prompt += "   - Official NZ building codes, standards (NZS), technical references\n"
            prompt += "   - Use case: Code requirements, standard specifications\n"
            prompt += "   - These are NOT DTCE-specific, they are general industry standards\n\n"
            prompt += "4. **PROJECT DOCUMENTS** (Projects/225/, Projects/224/, etc.):\n"
            prompt += "   - Actual DTCE project work with specific clients and job numbers\n"
            prompt += "   - Use case: Past project examples, client work, project references\n"
            prompt += "   - When users ask for 'past projects' → ONLY reference Project folders\n\n"
            prompt += "5. **CLIENT INFORMATION** (also in Projects/ folders):\n"
            prompt += "   - Client contact details, past client projects\n"
            prompt += "   - Use case: Client relationship management, contact information\n\n"
            prompt += "CRITICAL: Do NOT mix document types! If someone asks about 'safety rules', only reference Policy documents, not project safety plans.\n\n"
            prompt += "DOCUMENT FILTERING INSTRUCTIONS:\n"
            prompt += "You will receive search results from multiple folders. Use INTELLIGENT PRIORITIZATION, not strict exclusion:\n\n"
            prompt += "**POLICY PROMPT Prioritization** ('safety rules', 'company policies', 'what do I need to follow'):\n"
            prompt += "- PRIORITIZE documents from: Policy/, Health & Safety/, IT Policy/, Employment/, Quality/, Operations/\n"
            prompt += "- If no policy documents found, consider H2H/ procedures as secondary source\n"
            prompt += "- Purpose: Employee compliance and mandatory rules\n\n"
            prompt += "**PROCEDURES PROMPT Prioritization** ('how do I use', 'best practices', 'DTCE approach'):\n"
            prompt += "- PRIORITIZE documents from: H2H/, Procedures/, Technical Procedures/\n"
            prompt += "- If no procedures found, consider Templates/ and relevant project examples\n"
            prompt += "- Purpose: Guidance on 'how we do things at DTCE'\n\n"
            prompt += "**STANDARDS PROMPT Prioritization** ('NZS requirements', 'building codes', 'code sections'):\n"
            prompt += "- PRIORITIZE documents from: Engineering/, Standards/, NZ Standards/\n"
            prompt += "- If no standards found, mention this and provide general guidance\n"
            prompt += "- Purpose: Official NZ engineering standards and codes\n\n"
            prompt += "**TEMPLATE/TOOL PROMPT Prioritization** ('template', 'spreadsheet', 'form', 'PS3', 'design tool'):\n"
            prompt += "- PRIORITIZE documents from: Templates/, Forms/, H2H/, Engineering/\n"
            prompt += "- ALSO CONSIDER: Project examples that show similar tools or templates in use\n"
            prompt += "- If no templates found, suggest where to find them or how to create them\n"
            prompt += "- Purpose: DTCE tools, templates, and design resources\n\n"
            prompt += "**PROJECT PROMPT Prioritization** ('past projects', 'show me examples', 'lessons learned'):\n"
            prompt += "- PRIORITIZE documents from: Projects/, etc.\n"
            prompt += "- Purpose: DTCE project work, client examples, project history\n\n"
            prompt += "**GENERAL RULE**: If no documents are found in the prioritized folders, be helpful and:\n"
            prompt += "1. Acknowledge what you searched for\n"
            prompt += "2. Use any relevant documents from other folders if they contain useful information\n"
            prompt += "3. Provide general guidance or external resources\n"
            prompt += "4. Suggest contacting DTCE directly for internal resources\n\n"
            
            prompt += "**INTELLIGENT ALTERNATIVES SYSTEM:**\n"
            prompt += "If the prioritized search results don't make sense or aren't relevant to the user's question:\n\n"
            prompt += "1. **EVALUATE RELEVANCE**: First determine if the primary results actually help answer the question\n"
            prompt += "2. **PROVIDE ALTERNATIVES**: If primary results aren't helpful, look for alternatives in:\n"
            prompt += "   - Documents from 'ignored' folders that might actually be relevant\n"
            prompt += "   - Example: If looking for safety info but only found project documents, still check if those project documents contain relevant safety information\n"
            prompt += "   - Example: If looking for procedures but only found policy documents, check if policies contain procedural guidance\n"
            prompt += "3. **LABEL CLEARLY**: Always label alternatives as 'Alternative from SuiteFiles:' so users know this is from a broader search\n"
            prompt += "4. **INCLUDE GENERAL KNOWLEDGE**: Also provide 'General Engineering Guidance:' using your knowledge of NZ standards and engineering practices\n"
            prompt += "5. **BE TRANSPARENT**: Explain why the primary search wasn't perfect and what alternatives you're providing\n\n"
            
            prompt += "**EXAMPLE ALTERNATIVE SCENARIOS:**\n"
            prompt += "- User asks about 'DTCE safety rules' → Primary search finds policies → If policies are empty, check project safety plans as alternative\n"
            prompt += "- User asks about 'how we do X' → Primary search finds procedures → If procedures don't cover X, check project examples as alternative\n"
            prompt += "- User asks about 'past projects' → Primary search finds project docs → If project docs don't match the query, provide general project management guidance\n\n"
            
            prompt += "IGNORE documents from inappropriate folders! Each document result includes folder information - use this to filter your response.\n\n"
            prompt += "SPECIAL NOTE FOR POLICY DOCUMENTS:\n"
            prompt += "- Some policy documents (e.g., Wellbeing Policy) may appear in search results but have minimal extracted content\n"
            prompt += "- If you find policy documents with limited content, acknowledge the document exists and provide general guidance about the topic\n"
            prompt += "- For wellbeing/wellness queries: Explain that DTCE has wellbeing policies and suggest contacting HR for detailed information\n"
            prompt += "- Always provide the SuiteFiles link even if content is limited\n\n"
            prompt += "SUITEFILES KNOWLEDGE INDICATORS - Questions that REQUIRE SuiteFiles data:\n"
            prompt += "- Contains pronouns: \"we\", \"we've\", \"our\", \"us\", \"DTCE has\", \"company\", \"past projects\"\n"
            prompt += "- Requests for PAST PROJECTS: \"past project\", \"previous project\", \"project examples\", \"projects that\", \"show me projects\"\n"
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
            prompt += "RESPONSE GUIDELINES BY FOLDER TYPE:\n\n"
            prompt += "**POLICY PROMPT (H&S, IT, Employment, Quality, Operations):**\n"
            prompt += "- Purpose: Documents that employees MUST follow\n"
            prompt += "- Use case: First search for compliance requirements, safety procedures, company rules\n"
            prompt += "- Response style: Authoritative, mandatory language ('You must...', 'DTCE requires...')\n"
            prompt += "- Always emphasize compliance obligations and refer to HR for clarification if needed\n"
            prompt += "- Example: 'According to DTCE's Health & Safety Policy, all employees must...'\n\n"
            prompt += "**TECHNICAL & ADMIN PROCEDURES PROMPT (H2H - How to Handbooks):**\n"
            prompt += "- Purpose: Best practices and 'how we do things at DTCE'\n"
            prompt += "- Use case: Staff guidance on processes ('how do I use the site wind speed spreadsheet')\n"
            prompt += "- Response style: Guidance-oriented, helpful ('DTCE's standard approach is...', 'Best practice at DTCE...')\n"
            prompt += "- Not as strict as policies - frame as recommendations and guidance\n"
            prompt += "- Example: 'The H2H handbook recommends the following approach for...'\n\n"
            prompt += "**NZ ENGINEERING STANDARDS PROMPT (Engineering/, Standards/):**\n"
            prompt += "- Purpose: Record of NZ engineering standards (PDFs) that DTCE has\n"
            prompt += "- Use case: Pre-search on specific codes and sections of codes\n"
            prompt += "- Response style: Technical, authoritative, reference official standards\n"
            prompt += "- These are NOT DTCE-specific - they are general industry standards\n"
            prompt += "- Always mention compliance requirements and official status\n"
            prompt += "- Example: 'According to NZS 3101, the design requirements are...'\n\n"
            prompt += "**PROJECT REFERENCE PROMPT (Projects/, etc.):**\n"
            prompt += "- Purpose: Search past DTCE project work for examples and lessons learned\n"
            prompt += "- Use case: Most complex - less structured data, project examples, client work\n"
            prompt += "- Response style: Specific examples with project numbers, quantitative data when available\n"
            prompt += "- Include project details: client, location, scope, lessons learned, costs/timelines if available\n"
            prompt += "- Look for patterns across multiple projects\n"
            prompt += "- Example: 'In Project 224156 with [Client], DTCE encountered similar challenges...'\n\n"
            prompt += "**CLIENT REFERENCE PROMPT (also in Projects/ folders):**\n"
            prompt += "- Purpose: Search for client information, contact details, past collaborations\n"
            prompt += "- Use case: Client relationship management, finding past work with specific clients\n"
            prompt += "- Response style: Relationship-focused, include contact info, project history\n"
            prompt += "- Aggregate all projects for a client to show relationship history\n"
            prompt += "- Example: 'DTCE has worked with [Client] on the following projects: [list with details]'\n\n"
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
            prompt += "5. **IF PRIMARY RESULTS DON'T MAKE SENSE**: Provide intelligent alternatives:\n"
            prompt += "   - Look through ALL the retrieved content for any documents that might be relevant (even from 'ignored' folders)\n"
            prompt += "   - Label these clearly as 'Alternative from SuiteFiles:'\n"
            prompt += "   - Also provide 'General Engineering Guidance:' using your knowledge\n"
            prompt += "   - Explain why the primary search wasn't perfect\n"
            prompt += "6. For COMPLEX ANALYSIS QUESTIONS (scenarios, lessons learned, cost insights, comparisons):\n"
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
            prompt += "1. Start with your answer (NO document references first)\n"
            prompt += "2. End with sources using EXACTLY this format:\n\n"
            prompt += "**Primary Sources:**\n"
            prompt += "- **[Document Name] (Project XXXXX)**: [QUOTE specific procedures, requirements, dates, numbers, or key content from this document. For example: 'Contains the lockout/tagout procedure requiring 3-step verification' or 'Specifies infection control measures implemented April 1, 2021 including mandatory temperature checks' or 'Lists the required PPE for electrical work: safety glasses, hard hat, and insulated gloves']\n"
            prompt += "  SuiteFiles Link: [link]\n"
            prompt += "  NOTE: If a document shows 'Project: Project XXXXX' in the retrieved content, include the project number in parentheses after the document name. If no project information is shown, just use **[Document Name]**:\n\n"
            prompt += "**Alternative that might be helpful:**\n"
            prompt += "- **[Document Name] (Project XXXXX)**: [QUOTE or describe specific sections/content that provide background or related information. For example: 'Section 3.2 covers site safety protocols for contaminated soil' or 'Contains the emergency contact procedures and evacuation routes for the Auckland office']\n"
            prompt += "  SuiteFiles Link: [link]\n"
            prompt += "  NOTE: Include project number if available in the retrieved content\n\n"
            prompt += "**General Engineering Guidance:**\n"
            prompt += "- [Resource]: [SPECIFIC standards, codes, or guidance that directly relate to the question]\n\n"
            prompt += "EXAMPLES OF GOOD vs BAD descriptions:\n"
            prompt += "BAD: 'Details DTCE's commitment to health and safety'\n"
            prompt += "GOOD: 'Specifies the updated infection control measures effective April 1, 2021, including site access restrictions, mandatory hand sanitizing, and social distancing requirements for project meetings'\n"
            prompt += "BAD: 'Contains safety information'\n"
            prompt += "GOOD: 'Section 4.1 outlines the electrical safety lockout/tagout procedure requiring three-point verification and supervisor sign-off before re-energizing circuits'\n\n"
            prompt += "NEVER use generic phrases like 'commitment to', 'outlines', 'details', 'highlights' - instead describe the ACTUAL CONTENT!\n\n"
            prompt += "CRITICAL: ONLY use the EXACT SuiteFiles links provided in the retrieved content above. DO NOT construct your own links or modify the provided URLs. If a document is mentioned in the retrieved content, use its exact link. If no link is provided for a document in the retrieved content, do not include it in your sources.\n\n"
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
        for doc in documents[:10]:  # Check more documents but limit final sources
            # Filter out superseded/archive documents at source formatting level too
            blob_name = doc.get('blob_name', '') or doc.get('filename', '')
            if self.folder_service.should_exclude_folder(blob_name):
                logger.debug("Excluded superseded document during source formatting", 
                           filename=doc.get('filename'), blob_name=blob_name)
                continue
                
            source = {
                'filename': doc.get('filename', 'Unknown'),
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
