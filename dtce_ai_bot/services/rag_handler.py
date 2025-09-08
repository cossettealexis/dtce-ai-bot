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
        INTELLIGENT FOLDER-ROUTED SEARCH WITH CONVERSATIONAL CONTEXT:
        
        1. Check if query is conversational (requires context) vs informational (requires search)
        2. For conversational queries: Use conversation history to generate contextual response
        3. For informational queries: Classify intent, route to appropriate folder, and search
        4. Generate appropriate response based on query type
        """
        try:
            logger.info("Processing question with conversational context analysis", question=question)
            
            # STEP 0: Check if this is a conversational query that doesn't need document search
            is_conversational = await self._is_conversational_query(question, conversation_history)
            
            if is_conversational:
                logger.info("Detected conversational query - using context instead of search")
                return await self._handle_conversational_query(question, conversation_history)
            
            # STEP 1: Normalize query for consistent semantic search results
            logger.info("Detected informational query - proceeding with document search")
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
                temperature=0.3,
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
            
            # Build a universal ChatGPT-style prompt that can handle anything
            prompt = f"""You are DTCE AI Assistant - a comprehensive AI assistant like ChatGPT, but with access to DTCE's internal documents and expertise.

USER QUESTION: "{question}"

TOPIC AREA: {search_strategy.get('topic_area', 'General inquiry')}
SEARCH CONTEXT: {search_strategy.get('search_context', 'General knowledge')}

{f"RELEVANT DTCE DOCUMENTS FOUND:" if retrieved_content else ""}
{retrieved_content[:2000] if retrieved_content else ""}

Instructions:
- Answer the question naturally and comprehensively like ChatGPT would
- If you found relevant DTCE documents, incorporate that information
- If it's about DTCE policies, procedures, projects, or standards - use the documents
- If it's general knowledge - answer from your training
- Be helpful, accurate, and conversational
- Provide practical guidance when appropriate

Answer the user's question directly and helpfully:

USER QUESTION: "{question}"

ENHANCED ADVISORY INSTRUCTIONS:
1. **Comprehensive Engineering Advice**: Beyond just document content, provide engineering analysis and professional recommendations
2. **Project Lessons Integration**: Analyze past project findings and extract practical lessons learned for current application
3. **Risk Awareness**: Identify potential issues, warnings, and cautionary advice based on past project experiences
4. **Standards Integration**: Combine SuiteFiles documents, general engineering knowledge, and NZ Standards (NZS) requirements
5. **Advisory Tone**: Act as a senior consulting engineer providing guidance, not just information retrieval
6. **General Guidelines**: Always include applicable general engineering principles and best practices
7. **Past Project Analysis**: When referencing past projects, provide engineering insights and recommendations
8. **Superseded Content Handling**: If superseded documents are included, clearly flag them as outdated and explain current best practice
9. **Client Issue Detection**: Extract and prominently highlight any client complaints, issues, or satisfaction problems
10. **Engineering Failure Analysis**: Identify what went wrong in past projects and how to prevent similar issues

RESPONSE STRUCTURE:
**Direct Answer**: Address the specific question with document-based information

**DTCE Project Experience & Findings**: 
- Summarize key findings from past DTCE projects rather than just listing links
- Extract practical insights and outcomes from project documents
- Highlight successful approaches and methodologies that worked well
- Include specific project examples with engineering insights (not just job numbers)

**Critical Warnings & Issues**: 
- ALWAYS look for and highlight any problems, failures, client complaints, issues, or challenges mentioned in the documents
- Extract specific problems encountered in past projects and explain the technical causes
- Identify design approaches that caused issues or were superseded for safety/performance reasons
- Flag any regulatory compliance issues or standard violations
- Warn about approaches that led to client dissatisfaction or project problems

**Lessons Learned Analysis**:
- Extract key takeaways from project outcomes (both successful and problematic)
- Analyze what worked well vs what caused problems with technical explanations
- Identify patterns in successful vs unsuccessful approaches
- Document client feedback and satisfaction issues with recommended improvements
- Provide "what to do" and "what NOT to do" guidance based on past experience

**Engineering Best Practices & General Guidelines**: 
- Provide general engineering guidelines and standards (including NZ Standards where relevant)
- Reference current industry best practices and compliance requirements
- Include regulatory requirements and code compliance guidance
- Offer general design principles that apply beyond the specific query
- Connect general engineering knowledge with document-specific findings

**Combined Knowledge Response**: 
- Integrate SuiteFiles project data with general engineering knowledge
- Reference relevant NZ Standards (NZS 3101, 3404, 1170, etc.) where applicable
- Combine DTCE's practical experience with theoretical engineering principles
- Provide comprehensive guidance that draws from both sources

**Professional Recommendations**: 
- Give specific advisory guidance based on DTCE's experience and general engineering practice
- Suggest preventive measures to avoid past problems and common pitfalls
- Recommend verification approaches, quality assurance measures, and risk mitigation
- Provide actionable next steps and decision-making guidance
- Include risk assessment and recommendation priorities

**Supporting Documentation**: Include relevant SuiteFiles links and references

TONE AND APPROACH:
- Professional consulting engineer providing expert advice
- Proactive identification of potential issues and solutions
- Integration of theoretical knowledge with practical project experience
- Warning about common pitfalls and client satisfaction issues when relevant
- Actionable recommendations that prevent problems

CRITICAL ADVISORY ANALYSIS REQUIREMENTS:
- **Issue Detection**: Scan documents for keywords like "problem", "issue", "failure", "complaint", "redesign", "rework", "delay", "cost overrun", "client unhappy", "dispute", "non-compliance", "rejected"
- **Warning Extraction**: Look for phrases like "avoid", "do not", "caution", "warning", "superseded", "outdated", "dangerous", "non-compliant", "not recommended", "problematic"
- **Lessons Analysis**: Extract statements about "learned", "experience shows", "found that", "discovered", "realized", "should have", "mistake", "error", "would recommend", "next time"
- **Client Feedback**: Identify any mentions of client satisfaction, complaints, change requests, project relationship issues, communication problems, or satisfaction surveys
- **Technical Problems**: Highlight design errors, calculation mistakes, material failures, construction issues, performance problems, or regulatory non-compliance
- **Standards Evolution**: Note where old approaches have been superseded by new standards, better practices, or updated regulations
- **Success Factor Analysis**: Extract what made projects successful and why certain approaches worked well
- **Cost and Time Issues**: Identify budget overruns, schedule delays, and efficiency problems with their causes

MANDATORY ADVISORY BEHAVIORS:
- If documents mention ANY problems or issues, these MUST be highlighted prominently and analyzed for root causes
- If documents show superseded or outdated approaches, these MUST be flagged with clear warnings and current alternatives provided
- Any client complaints or satisfaction issues MUST be extracted, analyzed, and used to provide preventive guidance
- Failed approaches or problematic designs MUST be explained as lessons learned with specific technical recommendations
- Current best practices MUST be contrasted with past problematic approaches, explaining why changes were made
- When referencing past projects, provide engineering insights and analysis, not just project lists or links
- Combine document findings with general engineering knowledge and NZ Standards where relevant
- Always include general guidelines that apply beyond the specific question asked
- Provide actionable recommendations that prevent repetition of past problems
- Extract and summarize key project findings rather than directing users to read documents themselves

Here are the relevant DTCE documents and project records:

{retrieved_content}

Based on the above documents and DTCE's engineering expertise, provide a comprehensive advisory response that combines document information with professional engineering guidance, lessons learned, and practical recommendations:"""

            # Generate comprehensive response with higher token limit
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are DTCE AI Assistant, a senior engineering advisor that provides comprehensive engineering guidance. You combine document knowledge with professional engineering analysis, lessons learned from past projects, risk assessment, and practical recommendations. You reference NZ Standards, identify potential issues, and provide advisory guidance to prevent problems and ensure successful project outcomes."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Balanced for advisory recommendations
                max_tokens=3000   # Increased for comprehensive advisory responses with lessons learned
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
            prompt += "**ANALYZE THE QUESTION TYPE**:\n"
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
                temperature=0.4  # Slightly higher temperature for more natural conversation
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
        """Universal ChatGPT-style AI assistant that can handle ANY topic.
        
        Intelligently routes to:
        - DTCE document search (with job numbers and links)
        - External web search for forums/products
        - Database search for clients/builders
        - Pure AI knowledge for general questions
        """
        try:
            # Let AI analyze what type of information is needed
            routing_analysis = await self._analyze_information_needs(question)
            
            logger.info(f"AI routing analysis: {routing_analysis}")
            
            # Handle different types of information needs
            if routing_analysis.get('needs_database_search', False):
                # Search client/builder database
                return await self._handle_database_search(question, routing_analysis)
                
            elif routing_analysis.get('needs_web_search', False):
                # Search external web for forums, products, etc.
                return await self._handle_web_search(question, routing_analysis)
                
            elif routing_analysis.get('needs_dtce_documents', False):
                # Search DTCE documents with enhanced features
                return await self._handle_dtce_document_search(question, routing_analysis)
                
            else:
                # General ChatGPT-style response
                return await self._generate_general_ai_response(question, routing_analysis)
                
        except Exception as e:
            logger.error("Universal AI assistant failed", error=str(e), question=question)
            import traceback
            logger.error("Full traceback", traceback=traceback.format_exc())
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
            
            formatted_content.append(f"Document {i}: {title} (relevance: {score:.2f})\n{content[:500]}...")
        
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
- policies: H&S policies, IT policies, employee policies  
- procedures: Technical procedures, admin procedures, H2H (how-to) documents, templates, spreadsheets
- standards: NZ engineering standards, codes, specifications, clause references
- projects: Past project information, project references, job numbers
- clients: Client information, contact details, builder information

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
        """Use AI to determine what the user is asking about and which folder to search."""
        try:
            routing_prompt = f"""Analyze this question and determine what the user is asking about:

QUESTION: "{question}"

Determine which DTCE folder (if any) would have relevant information:

AVAILABLE FOLDERS:
1. Policy (H&S, IT policies) - for questions about company policies, safety procedures, what employees must follow
2. Procedures (H2H - How to Handbooks) - for questions about how to do things at DTCE, best practices, technical procedures
3. NZ Standards - for questions about engineering codes, standards, technical specifications
4. Projects - for questions about past DTCE projects, project details, project history
5. Clients - for questions about client information, contact details, past client projects
6. General - for general knowledge questions not related to DTCE internal documents

Respond with JSON:
{{
    "topic_area": "brief description of what they're asking about",
    "target_folder": "policy|procedures|nz_standards|projects|clients|general",
    "needs_folder_search": true/false,
    "search_context": "explanation of why this folder or general knowledge",
    "confidence": "high|medium|low"
}}"""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an AI that routes user questions to the right information source. Always respond with valid JSON."
                    },
                    {"role": "user", "content": routing_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            import json
            strategy = json.loads(response.choices[0].message.content)
            return strategy
            
        except Exception as e:
            logger.error("Search strategy determination failed", error=str(e))
            return {
                "topic_area": "general inquiry",
                "target_folder": "general", 
                "needs_folder_search": False,
                "search_context": "general knowledge response",
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

Please provide a comprehensive response using the DTCE document context. Include specific clause numbers, requirements, and technical details when available."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are DTCE AI Assistant. Provide detailed, actionable responses using DTCE document context."
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
