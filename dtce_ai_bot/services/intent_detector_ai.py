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
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        """Initialize intent detector with OpenAI client."""
        self.openai_client = openai_client
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
        Builds OData filter based on intent and extracted metadata.
        
        Returns: OData filter string or None (for General_Knowledge)
        """
        category = self.CATEGORIES.get(intent)
        if not category or category["folder_field"] is None:
            return None  # No filter for General_Knowledge
        
        # Special handling for Project intent
        if intent == "Project":
            project_meta = self.extract_project_metadata(user_query)
            if project_meta:
                if "job_number" in project_meta:
                    # Specific job number
                    job_num = project_meta["job_number"]
                    filter_str = f"search.ismatch('{job_num}', 'folder,project_name', 'full', 'any')"
                    logger.info("Built project filter", filter=filter_str, job_number=job_num)
                    return filter_str
                elif "year" in project_meta:
                    # Year code - search all projects from that year
                    year = project_meta["year"]
                    filter_str = f"search.ismatch('{year}*', 'folder,project_name', 'full', 'any')"
                    logger.info("Built year filter", filter=filter_str, year=year)
                    return filter_str
            
            # Fallback: search all project folders
            filter_str = "search.ismatch('Projects', 'folder', 'full', 'any')"
            logger.info("Built generic project filter", filter=filter_str)
            return filter_str
        
        # Special handling for Client intent
        if intent == "Client":
            client_name = self.extract_client_name(user_query)
            if client_name:
                filter_str = f"search.ismatch('Clients', 'folder', 'full', 'any') and search.ismatch('{client_name}', 'content,project_name', 'full', 'any')"
                logger.info("Built client filter", filter=filter_str, client_name=client_name)
                return filter_str
            
            # Fallback: search all client folders
            filter_str = "search.ismatch('Clients', 'folder', 'full', 'any')"
            return filter_str
        
        # Standard folder filtering for Policy, Procedure, Standards
        folder_values = category["folder_values"]
        if folder_values:
            # Build search.ismatch with OR logic
            folders_pattern = "|".join(folder_values)
            filter_str = f"search.ismatch('{folders_pattern}', 'folder', 'full', 'any')"
            logger.info("Built folder filter", intent=intent, filter=filter_str)
            return filter_str
        
        return None
