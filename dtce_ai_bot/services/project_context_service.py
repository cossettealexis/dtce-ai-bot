"""
Project Context Service

Single Responsibility: Parse and analyze DTCE project folder structures
"""

from typing import Dict, Any, List
import re
import structlog

logger = structlog.get_logger(__name__)


class ProjectContextService:
    """
    Responsible for extracting project information from DTCE folder structures
    and analyzing project distribution in document sets.
    """
    
    def extract_project_info(self, blob_name: str) -> Dict[str, Any]:
        """
        Extract project information from DTCE folder structure.
        
        Folder pattern: Projects/{ProjectYear_Code}/{ProjectNumber}/{...}
        - ProjectYear_Code: 3-digit code (22X where X is year digit)
          - 225 = 2025, 224 = 2024, 223 = 2023, etc.
        - ProjectNumber: 6-digit number starting with ProjectYear_Code
          - e.g., 225001, 224015, 223045
        
        Args:
            blob_name: Full path like "Projects/225/225001/Documents/Report.pdf"
            
        Returns:
            Dict with project_year, project_number, full_project_path, is_project_document
        """
        project_info = {
            'is_project_document': False,
            'project_year': None,
            'project_year_code': None,
            'project_number': None,
            'full_project_path': None,
            'project_subfolder': None
        }
        
        # Pattern to match DTCE project structure
        # Projects/{year_code}/{project_number}/{optional_subfolders}/{filename}
        project_pattern = r'Projects/(\d{3})/(\d{6})(?:/(.+?))?/[^/]+$'
        
        match = re.search(project_pattern, blob_name, re.IGNORECASE)
        
        if match:
            year_code = match.group(1)
            project_number = match.group(2)
            subfolder_path = match.group(3) if match.group(3) else ""
            
            # Convert year code to actual year (22X -> 20XX)
            actual_year = self._convert_year_code(year_code)
            
            # Validate that project number starts with year code
            if project_number.startswith(year_code):
                project_info.update({
                    'is_project_document': True,
                    'project_year': actual_year,
                    'project_year_code': year_code,
                    'project_number': project_number,
                    'full_project_path': f"Projects/{year_code}/{project_number}",
                    'project_subfolder': subfolder_path
                })
        
        return project_info
    
    def enrich_document_with_context(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich document with extracted project context."""
        enriched_doc = doc.copy()
        
        # Extract project info from blob_name or filename
        blob_name = doc.get('blob_name', '') or doc.get('filename', '')
        project_info = self.extract_project_info(blob_name)
        
        # Add project context to document
        enriched_doc['project_context'] = project_info
        
        # Add human-readable project description
        if project_info['is_project_document']:
            enriched_doc['project_description'] = (
                f"Project {project_info['project_number']} ({project_info['project_year']})"
            )
            if project_info['project_subfolder']:
                enriched_doc['project_description'] += f" - {project_info['project_subfolder']}"
        
        return enriched_doc
    
    def analyze_project_distribution(self, documents: List[Dict]) -> Dict[str, Any]:
        """Analyze the project distribution in search results to provide context."""
        project_stats = {
            'total_documents': len(documents),
            'project_documents': 0,
            'non_project_documents': 0,
            'projects_found': {},
            'years_represented': set(),
            'most_common_project': None
        }
        
        for doc in documents:
            project_info = self.extract_project_info(
                doc.get('blob_name', '') or doc.get('filename', '')
            )
            
            if project_info['is_project_document']:
                self._update_project_stats(project_stats, project_info)
            else:
                project_stats['non_project_documents'] += 1
        
        # Find most common project
        if project_stats['projects_found']:
            project_stats['most_common_project'] = max(
                project_stats['projects_found'].items(),
                key=lambda x: x[1]['count']
            )[0]
        
        project_stats['years_represented'] = sorted(list(project_stats['years_represented']))
        
        return project_stats
    
    def _convert_year_code(self, year_code: str) -> int:
        """Convert year code to actual year (22X -> 20XX)."""
        if year_code.startswith('22'):
            return 2000 + int(year_code)
        return None
    
    def _update_project_stats(self, project_stats: Dict, project_info: Dict) -> None:
        """Update project statistics with new project info."""
        project_stats['project_documents'] += 1
        project_num = project_info['project_number']
        year = project_info['project_year']
        
        if project_num not in project_stats['projects_found']:
            project_stats['projects_found'][project_num] = {
                'count': 0,
                'year': year,
                'subfolders': set()
            }
        
        project_stats['projects_found'][project_num]['count'] += 1
        project_stats['years_represented'].add(year)
        
        if project_info.get('project_subfolder'):
            project_stats['projects_found'][project_num]['subfolders'].add(
                project_info['project_subfolder']
            )
