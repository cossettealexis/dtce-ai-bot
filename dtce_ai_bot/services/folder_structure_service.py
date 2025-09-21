"""
DTCE Folder Structure Service
Manages SuiteFiles folder organization and document routing for intelligent search.
"""

from typing import Dict, List, Any, Optional
import structlog
import re

logger = structlog.get_logger(__name__)


class FolderStructureService:
    """
    Service for managing DTCE's SuiteFiles folder structure and document organization.
    
    Provides intelligent folder-based document filtering, relevance scoring,
    and category-specific search optimization for the DTCE knowledge base.
    """
    
    def __init__(self):
        """Initialize with DTCE's SuiteFiles folder structure mapping."""
        self.folder_mapping = {
            'policies': {
                'paths': [
                    'Health & Safety',
                    'IT Policies', 
                    'HR Policies',
                    'Company Policies',
                    'Procedures',
                    'Guidelines'
                ],
                'keywords': ['policy', 'procedure', 'guideline', 'protocol', 'standard operating'],
                'priority': 1.0
            },
            'procedures': {
                'paths': [
                    'H2H',
                    'How to How',
                    'Procedures',
                    'Technical Procedures',
                    'Admin Procedures',
                    'Process'
                ],
                'keywords': ['procedure', 'process', 'how to', 'step', 'instruction', 'method'],
                'priority': 1.0
            },
            'standards': {
                'paths': [
                    'NZ Standards',
                    'Standards',
                    'Technical Standards',
                    'Design Standards',
                    'Engineering Standards'
                ],
                'keywords': ['nzs', 'standard', 'specification', 'requirement', 'code'],
                'priority': 1.0
            },
            'projects': {
                'paths': [
                    'Projects',
                    'Project',
                    '220', '221', '222', '223', '224', '225'  # Year-based project folders
                ],
                'keywords': ['project', 'job', 'site', 'client', 'contract'],
                'priority': 0.9
            },
            'clients': {
                'paths': [
                    'Clients',
                    'Client Information',
                    'Contact Information'
                ],
                'keywords': ['client', 'contact', 'customer', 'stakeholder'],
                'priority': 0.8
            },
            'engineering': {
                'paths': [
                    'Engineering',
                    'Technical',
                    'Design',
                    'Calculations',
                    'Reports'
                ],
                'keywords': ['engineering', 'technical', 'design', 'calculation', 'analysis'],
                'priority': 0.7
            },
            'templates': {
                'paths': [
                    'Templates',
                    'Forms',
                    'Proformas',
                    'Standard Forms'
                ],
                'keywords': ['template', 'form', 'proforma', 'format'],
                'priority': 0.6
            }
        }
    
    def analyze_document_folder(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a document's folder location and categorize it.
        
        Args:
            document: Document dict with blob_url, filename, and other metadata
            
        Returns:
            Dictionary with folder analysis results
        """
        try:
            blob_url = document.get('blob_url', '')
            filename = document.get('filename', '')
            
            if not blob_url and not filename:
                return self._default_folder_analysis()
            
            # Extract folder path from blob URL
            folder_path = self._extract_folder_path(blob_url)
            
            # Determine category based on folder path and filename
            category = self._categorize_document(folder_path, filename)
            
            # Calculate relevance score
            relevance_score = self._calculate_folder_relevance(category, folder_path, filename)
            
            # Extract project information if applicable
            project_info = self._extract_project_info(blob_url, folder_path)
            
            return {
                'category': category,
                'folder_path': folder_path,
                'relevance_score': relevance_score,
                'project_info': project_info,
                'is_project_document': bool(project_info.get('project_number')),
                'priority_level': self.folder_mapping.get(category, {}).get('priority', 0.5)
            }
            
        except Exception as e:
            logger.warning("Folder analysis failed", error=str(e), document_id=document.get('id'))
            return self._default_folder_analysis()
    
    def filter_documents_by_relevance(
        self, 
        documents: List[Dict], 
        target_category: str, 
        max_results: int = 10
    ) -> List[Dict]:
        """
        Filter and rank documents based on folder relevance to target category.
        
        Args:
            documents: List of document dictionaries
            target_category: Target category for filtering
            max_results: Maximum number of results to return
            
        Returns:
            Filtered and ranked list of documents
        """
        try:
            logger.info(f"Filtering {len(documents)} documents for category: {target_category}")
            
            # Analyze each document's folder structure
            analyzed_docs = []
            for doc in documents:
                folder_analysis = self.analyze_document_folder(doc)
                doc['folder_analysis'] = folder_analysis
                
                # Calculate combined relevance score
                combined_score = self._calculate_combined_relevance(
                    doc, target_category, folder_analysis
                )
                doc['combined_relevance_score'] = combined_score
                
                analyzed_docs.append(doc)
            
            # Sort by combined relevance score (descending)
            sorted_docs = sorted(
                analyzed_docs, 
                key=lambda x: x.get('combined_relevance_score', 0), 
                reverse=True
            )
            
            # Filter out low-relevance documents for specific categories
            filtered_docs = self._apply_category_filters(sorted_docs, target_category)
            
            # Return top results
            final_results = filtered_docs[:max_results]
            
            logger.info(f"Filtered to {len(final_results)} relevant documents")
            
            return final_results
            
        except Exception as e:
            logger.error("Document filtering failed", error=str(e))
            return documents[:max_results]
    
    def get_search_filters_for_category(self, category: str) -> Dict[str, Any]:
        """
        Get Azure Search filters specific to a document category.
        
        Args:
            category: Document category (policies, procedures, standards, etc.)
            
        Returns:
            Dictionary with search filters and parameters
        """
        try:
            if category not in self.folder_mapping:
                return {'folder_filters': [], 'boost_terms': []}
            
            category_config = self.folder_mapping[category]
            
            # Build folder path filters
            folder_filters = []
            for path in category_config['paths']:
                folder_filters.append(f"search.ismatch('*{path}*', 'blob_url')")
            
            # Get boost terms for relevance scoring
            boost_terms = category_config['keywords']
            
            return {
                'folder_filters': folder_filters,
                'boost_terms': boost_terms,
                'priority_weight': category_config['priority']
            }
            
        except Exception as e:
            logger.warning("Search filter generation failed", error=str(e), category=category)
            return {'folder_filters': [], 'boost_terms': []}
    
    def _extract_folder_path(self, blob_url: str) -> str:
        """Extract folder path from blob URL."""
        if not blob_url:
            return ""
        
        try:
            # Remove the base URL and filename to get folder path
            if '/dtce-documents/' in blob_url:
                path_part = blob_url.split('/dtce-documents/')[1]
                # Remove filename (everything after the last '/')
                folder_path = '/'.join(path_part.split('/')[:-1])
                return folder_path
            
            return ""
            
        except Exception as e:
            logger.warning("Folder path extraction failed", error=str(e), blob_url=blob_url)
            return ""
    
    def _categorize_document(self, folder_path: str, filename: str) -> str:
        """Categorize document based on folder path and filename."""
        folder_path_lower = folder_path.lower()
        filename_lower = filename.lower()
        
        # Check each category mapping
        for category, config in self.folder_mapping.items():
            # Check folder paths
            for path in config['paths']:
                if path.lower() in folder_path_lower:
                    return category
            
            # Check keywords in filename
            for keyword in config['keywords']:
                if keyword.lower() in filename_lower:
                    return category
        
        # Default categorization based on common patterns
        if any(term in folder_path_lower for term in ['project', '220', '221', '222', '223', '224', '225']):
            return 'projects'
        elif any(term in folder_path_lower for term in ['standard', 'nzs']):
            return 'standards'
        elif any(term in folder_path_lower for term in ['policy', 'procedure']):
            return 'policies'
        else:
            return 'general'
    
    def _calculate_folder_relevance(self, category: str, folder_path: str, filename: str) -> float:
        """Calculate relevance score based on folder structure."""
        base_score = self.folder_mapping.get(category, {}).get('priority', 0.5)
        
        # Boost score for exact category matches
        if category in self.folder_mapping:
            config = self.folder_mapping[category]
            
            # Check for exact path matches
            for path in config['paths']:
                if path.lower() in folder_path.lower():
                    base_score += 0.2
                    break
            
            # Check for keyword matches in filename
            for keyword in config['keywords']:
                if keyword.lower() in filename.lower():
                    base_score += 0.1
                    break
        
        return min(base_score, 1.0)
    
    def _extract_project_info(self, blob_url: str, folder_path: str) -> Dict[str, Optional[str]]:
        """Extract project information from URL and folder path."""
        project_info = {
            'project_number': None,
            'project_year': None,
            'project_folder': None
        }
        
        try:
            # Look for project number patterns
            project_match = re.search(r'/Projects?/(\d{3})/(\d{6})/', blob_url, re.IGNORECASE)
            if project_match:
                project_info['project_year'] = project_match.group(1)
                project_info['project_number'] = project_match.group(2)
                project_info['project_folder'] = f"Projects/{project_match.group(1)}/{project_match.group(2)}"
            
            # Alternative pattern for simpler project structures
            elif re.search(r'/Projects?/(\d{6})/', blob_url, re.IGNORECASE):
                project_match = re.search(r'/Projects?/(\d{6})/', blob_url, re.IGNORECASE)
                project_info['project_number'] = project_match.group(1)
                # Extract year from project number (first 3 digits)
                if len(project_match.group(1)) >= 3:
                    project_info['project_year'] = project_match.group(1)[:3]
            
        except Exception as e:
            logger.debug("Project info extraction failed", error=str(e))
        
        return project_info
    
    def _calculate_combined_relevance(
        self, 
        document: Dict, 
        target_category: str, 
        folder_analysis: Dict
    ) -> float:
        """Calculate combined relevance score including search score and folder relevance."""
        # Get base search score
        search_score = document.get('@search.score', 0)
        
        # Normalize search score (typical range 0-4, normalize to 0-1)
        normalized_search_score = min(search_score / 4.0, 1.0)
        
        # Get folder relevance score
        folder_relevance = folder_analysis.get('relevance_score', 0.5)
        
        # Check if document category matches target category
        document_category = folder_analysis.get('category', 'general')
        category_match_bonus = 0.3 if document_category == target_category else 0
        
        # Combine scores with weights
        combined_score = (
            normalized_search_score * 0.4 +  # 40% search relevance
            folder_relevance * 0.4 +          # 40% folder relevance
            category_match_bonus               # 20% category match bonus
        )
        
        return combined_score
    
    def _apply_category_filters(self, documents: List[Dict], target_category: str) -> List[Dict]:
        """Apply category-specific filtering rules."""
        if target_category == 'projects':
            # For project searches, prefer actual project documents
            return [doc for doc in documents 
                   if doc.get('folder_analysis', {}).get('is_project_document', False) or
                      doc.get('combined_relevance_score', 0) > 0.3]
        
        elif target_category in ['policies', 'procedures']:
            # For policies/procedures, filter out project-specific documents
            return [doc for doc in documents 
                   if not doc.get('folder_analysis', {}).get('is_project_document', False) or
                      doc.get('combined_relevance_score', 0) > 0.5]
        
        else:
            # For other categories, use general relevance threshold
            return [doc for doc in documents 
                   if doc.get('combined_relevance_score', 0) > 0.2]
    
    def _default_folder_analysis(self) -> Dict[str, Any]:
        """Return default folder analysis for documents without clear structure."""
        return {
            'category': 'general',
            'folder_path': '',
            'relevance_score': 0.5,
            'project_info': {'project_number': None, 'project_year': None, 'project_folder': None},
            'is_project_document': False,
            'priority_level': 0.5
        }
