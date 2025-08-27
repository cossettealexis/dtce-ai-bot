"""
Folder Structure Service for DTCE AI Bot
Maps folder naming conventions and provides context for better search results
"""

import re
from typing import Dict, List, Optional, Tuple, Any
import structlog

logger = structlog.get_logger(__name__)


class FolderStructureService:
    """Service to understand DTCE folder structure and naming conventions."""
    
    def __init__(self):
        """Initialize folder structure mappings."""
        self.folder_mappings = self._initialize_folder_mappings()
        self.excluded_folders = self._initialize_excluded_folders()
        self.year_mappings = self._initialize_year_mappings()
        
    def _initialize_folder_mappings(self) -> Dict[str, Dict[str, str]]:
        """Define folder structure and what each folder contains."""
        return {
            # Project folder structure
            "projects": {
                "225": "2025 Projects",
                "224": "2024 Projects", 
                "223": "2023 Projects",
                "222": "2022 Projects",
                "221": "2021 Projects",
                "220": "2020 Projects",
                "219": "2019 Projects",
                "218": "2018 Projects",
                "217": "2017 Projects",
                "216": "2016 Projects",
                "215": "2015 Projects"
            },
            
            # Standard project subfolders
            "project_subfolders": {
                "01 Admin Documents": "Administrative documents, contracts, briefs",
                "01 Fees & Invoice": "Fee schedules, invoices, billing documents",
                "02 Quality Assurance": "QA documents, reviews, compliance checks",
                "02 Emails": "Email communications and correspondence",
                "03 RFI": "Requests for Information and responses",
                "04 Reports": "Final reports, analysis reports, assessment reports",
                "05 Calculations": "Structural calculations, engineering analysis",
                "06 Drawings": "Technical drawings, plans, sections, details",
                "07 Specifications": "Material specifications, technical requirements",
                "08 Site Photos": "Site photographs and visual documentation",
                "09 Reference": "Reference materials, standards, guidelines"
            },
            
            # Company policies and procedures
            "policies": {
                "Health & Safety": "H&S policies, safety procedures, compliance documents",
                "IT Policy": "IT policies, computer use, security guidelines",
                "Employment": "Employment policies, onboarding, HR procedures",
                "Quality": "Quality management, procedures, standards",
                "Operations": "Operational procedures, business processes"
            },
            
            # Technical resources
            "technical": {
                "Engineering Standards": "NZ Standards, building codes, technical references",
                "Design Guidelines": "DTCE design methodologies, best practices",
                "Templates": "Calculation templates, report templates, forms",
                "Software Resources": "Software tools, spreadsheets, utilities",
                "Training Materials": "Technical training, CPD materials"
            },
            
            # H2H (How to Handbooks)
            "procedures": {
                "H2H": "How to Handbooks - DTCE procedures and best practices",
                "Technical Procedures": "Technical step-by-step procedures",
                "Admin Procedures": "Administrative and office procedures",
                "Engineering Procedures": "Engineering workflow and processes"
            }
        }
    
    def _initialize_excluded_folders(self) -> List[str]:
        """Define folders that should be excluded from search."""
        return [
            "superseded",
            "superceded",  # Common misspelling
            "archive", 
            "archived",
            "old",
            "backup",
            "temp",
            "temporary",
            "draft",
            "drafts",
            "obsolete",
            "deprecated",
            "legacy",
            "trash",
            "deleted",
            "recycle",
            "_old",
            "_archive",
            "_superseded",
            "_superceded",
            "00 Archive",
            "00 Superseded",
            "00 Superceded",
            "99 Archive",
            "99 Superseded",
            "99 Superceded",
            "archive - superseded",
            "superseded - archive",
            "superceded - archive",
            "old version",
            "old versions",
            "previous version",
            "previous versions"
        ]
    
    def _initialize_year_mappings(self) -> Dict[str, str]:
        """Map folder codes to years."""
        return {
            "225": "2025",
            "224": "2024", 
            "223": "2023",
            "222": "2022",
            "221": "2021",
            "220": "2020",
            "219": "2019",
            "218": "2018",
            "217": "2017",
            "216": "2016",
            "215": "2015"
        }
    
    def get_all_project_folders(self) -> List[str]:
        """Get all project folder codes dynamically from year mappings."""
        return list(self.year_mappings.keys())
    
    def get_recent_project_folders(self, years_back: int = 5) -> List[str]:
        """Get recent project folder codes dynamically."""
        from datetime import datetime
        current_year = datetime.now().year
        recent_folders = []
        
        for folder_code, year_str in self.year_mappings.items():
            year = int(year_str)
            if year >= (current_year - years_back):
                recent_folders.append(folder_code)
        
        # Sort by year (descending)
        recent_folders.sort(key=lambda x: int(self.year_mappings[x]), reverse=True)
        return recent_folders
    
    def interpret_user_query(self, question: str) -> Dict[str, Any]:
        """
        Interpret user query and provide folder context.
        
        Args:
            question: User's question
            
        Returns:
            Dictionary with interpreted context including:
            - suggested_folders: List of folders to search
            - excluded_folders: List of folders to exclude
            - year_context: Detected year information
            - query_type: Type of query (project, policy, technical, etc.)
            - enhanced_search_terms: Additional search terms based on folder context
        """
        context = {
            "suggested_folders": [],
            "excluded_folders": self.excluded_folders,
            "year_context": None,
            "query_type": "general",
            "enhanced_search_terms": [],
            "folder_context": ""
        }
        
        question_lower = question.lower()
        
        # Detect year references first
        year_info = self._detect_year_references(question)
        if year_info:
            context["year_context"] = year_info
            context["suggested_folders"].extend(year_info["folder_codes"])
            context["enhanced_search_terms"].extend(year_info["search_terms"])
        
        # Detect query type and suggest relevant folders
        query_analysis = self._analyze_query_type(question_lower, year_info)
        context["query_type"] = query_analysis["type"]
        context["suggested_folders"].extend(query_analysis["folders"])
        context["enhanced_search_terms"].extend(query_analysis["search_terms"])
        context["folder_context"] = query_analysis["context"]
        
        # Remove duplicates
        context["suggested_folders"] = list(set(context["suggested_folders"]))
        context["enhanced_search_terms"] = list(set(context["enhanced_search_terms"]))
        
        logger.info("Folder structure interpretation", 
                   question=question,
                   query_type=context["query_type"],
                   suggested_folders=context["suggested_folders"],
                   year_context=context["year_context"])
        
        return context
    
    def _detect_year_references(self, question: str) -> Optional[Dict[str, Any]]:
        """Detect year references in the question."""
        year_patterns = [
            r'\b(202[0-9])\b',  # 2020-2029
            r'\b(201[5-9])\b',  # 2015-2019
            r'\b(22[0-9])\b',   # Folder codes like 225, 224
        ]
        
        detected_years = []
        folder_codes = []
        
        for pattern in year_patterns:
            matches = re.findall(pattern, question)
            for match in matches:
                if len(match) == 4 and match.startswith('20'):  # Full year
                    detected_years.append(match)
                    # Convert to folder code
                    if match in ['2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015']:
                        folder_code = match[2:]  # 2025 -> 25, but we use 225
                        if match >= '2020':
                            folder_code = '2' + match[2:]  # 2025 -> 225
                        else:
                            folder_code = '2' + match[2:]  # 2019 -> 219
                        folder_codes.append(folder_code)
                elif len(match) == 3 and match.startswith('2'):  # Folder code like 225
                    folder_codes.append(match)
                    # Convert to full year
                    if match in self.year_mappings:
                        detected_years.append(self.year_mappings[match])
        
        if detected_years or folder_codes:
            return {
                "years": list(set(detected_years)),
                "folder_codes": list(set(folder_codes)),
                "search_terms": detected_years + folder_codes
            }
        
        return None
    
    def _analyze_query_type(self, question_lower: str, year_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze the type of query and suggest relevant folders."""
        
        # Folder listing queries - highest priority
        folder_listing_indicators = [
            'list of all project folders', 'list all project folders', 'list project folders',
            'show all project folders', 'show project folders', 'all project folders',
            'list of folders', 'list all folders', 'show all folders', 'folder structure',
            'folder list', 'directory structure', 'directory list', 'what folders',
            'what project folders', 'project folder structure'
        ]
        
        # Policy-related queries
        policy_keywords = [
            'policy', 'policies', 'h&s', 'health and safety', 'safety', 'it policy',
            'employment', 'onboarding', 'hr', 'human resources', 'quality policy',
            'procedures', 'guidelines', 'compliance', 'rules', 'wellbeing', 'wellness',
            'mental health', 'employee assistance', 'eap', 'work life balance'
        ]
        
        # Technical queries
        technical_keywords = [
            'calculation', 'calculations', 'design', 'engineering', 'structural',
            'seismic', 'wind load', 'foundation', 'beam', 'column', 'slab',
            'nz standard', 'nzs', 'building code', 'standard', 'specification'
        ]
        
        # Project queries - prioritize past project requests
        past_project_indicators = [
            'past project', 'previous project', 'past job', 'previous job',
            'all project', 'all past', 'past work', 'similar project',
            'project example', 'project reference', 'project that', 'projects that'
        ]
        
        project_keywords = [
            'project', 'job', 'client', 'report', 'drawing', 'site', 'building',
            'assessment', 'analysis', 'construction', 'development'
        ]
        
        # H2H (How-to) procedure queries
        procedure_keywords = [
            'how to', 'procedure', 'process', 'workflow', 'method', 'approach',
            'steps', 'guide', 'handbook', 'h2h', 'best practice'
        ]
        
        # Template/Form queries
        template_keywords = [
            'template', 'form', 'spreadsheet', 'checklist', 'format',
            'example', 'sample', 'blank'
        ]
        
        # Check for folder listing requests first (highest priority)
        if any(indicator in question_lower for indicator in folder_listing_indicators):
            return {
                "type": "folder_listing",
                "folders": [],  # No specific search needed
                "search_terms": [],
                "context": "Providing folder structure information"
            }
        
        # Check for past project requests next (high priority)
        elif any(indicator in question_lower for indicator in past_project_indicators):
            # If specific year is mentioned, use only that year's folder
            if year_info and year_info.get("folder_codes"):
                project_folders = year_info["folder_codes"]
                context_msg = f"Searching specifically in {', '.join(year_info.get('years', []))} project documents and reports"
            else:
                # No specific year mentioned, search all projects
                project_folders = ["Projects"]
                context_msg = "Searching specifically in past project documents and reports"
                
            return {
                "type": "project",
                "folders": project_folders,
                "search_terms": ["project", "job", "client", "scope"],
                "context": context_msg
            }
        
        elif any(keyword in question_lower for keyword in policy_keywords):
            return {
                "type": "policy",
                "folders": ["Health & Safety", "IT Policy", "Employment", "Quality", "Operations"],
                "search_terms": ["policy", "procedure", "guideline"],
                "context": "Searching in company policy and procedure documents"
            }
        
        elif any(keyword in question_lower for keyword in technical_keywords):
            return {
                "type": "technical",
                "folders": ["Engineering Standards", "Design Guidelines", "05 Calculations", "07 Specifications"],
                "search_terms": ["engineering", "design", "calculation", "standard"],
                "context": "Searching in technical and engineering documents"
            }
        
        elif any(keyword in question_lower for keyword in procedure_keywords):
            return {
                "type": "procedure",
                "folders": ["H2H", "Technical Procedures", "Admin Procedures"],
                "search_terms": ["procedure", "how to", "process", "method"],
                "context": "Searching in DTCE procedures and how-to handbooks"
            }
        
        elif any(keyword in question_lower for keyword in template_keywords):
            return {
                "type": "template",
                "folders": ["Templates", "Forms", "H2H", "Engineering Standards", "Projects"],
                "search_terms": ["template", "form", "example", "spreadsheet"],
                "context": "Searching in templates, procedures, and project examples for tools and forms"
            }
        
        elif any(keyword in question_lower for keyword in project_keywords):
            # If specific year is mentioned, use only that year's folder
            if year_info and year_info.get("folder_codes"):
                project_folders = year_info["folder_codes"]
                context_msg = f"Searching in {', '.join(year_info.get('years', []))} project documents and reports"
            else:
                # No specific year mentioned, search projects folder
                project_folders = ["Projects"]
                context_msg = "Searching in project documents and reports"
                
            return {
                "type": "project",
                "folders": project_folders,
                "search_terms": ["project", "job", "client"],
                "context": context_msg
            }
        
        else:
            return {
                "type": "general",
                "folders": [],
                "search_terms": [],
                "context": "General search across all document types"
            }
    
    def should_exclude_folder(self, folder_path: str) -> bool:
        """Check if a folder should be excluded from search."""
        folder_path_lower = folder_path.lower()
        
        return any(excluded.lower() in folder_path_lower for excluded in self.excluded_folders)
    
    def get_folder_structure_listing(self) -> str:
        """Generate a comprehensive folder structure listing for display to users."""
        
        listing = "## DTCE SuiteFiles Folder Structure\n\n"
        
        # Project folders
        listing += "### Project Folders (by Year)\n"
        for folder_code, description in self.folder_mappings["projects"].items():
            listing += f"- **Projects/{folder_code}/** - {description}\n"
        
        listing += "\n### Standard Project Subfolders\n"
        listing += "Each project typically contains these subfolders:\n"
        for subfolder, description in self.folder_mappings["project_subfolders"].items():
            listing += f"- **{subfolder}/** - {description}\n"
        
        # Other folder types
        listing += "\n### Policy & Procedure Folders\n"
        for folder, description in self.folder_mappings["policies"].items():
            listing += f"- **{folder}/** - {description}\n"
        
        listing += "\n### Technical Resources\n"
        for folder, description in self.folder_mappings["technical"].items():
            listing += f"- **{folder}/** - {description}\n"
        
        listing += "\n### Procedures & Handbooks\n"
        for folder, description in self.folder_mappings["procedures"].items():
            listing += f"- **{folder}/** - {description}\n"
        
        listing += "\n### Usage Examples\n"
        listing += "- To find **past projects**: \"show me projects from 2024\" or \"projects about precast panels\"\n"
        listing += "- To find **standards**: \"NZS 3404 steel design\" or \"building code requirements\"\n"
        listing += "- To find **policies**: \"health and safety policy\" or \"IT policy\"\n"
        listing += "- To find **procedures**: \"how to use wind load spreadsheet\" or \"H2H procedures\"\n"
        
        return listing
    
    def enhance_search_query(self, original_query: str, context: Dict[str, Any]) -> str:
        """Enhance the search query with folder structure context and synonyms."""
        enhanced_terms = context.get("enhanced_search_terms", [])
        
        query_lower = original_query.lower()
        synonym_terms = []
        
        if 'wellbeing' in query_lower or 'well-being' in query_lower:
            synonym_terms.extend(['wellness', 'mental health', 'employee assistance'])
        elif 'wellness' in query_lower:
            synonym_terms.extend(['wellbeing', 'well-being', 'mental health'])
        
        if 'health' in query_lower and 'safety' in query_lower:
            synonym_terms.extend(['h&s', 'workplace safety', 'occupational health'])
        
        if 'policy' in query_lower:
            synonym_terms.extend(['procedure', 'guideline', 'rules'])
        
        all_enhanced_terms = enhanced_terms + synonym_terms
        
        if all_enhanced_terms:
            enhanced_query = original_query + " " + " ".join(set(all_enhanced_terms))
            return enhanced_query
        
        return original_query
    
    def get_folder_filter_query(self, context: Dict[str, Any]) -> Optional[str]:
        """Generate a minimal Azure Search filter - let GPT do the intelligent filtering."""
        # Only exclude the most critical superseded/archive folders 
        # Let GPT handle intelligent folder-based filtering based on context
        return "not search.ismatch('superseded', 'folder')"
    
    def format_folder_context_for_ai(self, context: Dict[str, Any]) -> str:
        """Format folder context information for AI prompts."""
        context_parts = []
        
        if context.get("query_type") != "general":
            context_parts.append(f"Query Type: {context['query_type'].title()}")
        
        if context.get("year_context"):
            years = context["year_context"]["years"]
            context_parts.append(f"Year Context: Looking for documents from {', '.join(years)}")
        
        if context.get("folder_context"):
            context_parts.append(f"Search Context: {context['folder_context']}")
        
        if context.get("suggested_folders"):
            folders = ", ".join(context["suggested_folders"])
            context_parts.append(f"Relevant Folders: {folders}")
        
        return "\n".join(context_parts) if context_parts else ""
