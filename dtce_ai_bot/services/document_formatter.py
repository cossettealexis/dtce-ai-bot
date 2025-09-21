"""
Document Formatter Service - Formats retrieved documents for optimal LLM processing
"""

from typing import List, Dict, Any, Optional
import re
import structlog

logger = structlog.get_logger(__name__)


class DocumentFormatter:
    """
    Service for formatting retrieved documents for optimal LLM processing.
    Implements strategic chunking and metadata integration as described in RAG requirements.
    """
    
    def __init__(self):
        self.max_content_length = 3500  # Characters per document section
        self.max_total_length = 8000    # Total characters for all documents
    
    def format_documents_for_rag(
        self, 
        documents: List[Dict], 
        query: str,
        category: str = "general",
        include_metadata: bool = True
    ) -> str:
        """
        Format documents for RAG processing with optimal structure for LLM consumption.
        
        Args:
            documents: List of retrieved documents
            query: Original user query for relevance optimization
            category: Query category for specialized formatting
            include_metadata: Whether to include document metadata
            
        Returns:
            Formatted string ready for LLM processing
        """
        try:
            logger.info("Formatting documents for RAG", 
                       doc_count=len(documents), 
                       category=category)
            
            if not documents:
                return "No relevant documents found in the DTCE database."
            
            # Apply category-specific formatting
            if category == 'project_reference':
                return self._format_project_documents(documents, query, include_metadata)
            elif category == 'nz_standards':
                return self._format_standards_documents(documents, query, include_metadata)
            elif category in ['policy', 'procedures']:
                return self._format_policy_procedure_documents(documents, query, include_metadata)
            else:
                return self._format_general_documents(documents, query, include_metadata)
            
        except Exception as e:
            logger.error("Document formatting failed", error=str(e))
            return self._fallback_format(documents)
    
    def _format_project_documents(
        self, 
        documents: List[Dict], 
        query: str, 
        include_metadata: bool
    ) -> str:
        """
        Format project documents with project-specific context.
        """
        formatted_docs = []
        
        for i, doc in enumerate(documents[:6], 1):  # Limit to 6 project docs
            content = self._extract_document_content(doc)
            if not content:
                continue
            
            # Extract project information
            project_info = self._extract_project_metadata(doc)
            
            doc_section = f"**DOCUMENT {i}:** {doc.get('filename', 'Unknown')}"
            
            if include_metadata and project_info:
                if project_info.get('project_number'):
                    doc_section += f"\n**Project:** Project {project_info['project_number']}"
                if project_info.get('folder'):
                    doc_section += f"\n**Folder:** {project_info['folder']}"
                if project_info.get('year'):
                    doc_section += f"\n**Year:** {project_info['year']}"
            
            # Add optimized content
            optimized_content = self._optimize_content_for_query(content, query)
            doc_section += f"\n**Content:**\n{optimized_content}"
            
            formatted_docs.append(doc_section)
        
        return "\n\n---\n\n".join(formatted_docs)
    
    def _format_standards_documents(
        self, 
        documents: List[Dict], 
        query: str, 
        include_metadata: bool
    ) -> str:
        """
        Format NZ standards documents with technical focus.
        """
        formatted_docs = []
        
        for i, doc in enumerate(documents[:5], 1):  # Limit to 5 standards docs
            content = self._extract_document_content(doc)
            if not content:
                continue
            
            filename = doc.get('filename', 'Unknown')
            doc_section = f"**NZ STANDARD {i}:** {filename}"
            
            # Extract standard number from filename
            standard_number = self._extract_standard_number(filename)
            if standard_number:
                doc_section += f"\n**Standard:** {standard_number}"
            
            if include_metadata:
                folder = self._extract_folder_from_blob_url(doc.get('blob_url', ''))
                if folder:
                    doc_section += f"\n**Section:** {folder}"
            
            # Focus on technical content
            technical_content = self._extract_technical_content(content, query)
            doc_section += f"\n**Technical Content:**\n{technical_content}"
            
            formatted_docs.append(doc_section)
        
        return "\n\n---\n\n".join(formatted_docs)
    
    def _format_policy_procedure_documents(
        self, 
        documents: List[Dict], 
        query: str, 
        include_metadata: bool
    ) -> str:
        """
        Format policy and procedure documents with procedural focus.
        """
        formatted_docs = []
        
        for i, doc in enumerate(documents[:5], 1):
            content = self._extract_document_content(doc)
            if not content:
                continue
            
            filename = doc.get('filename', 'Unknown')
            doc_section = f"**DOCUMENT {i}:** {filename}"
            
            if include_metadata:
                folder = self._extract_folder_from_blob_url(doc.get('blob_url', ''))
                if folder:
                    doc_section += f"\n**Category:** {folder}"
            
            # Extract procedural content
            procedural_content = self._extract_procedural_content(content, query)
            doc_section += f"\n**Content:**\n{procedural_content}"
            
            formatted_docs.append(doc_section)
        
        return "\n\n---\n\n".join(formatted_docs)
    
    def _format_general_documents(
        self, 
        documents: List[Dict], 
        query: str, 
        include_metadata: bool
    ) -> str:
        """
        General document formatting for mixed content types.
        """
        formatted_docs = []
        total_length = 0
        
        for i, doc in enumerate(documents, 1):
            if total_length >= self.max_total_length:
                break
            
            content = self._extract_document_content(doc)
            if not content:
                continue
            
            filename = doc.get('filename', 'Unknown')
            doc_section = f"**DOCUMENT {i}:** {filename}"
            
            if include_metadata:
                metadata = self._format_document_metadata(doc)
                if metadata:
                    doc_section += f"\n{metadata}"
            
            # Optimize content length
            remaining_length = self.max_total_length - total_length
            available_length = min(self.max_content_length, remaining_length - len(doc_section) - 100)
            
            if available_length > 100:
                optimized_content = self._optimize_content_for_query(content, query, available_length)
                doc_section += f"\n**Content:**\n{optimized_content}"
                
                formatted_docs.append(doc_section)
                total_length += len(doc_section)
            
            if len(formatted_docs) >= 8:  # Limit to 8 documents
                break
        
        return "\n\n---\n\n".join(formatted_docs)
    
    def _extract_document_content(self, doc: Dict) -> str:
        """
        Extract content from document with fallbacks.
        """
        content = (
            doc.get('content') or 
            doc.get('text') or 
            doc.get('body') or 
            doc.get('description') or
            ""
        )
        
        return content.strip() if content else ""
    
    def _extract_project_metadata(self, doc: Dict) -> Dict[str, str]:
        """
        Extract project-specific metadata from document.
        """
        metadata = {}
        
        blob_url = doc.get('blob_url', '')
        filename = doc.get('filename', '')
        
        # Extract project number from blob URL
        project_match = re.search(r'/Projects/\d{3}/(\d{6})/', blob_url, re.IGNORECASE)
        if project_match:
            metadata['project_number'] = project_match.group(1)
        
        # Extract year from blob URL
        year_match = re.search(r'/Projects/(\d{3})/', blob_url, re.IGNORECASE)
        if year_match:
            year_code = year_match.group(1)
            # Convert year code to actual year
            year_mapping = {'225': '2025', '224': '2024', '223': '2023', '222': '2022'}
            metadata['year'] = year_mapping.get(year_code, f"20{year_code[-2:]}")
        
        # Extract folder information
        folder = self._extract_folder_from_blob_url(blob_url)
        if folder:
            metadata['folder'] = folder
        
        return metadata
    
    def _extract_folder_from_blob_url(self, blob_url: str) -> str:
        """
        Extract meaningful folder information from blob URL.
        """
        if not blob_url:
            return ""
        
        # Extract the last meaningful folder before filename
        parts = blob_url.split('/')
        if len(parts) > 2:
            # Skip the filename and get the parent folder
            for i in range(len(parts) - 2, -1, -1):
                folder = parts[i]
                if folder and not folder.startswith('dtce-') and folder != 'suitefiles':
                    return folder
        
        return ""
    
    def _extract_standard_number(self, filename: str) -> str:
        """
        Extract NZ standard number from filename.
        """
        patterns = [
            r'(NZS\s*\d+(?:\.\d+)*)',
            r'(AS/NZS\s*\d+(?:\.\d+)*)',
            r'(NZBC\s*[A-Z]\d*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ""
    
    def _optimize_content_for_query(
        self, 
        content: str, 
        query: str, 
        max_length: Optional[int] = None
    ) -> str:
        """
        Optimize content based on query relevance and length constraints.
        """
        if not content:
            return "No content available."
        
        max_length = max_length or self.max_content_length
        
        if len(content) <= max_length:
            return content
        
        # Extract query keywords for relevance scoring
        query_words = set(query.lower().split())
        
        # Split content into sentences
        sentences = re.split(r'[.!?]+', content)
        
        # Score sentences by query relevance
        scored_sentences = []
        for sentence in sentences:
            if len(sentence.strip()) < 10:  # Skip very short sentences
                continue
            
            sentence_lower = sentence.lower()
            score = sum(1 for word in query_words if word in sentence_lower)
            
            scored_sentences.append((sentence.strip(), score))
        
        # Sort by relevance and take top sentences within length limit
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        selected_content = []
        current_length = 0
        
        for sentence, score in scored_sentences:
            if current_length + len(sentence) + 2 <= max_length:  # +2 for ". "
                selected_content.append(sentence)
                current_length += len(sentence) + 2
            else:
                break
        
        if not selected_content:
            # Fallback: truncate original content
            return content[:max_length] + "..."
        
        return '. '.join(selected_content)
    
    def _extract_technical_content(self, content: str, query: str) -> str:
        """
        Extract technical content relevant to engineering queries.
        """
        # Look for technical patterns
        technical_patterns = [
            r'clause\s+\d+(?:\.\d+)*[^.]*\.',
            r'section\s+\d+(?:\.\d+)*[^.]*\.',
            r'\d+\s*mpa[^.]*\.',
            r'design\s+[^.]*\.',
            r'load[^.]*\.',
            r'strength[^.]*\.',
            r'factor[^.]*\.'
        ]
        
        technical_sentences = []
        for pattern in technical_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            technical_sentences.extend(matches)
        
        if technical_sentences:
            # Combine and optimize technical content
            tech_content = ' '.join(technical_sentences)
            return self._optimize_content_for_query(tech_content, query)
        
        # Fallback to general optimization
        return self._optimize_content_for_query(content, query)
    
    def _extract_procedural_content(self, content: str, query: str) -> str:
        """
        Extract procedural content like steps, requirements, guidelines.
        """
        # Look for procedural patterns
        procedural_patterns = [
            r'step\s+\d+[^.]*\.',
            r'\d+\.\s+[^.]*\.',
            r'procedure[^.]*\.',
            r'requirement[^.]*\.',
            r'guideline[^.]*\.',
            r'process[^.]*\.'
        ]
        
        procedural_sentences = []
        for pattern in procedural_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            procedural_sentences.extend(matches)
        
        if procedural_sentences:
            proc_content = ' '.join(procedural_sentences)
            return self._optimize_content_for_query(proc_content, query)
        
        return self._optimize_content_for_query(content, query)
    
    def _format_document_metadata(self, doc: Dict) -> str:
        """
        Format document metadata for display.
        """
        metadata_parts = []
        
        # Project information
        project_info = self._extract_project_metadata(doc)
        if project_info.get('project_number'):
            metadata_parts.append(f"**Project:** {project_info['project_number']}")
        
        # Folder information
        folder = self._extract_folder_from_blob_url(doc.get('blob_url', ''))
        if folder:
            metadata_parts.append(f"**Folder:** {folder}")
        
        return '\n'.join(metadata_parts)
    
    def _fallback_format(self, documents: List[Dict]) -> str:
        """
        Fallback formatting when main formatting fails.
        """
        if not documents:
            return "No documents available."
        
        simple_docs = []
        for i, doc in enumerate(documents[:5], 1):
            filename = doc.get('filename', f'Document {i}')
            content = self._extract_document_content(doc)
            
            if content:
                # Simple truncation
                truncated_content = content[:500] + "..." if len(content) > 500 else content
                simple_docs.append(f"**{filename}:**\n{truncated_content}")
        
        return "\n\n---\n\n".join(simple_docs)
