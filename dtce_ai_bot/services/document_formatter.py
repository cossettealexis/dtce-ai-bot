"""
Document Formatter Service

Single Responsibility: Format documents with appropriate context for different intents
"""

from typing import Dict, Any, List
import structlog

logger = structlog.get_logger(__name__)


class DocumentFormatter:
    """
    Responsible for formatting documents with appropriate context based on intent
    and project information.
    """
    
    def __init__(self, project_service=None):
        self.project_service = project_service
    
    def format_documents_for_intent(self, documents: List[Dict], intent_classification: Dict) -> str:
        """
        Format documents with intent-specific context and project information.
        
        Args:
            documents: List of document dictionaries
            intent_classification: The classified intent information
            
        Returns:
            Formatted document string for the AI prompt
        """
        if not documents:
            return "No documents found."
        
        formatted_docs = []
        for i, doc in enumerate(documents[:5], 1):
            formatted_doc = self._format_single_document(doc, i)
            formatted_docs.append(formatted_doc)
        
        return "\n\n".join(formatted_docs)
    
    def _format_single_document(self, doc: Dict[str, Any], index: int) -> str:
        """Format a single document with project context."""
        # Enrich document with project context
        enriched_doc = self.project_service.enrich_document_with_context(doc)
        
        filename = enriched_doc.get('filename', 'Unknown Document')
        content = enriched_doc.get('content', '')
        project_context = enriched_doc.get('project_context', {})
        
        # Build document header with project context
        doc_header = f"=== DOCUMENT {index}: {filename} ==="
        
        # Add project information if available
        if project_context.get('is_project_document'):
            project_desc = enriched_doc.get('project_description', '')
            doc_header += f"\n**PROJECT CONTEXT:** {project_desc}"
            doc_header += f"\n**PROJECT PATH:** {project_context['full_project_path']}"
            if project_context.get('project_subfolder'):
                doc_header += f"\n**SUBFOLDER:** {project_context['project_subfolder']}"
        
        # Add content
        formatted_doc = f"{doc_header}\n**CONTENT:**\n{content}\n=== END DOCUMENT {index} ==="
        return formatted_doc
    
    def build_project_context_section(self, project_stats: Dict[str, Any]) -> str:
        """Build the project context section for the AI prompt."""
        if project_stats['project_documents'] == 0:
            return ""
        
        section = "\n\n**PROJECT ANALYSIS:**"
        section += f"\n- Total documents: {project_stats['total_documents']}"
        section += f"\n- Project documents: {project_stats['project_documents']}"
        section += f"\n- Projects represented: {len(project_stats['projects_found'])}"
        section += f"\n- Years: {', '.join(map(str, project_stats['years_represented']))}"
        
        if project_stats['most_common_project']:
            most_common = project_stats['projects_found'][project_stats['most_common_project']]
            section += f"\n- Primary project: {project_stats['most_common_project']} ({most_common['year']}) - {most_common['count']} documents"
        
        return section
