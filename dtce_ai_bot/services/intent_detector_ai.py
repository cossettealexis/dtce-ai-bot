"""
Intent Detection Service
Uses GPT to intelligently classify user queries into categories.
Follows the architecture: Intent Detection → Dynamic Filter Building → Hybrid Search → RAG Generation
"""
import structlog
from typing import Dict, Optional, Tuple
from openai import AsyncAzureOpenAI
import json
import re

logger = structlog.get_logger(__name__)


class IntentDetector:
    """
    Step 1 of RAG Orchestration: Intent Classification
    Uses a lightweight LLM call to classify user queries into knowledge categories.
    """
    
    # Knowledge Categories aligned with index metadata
    CATEGORIES = {
        "Policy": {
            "description": "Company policies, rules, H&S procedures, employee requirements",
            "folder_field": "folder",
            "folder_values": ["Policies", "Health and Safety", "H&S", "Company Documents", "Wellbeing"]
        },
        "Procedure": {
            "description": "How-to guides, technical procedures, best practices",
            "folder_field": "folder", 
            "folder_values": ["Procedures", "How to Handbooks", "H2H", "Technical"]
        },
        "Standards": {
            "description": "NZ Engineering Standards (NZS, AS/NZS codes)",
            "folder_field": "folder",
            "folder_values": ["Standards", "NZ Standards", "NZS", "Technical Library", "Codes"]
        },
        "Project": {
            "description": "Past project information, job folders (requires extracting job number or year)",
            "folder_field": "folder",
            "folder_values": ["Projects"],  # Will be filtered by year/job number dynamically
            "requires_extraction": True  # Need to extract job number or year code
        },
        "Client": {
            "description": "Client information, contact details, client history",
            "folder_field": "folder",
            "folder_values": ["Clients"]
        },
        "General_Knowledge": {
            "description": "General engineering knowledge, company info (no internal filter needed)",
            "folder_field": None,
            "folder_values": []
        }
    }
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str, max_retries: int = 3):
        """Initialize intent detector with OpenAI client."""
        self.openai_client = openai_client
        self.openai_client.max_retries = max_retries
        self.model_name = model_name
    
    async def classify_intent(self, user_query: str) -> str:
        """
        Step 2.1: Intent Classification
        Uses GPT-4o-mini (fast, cheap) to classify query into ONE category.
        
        Returns: Category name (e.g., "Policy", "Project", "General_Knowledge")
        """
        try:
            classification_prompt = f"""Goal: Classify the user's query into one of the following categories to enable targeted search. Output ONLY the category name and nothing else.

If the query is a general engineering term (e.g., "what is the maximum wind load on a commercial building?"), use General_Knowledge.

Categories:
- Policy: Company policies, H&S procedures, HR/IT rules, employee requirements
- Procedure: How-to guides, technical procedures, best practices, operational handbooks
- Standards: NZ Engineering Standards (NZS, AS/NZS codes), technical specifications
- Project: Past project information, job folders, work history (e.g., "project 225", "job 219208")
- Client: Client information, contact details, client relationships
- General_Knowledge: General engineering questions, company overview, unclear intent

User Query: "{user_query}"

CRITICAL: When someone asks "project 225" or "job 219208", they want PROJECT information, not technical measurements like "225mm beam depth"!

Output ONLY the category name (e.g., "Project" or "Policy" or "General_Knowledge")."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You classify queries into knowledge categories. Output ONLY the category name, nothing else."},
                    {"role": "user", "content": classification_prompt}
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            intent = response.choices[0].message.content.strip()
            
            # Validate the intent exists
            if intent not in self.CATEGORIES:
                logger.warning("Invalid intent returned, defaulting to General_Knowledge", 
                             returned_intent=intent, query=user_query)
                intent = "General_Knowledge"
            
            logger.info("Intent classified", query=user_query, intent=intent)
            return intent
                
        except Exception as e:
            logger.error("Intent classification failed", error=str(e), query=user_query)
            return "General_Knowledge"  # Safe fallback
    
    def extract_project_metadata(self, user_query: str) -> Optional[Dict[str, str]]:
        """
        Step 2.2: Extract Project Metadata (if intent is Project)
        
        Extracts:
        - 6-digit job number (e.g., "225221")
        - 3-digit year code (e.g., "225" = 2025)
        
        Returns: {"job_number": "225221", "year": "225"} or None
        """
        query_lower = user_query.lower()
        
        # Pattern 1: 6-digit job number (e.g., "225221", "219208")
        job_match = re.search(r'\b(2\d{5})\b', user_query)
        if job_match:
            job_number = job_match.group(1)
            year_code = job_number[:3]  # First 3 digits = year
            logger.info("Extracted job number", job_number=job_number, year_code=year_code)
            return {"job_number": job_number, "year": year_code}
        
        # Pattern 2: 3-digit year code (e.g., "project 225", "jobs from 219")
        year_match = re.search(r'\b(2[0-9]{2})\b', user_query)
        if year_match and any(keyword in query_lower for keyword in ['project', 'job', 'what is', 'tell me about']):
            year_code = year_match.group(1)
            logger.info("Extracted year code", year_code=year_code)
            return {"year": year_code}
        
        return None
    
    def extract_client_name(self, user_query: str) -> Optional[str]:
        """
        Step 2.2: Extract Client Name (if intent is Client)
        
        Uses simple heuristics to extract potential client names.
        Could be enhanced with NER (Named Entity Recognition) if needed.
        """
        # Simple extraction: look for capitalized words after "client"
        client_match = re.search(r'client\s+([A-Z][a-zA-Z\s]+?)(?:\s+|$|\?|\.)', user_query)
        if client_match:
            client_name = client_match.group(1).strip()
            logger.info("Extracted client name", client_name=client_name)
            return client_name
        
        return None
    
    def build_search_filter(self, intent: str, user_query: str) -> Optional[str]:
        """
        Step 2.3: Dynamic Filter Construction
        Builds a robust OData filter based on the CORRECT folder structure:
        Projects/{YEAR_CODE}/{JOB_NUMBER}. Uses range queries for folder scoping.

        Returns: OData filter string or None (for General_Knowledge)
        """
        category = self.CATEGORIES.get(intent)
        if not category or not category.get("folder_field"):
            logger.info("No folder-based filter needed for intent", intent=intent)
            return None

        def get_upper_bound(path: str) -> str:
            """Calculates the upper bound for a 'startswith' range query."""
            if not path: return ""
            parts = path.split('/')
            last_part = parts[-1]
            if last_part.isdigit():
                try:
                    incremented = str(int(last_part) + 1)
                    return '/'.join(parts[:-1] + [incremented])
                except (ValueError, IndexError): pass
            return path[:-1] + chr(ord(path[-1]) + 1)

        # --- Project Intent Logic ---
        if intent == "Project":
            project_meta = self.extract_project_metadata(user_query)
            if project_meta:
                project_code = project_meta.get("year") # This is the PROJECT_CODE, e.g., '225'
                job_num = project_meta.get("job_number")

                # Case 1: Specific 6-digit job number found (e.g., 225221)
                if job_num and project_code:
                    # Correct Path: Projects/{PROJECT_CODE}/{JOB_NUMBER}
                    base_path = f"Projects/{project_code}/{job_num}"
                    upper_bound = get_upper_bound(base_path)
                    # e.g., folder ge 'Projects/225/225221/' and folder lt 'Projects/225/225222'
                    filter_str = f"folder ge '{base_path}/' and folder lt '{upper_bound}'"
                    logger.info("Built specific project job filter", filter=filter_str)
                    return filter_str

                # Case 2: Only a 3-digit project code found (e.g., 225)
                elif project_code:
                    base_path = f"Projects/{project_code}"
                    upper_bound = get_upper_bound(base_path)
                    # e.g., folder ge 'Projects/225/' and folder lt 'Projects/226'
                    filter_str = f"folder ge '{base_path}/' and folder lt '{upper_bound}'"
                    logger.info("Built broad project year filter", filter=filter_str)
                    return filter_str
                elif project_code:
                    # If it's a broad project query (e.g., "project 225"), filter by folder path
                    year_code = project_code
                    next_year_code = str(int(year_code) + 1)
                    logger.info("Built project year folder filter", year_code=year_code)
                    return f"folder ge 'Projects/{year_code}/' and folder lt 'Projects/{next_year_code}/'"

            # Fallback for when metadata extraction fails but intent is 'Project'
            logger.warning("Project intent detected but no specific metadata extracted, creating final fallback.", query=user_query)
            project_code_match = re.search(r'\b(2[0-9]{2})\b', user_query)
            if project_code_match:
                project_code = project_code_match.group(1)
                filter_str = f"project_name eq '{project_code}'"
                logger.info("Built final fallback project_name filter", filter=filter_str)
                return filter_str

            return None # No filter if no metadata can be extracted

        # --- Client Intent Logic ---
        if intent == "Client":
            client_name = self.extract_client_name(user_query)
            base_filter = "folder ge 'Clients/' and folder lt 'Clients~'"
            if client_name:
                filter_str = f"({base_filter}) and search.ismatch('{client_name}', 'content, project_name', 'full', 'any')"
                logger.info("Built client-specific filter", filter=filter_str)
                return filter_str
            
            logger.info("Built generic client filter, scoping to Clients folder.")
            return base_filter

        # --- Standard Category Logic (Policy, Procedure, Standards) ---
        folder_values = category.get("folder_values")
        if folder_values:
            or_clauses = [f"(folder ge '{val}/' and folder lt '{val}~')" for val in folder_values]
            filter_str = " or ".join(or_clauses)
            logger.info("Built standard folder filter (range)", intent=intent, filter=filter_str)
            return filter_str

        logger.warning("Could not build filter for intent", intent=intent)
        return None
