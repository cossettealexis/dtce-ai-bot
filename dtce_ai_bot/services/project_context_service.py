"""
Project Context Service - Manages project-specific context and information
"""

from typing import Dict, List, Any, Optional
import re
import structlog

logger = structlog.get_logger(__name__)


class ProjectContextService:
    """
    Service for managing project context and extracting project-specific information.
    Handles project number detection, year mapping, and project metadata.
    """
    
    def __init__(self):
        self.year_mapping = self._initialize_year_mapping()
        self.project_patterns = self._initialize_project_patterns()
    
    def _initialize_year_mapping(self) -> Dict[str, str]:
        """
        Initialize mapping of years to project folder structures.
        """
        return {
            '2025': '225',
            '2024': '224',
            '2023': '223',
            '2022': '222',
            '2021': '221',
            '2020': '220',
            '2019': '219',
            '2018': '218'
        }
    
    def _initialize_project_patterns(self) -> List[str]:
        """
        Initialize regex patterns for project number detection.
        """
        return [
            r'project\s+(\d{3,6})',
            r'proj\s+(\d{3,6})',
            r'job\s+(\d{3,6})',
            r'site\s+(\d{3,6})',
            r'\b(\d{6})\b',  # 6-digit project numbers like 224001
            r'\b22[0-9](\d{3})\b',  # 22XXXX format
            r'P-?(\d{3,6})',  # P-224001 format
            r'#(\d{3,6})'  # #224001 format
        ]
    
    def extract_project_context(self, query: str) -> Dict[str, Any]:
        """
        Extract project context from user query.
        
        Returns:
            Dictionary with project information including number, year, etc.
        """
        context = {
            'has_project_reference': False,
            'project_number': None,
            'project_year': None,
            'folder_path': None,
            'confidence': 0.0
        }
        
        try:
            # Extract project number
            project_number = self._extract_project_number(query)
            if project_number:
                context['has_project_reference'] = True
                context['project_number'] = project_number
                context['confidence'] = 0.9
                
                # Determine year from project number
                year = self._infer_year_from_project_number(project_number)
                if year:
                    context['project_year'] = year
                    context['folder_path'] = f"Projects/{self.year_mapping[year]}"
            
            # Extract explicit year references
            year_refs = self._extract_year_references(query)
            if year_refs and not context['project_year']:
                context['project_year'] = year_refs[0]
                if context['project_year'] in self.year_mapping:
                    context['folder_path'] = f"Projects/{self.year_mapping[context['project_year']]}"
            
            logger.info("Project context extracted", context=context)
            return context
            
        except Exception as e:
            logger.error("Failed to extract project context", error=str(e))
            return context
    
    def _extract_project_number(self, query: str) -> Optional[str]:
        """
        Extract project number using various patterns.
        """
        for pattern in self.project_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Get the captured group or the full match
                project_num = match.group(1) if len(match.groups()) > 0 else match.group(0)
                
                # Validate project number
                if self._validate_project_number(project_num):
                    logger.info("Project number extracted", number=project_num, pattern=pattern)
                    return project_num
        
        return None
    
    def _validate_project_number(self, project_num: str) -> bool:
        """
        Validate if the extracted number looks like a valid project number.
        """
        if not project_num.isdigit():
            return False
        
        num_length = len(project_num)
        
        # Valid project number lengths
        if num_length < 3 or num_length > 6:
            return False
        
        # 6-digit numbers should start with reasonable year codes
        if num_length == 6:
            year_prefix = project_num[:3]
            valid_prefixes = ['218', '219', '220', '221', '222', '223', '224', '225']
            return year_prefix in valid_prefixes
        
        return True
    
    def _infer_year_from_project_number(self, project_number: str) -> Optional[str]:
        """
        Infer the project year from the project number format.
        """
        if len(project_number) == 6:
            year_code = project_number[:3]
            
            # Map year codes to actual years
            year_code_mapping = {
                '218': '2018',
                '219': '2019', 
                '220': '2020',
                '221': '2021',
                '222': '2022',
                '223': '2023',
                '224': '2024',
                '225': '2025'
            }
            
            return year_code_mapping.get(year_code)
        
        # For 3-digit numbers, try to infer from context or use current year
        return None
    
    def _extract_year_references(self, query: str) -> List[str]:
        """
        Extract explicit year references from the query.
        """
        year_pattern = r'\b(20\d{2})\b'
        years = re.findall(year_pattern, query)
        
        # Filter to reasonable years for DTCE projects
        valid_years = [year for year in years if '2018' <= year <= '2025']
        
        return valid_years
    
    def generate_project_filter(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Generate Azure Search filter for project-specific searches.
        """
        if not context.get('has_project_reference'):
            return None
        
        project_number = context.get('project_number')
        if not project_number:
            return None
        
        # Create filter for blob_url containing project number
        return f"search.ismatch('*{project_number}*', 'blob_url')"
    
    def enhance_query_with_project_context(self, query: str, context: Dict[str, Any]) -> str:
        """
        Enhance the search query with project context.
        """
        enhanced_query = query
        
        if context.get('has_project_reference'):
            project_number = context.get('project_number')
            project_year = context.get('project_year')
            
            # Add project number variations to improve search
            if project_number:
                enhanced_query += f" {project_number}"
                
                # Add padded versions for better matching
                if len(project_number) == 3:
                    # Add potential 6-digit versions
                    for year_code in ['224', '223', '222']:
                        enhanced_query += f" {year_code}{project_number}"
            
            # Add year information
            if project_year:
                enhanced_query += f" {project_year}"
        
        return enhanced_query
    
    def get_project_metadata(self, project_number: str) -> Dict[str, Any]:
        """
        Get metadata for a specific project.
        In a full implementation, this could query a project database.
        """
        metadata = {
            'project_number': project_number,
            'estimated_year': self._infer_year_from_project_number(project_number),
            'folder_structure': self._get_expected_folder_structure(project_number),
            'document_types': ['pdf', 'docx', 'xlsx', 'dwg']
        }
        
        return metadata
    
    def _get_expected_folder_structure(self, project_number: str) -> List[str]:
        """
        Get the expected folder structure for a project.
        """
        base_folders = [
            '01 Correspondence',
            '02 Drawings', 
            '03 Calculations',
            '04 Reports',
            '05 Specifications',
            '06 Site Information',
            '07 Photos',
            '08 As Built'
        ]
        
        year = self._infer_year_from_project_number(project_number)
        if year and year in self.year_mapping:
            year_code = self.year_mapping[year]
            return [f"Projects/{year_code}/{project_number}/{folder}" for folder in base_folders]
        
        return [f"Projects/{project_number}/{folder}" for folder in base_folders]
