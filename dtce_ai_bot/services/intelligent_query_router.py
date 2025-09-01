"""
Intelligent Query Router for DTCE AI Bot
Routes queries to specific folders based on intent classification.
"""

import re
from typing import Dict, List, Optional, Tuple
from enum import Enum
import structlog
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class SearchCategory(Enum):
    """Search categories matching DTCE folder structure."""
    POLICY = "policy"
    PROCEDURES = "procedures"
    STANDARDS = "standards"
    PROJECTS = "projects"
    CLIENTS = "clients"


class IntelligentQueryRouter:
    """
    Routes user queries to appropriate folder categories using AI classification.
    """
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
        
        # Define folder mappings for each category
        self.folder_mappings = {
            SearchCategory.POLICY: [
                "policies", "policy", "h&s", "health", "safety", "hr", "it policy",
                "employee handbook", "code of conduct", "disciplinary", "wellness"
            ],
            SearchCategory.PROCEDURES: [
                "procedures", "h2h", "how to", "handbook", "technical procedures",
                "admin procedures", "engineering procedures", "best practice", 
                "workflow", "process", "guideline", "methodology"
            ],
            SearchCategory.STANDARDS: [
                "standards", "nz standards", "engineering standards", "codes",
                "nzs", "specifications", "design criteria", "compliance standards",
                "building codes", "structural standards"
            ],
            SearchCategory.PROJECTS: [
                "projects", "project", "site", "construction", "development",
                "building", "residential", "commercial", "infrastructure",
                "past projects", "case study", "project history"
            ],
            SearchCategory.CLIENTS: [
                "clients", "client", "customer", "nzta", "council", "developer",
                "contact", "client details", "client information", "customer info"
            ]
        }
        
        # Keyword patterns for quick classification
        self.keyword_patterns = {
            SearchCategory.POLICY: [
                r'\bpolic(y|ies)\b', r'\bh&s\b', r'\bhealth.{0,10}safety\b',
                r'\bwellness\b', r'\bhr\b', r'\bemployee.{0,10}handbook\b',
                r'\bdisciplinary\b', r'\bcode.{0,10}conduct\b'
            ],
            SearchCategory.PROCEDURES: [
                r'\bprocedure\b', r'\bh2h\b', r'\bhow.{0,10}to\b',
                r'\bhandbook\b', r'\bworkflow\b', r'\bprocess\b',
                r'\bguideline\b', r'\bmethodology\b', r'\bbest.{0,10}practice\b'
            ],
            SearchCategory.STANDARDS: [
                r'\bstandards?\b', r'\bnzs\b', r'\bcodes?\b',
                r'\bspecifications?\b', r'\bdesign.{0,10}criteria\b',
                r'\bcompliance\b', r'\bbuilding.{0,10}code\b'
            ],
            SearchCategory.PROJECTS: [
                r'\bprojects?\b', r'\bsite\b', r'\bconstruction\b',
                r'\bdevelopment\b', r'\bbuilding\b', r'\bresidential\b',
                r'\bcommercial\b', r'\binfrastructure\b'
            ],
            SearchCategory.CLIENTS: [
                r'\bclients?\b', r'\bcustomer\b', r'\bnzta\b',
                r'\bcouncil\b', r'\bdeveloper\b', r'\bcontact\b'
            ]
        }
    
    async def classify_query(self, query: str) -> Tuple[SearchCategory, float]:
        """
        Classify user query into appropriate search category.
        
        Args:
            query: User's natural language query
            
        Returns:
            Tuple of (category, confidence_score)
        """
        try:
            # First try keyword-based classification for speed
            keyword_result = self._classify_by_keywords(query)
            if keyword_result[1] > 0.8:  # High confidence from keywords
                logger.info("Query classified by keywords", 
                           query=query[:100], 
                           category=keyword_result[0].value,
                           confidence=keyword_result[1])
                return keyword_result
            
            # Fall back to AI classification for complex queries
            ai_result = await self._classify_by_ai(query)
            
            # Combine keyword and AI results
            final_category, final_confidence = self._combine_classifications(
                keyword_result, ai_result, query
            )
            
            logger.info("Query classified", 
                       query=query[:100],
                       category=final_category.value,
                       confidence=final_confidence,
                       method="combined")
            
            return final_category, final_confidence
            
        except Exception as e:
            logger.error("Query classification failed", error=str(e), query=query[:100])
            # Default to projects as it's the most general category
            return SearchCategory.PROJECTS, 0.5
    
    def _classify_by_keywords(self, query: str) -> Tuple[SearchCategory, float]:
        """Quick keyword-based classification."""
        query_lower = query.lower()
        
        category_scores = {}
        
        for category, patterns in self.keyword_patterns.items():
            score = 0
            matches = 0
            
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    matches += 1
                    score += 1.0
            
            # Boost score based on folder mapping keywords
            for keyword in self.folder_mappings[category]:
                if keyword.lower() in query_lower:
                    score += 0.5
                    matches += 1
            
            if matches > 0:
                category_scores[category] = score / len(patterns)
        
        if not category_scores:
            return SearchCategory.PROJECTS, 0.0
        
        best_category = max(category_scores.keys(), key=lambda k: category_scores[k])
        confidence = min(category_scores[best_category], 1.0)
        
        return best_category, confidence
    
    async def _classify_by_ai(self, query: str) -> Tuple[SearchCategory, float]:
        """AI-based classification for complex queries."""
        
        classification_prompt = f"""
You are a document classification system for DTCE Engineering Consultancy.

Classify this user query into ONE of these categories:

1. POLICY - Company policies, H&S policies, HR policies, employee handbooks, disciplinary procedures, wellness policies
   Examples: "what's our wellness policy", "health and safety procedures", "hr policy"

2. PROCEDURES - Technical procedures, admin procedures, H2H (How To Handbooks), best practices, workflows
   Examples: "how do I use the wind speed spreadsheet", "technical procedures", "workflow guidelines"

3. STANDARDS - NZ Engineering Standards, building codes, design criteria, compliance standards, specifications
   Examples: "nz engineering standards", "building codes", "design specifications"

4. PROJECTS - Past projects, construction projects, development projects, site information, project history
   Examples: "find projects in wellington", "construction project details", "past residential projects"

5. CLIENTS - Client information, customer details, NZTA projects, council projects, contact information
   Examples: "NZTA client details", "council projects", "client contact information"

User Query: "{query}"

Respond with ONLY the category name (POLICY, PROCEDURES, STANDARDS, PROJECTS, or CLIENTS) and a confidence score (0.0-1.0).
Format: CATEGORY|CONFIDENCE
Example: PROCEDURES|0.95
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a precise document classification system."},
                    {"role": "user", "content": classification_prompt}
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse the response
            if '|' in result:
                category_str, confidence_str = result.split('|', 1)
                category_str = category_str.strip()
                confidence = float(confidence_str.strip())
                
                # Map string to enum
                category_mapping = {
                    'POLICY': SearchCategory.POLICY,
                    'PROCEDURES': SearchCategory.PROCEDURES,
                    'STANDARDS': SearchCategory.STANDARDS,
                    'PROJECTS': SearchCategory.PROJECTS,
                    'CLIENTS': SearchCategory.CLIENTS
                }
                
                if category_str in category_mapping:
                    return category_mapping[category_str], confidence
            
            # Fallback parsing
            for category_name, category_enum in [
                ('POLICY', SearchCategory.POLICY),
                ('PROCEDURES', SearchCategory.PROCEDURES),
                ('STANDARDS', SearchCategory.STANDARDS),
                ('PROJECTS', SearchCategory.PROJECTS),
                ('CLIENTS', SearchCategory.CLIENTS)
            ]:
                if category_name in result.upper():
                    return category_enum, 0.7
            
            return SearchCategory.PROJECTS, 0.5
            
        except Exception as e:
            logger.error("AI classification failed", error=str(e))
            return SearchCategory.PROJECTS, 0.5
    
    def _combine_classifications(
        self, 
        keyword_result: Tuple[SearchCategory, float],
        ai_result: Tuple[SearchCategory, float],
        query: str
    ) -> Tuple[SearchCategory, float]:
        """Combine keyword and AI classification results."""
        
        keyword_category, keyword_confidence = keyword_result
        ai_category, ai_confidence = ai_result
        
        # If both agree and have decent confidence, boost the result
        if keyword_category == ai_category and keyword_confidence > 0.3 and ai_confidence > 0.3:
            combined_confidence = min((keyword_confidence + ai_confidence) / 2 + 0.2, 1.0)
            return keyword_category, combined_confidence
        
        # If AI has much higher confidence, trust it
        if ai_confidence > keyword_confidence + 0.3:
            return ai_category, ai_confidence
        
        # If keyword has much higher confidence, trust it
        if keyword_confidence > ai_confidence + 0.3:
            return keyword_category, keyword_confidence
        
        # Otherwise, prefer the higher confidence result
        if ai_confidence >= keyword_confidence:
            return ai_category, ai_confidence
        else:
            return keyword_category, keyword_confidence
    
    def get_folder_filters(self, category: SearchCategory) -> List[str]:
        """
        Get folder-based search filters for a category.
        
        Args:
            category: The search category
            
        Returns:
            List of folder filter expressions for Azure Search
        """
        
        folder_filters = {
            SearchCategory.POLICY: [
                "search.ismatch('*policy*', 'folder')",
                "search.ismatch('*h&s*', 'folder')", 
                "search.ismatch('*health*safety*', 'folder')",
                "search.ismatch('*hr*', 'folder')",
                "search.ismatch('*employee*', 'folder')"
            ],
            SearchCategory.PROCEDURES: [
                "search.ismatch('*procedure*', 'folder')",
                "search.ismatch('*h2h*', 'folder')",
                "search.ismatch('*handbook*', 'folder')",
                "search.ismatch('*workflow*', 'folder')",
                "search.ismatch('*technical*', 'folder')"
            ],
            SearchCategory.STANDARDS: [
                "search.ismatch('*standard*', 'folder')",
                "search.ismatch('*nz*standard*', 'folder')",
                "search.ismatch('*engineering*standard*', 'folder')",
                "search.ismatch('*code*', 'folder')",
                "search.ismatch('*specification*', 'folder')"
            ],
            SearchCategory.PROJECTS: [
                "search.ismatch('*project*', 'folder')",
                "search.ismatch('*site*', 'folder')",
                "search.ismatch('*construction*', 'folder')",
                "search.ismatch('*development*', 'folder')",
                "search.ismatch('*building*', 'folder')"
            ],
            SearchCategory.CLIENTS: [
                "search.ismatch('*client*', 'folder')",
                "search.ismatch('*nzta*', 'folder')",
                "search.ismatch('*council*', 'folder')",
                "search.ismatch('*customer*', 'folder')"
            ]
        }
        
        return folder_filters.get(category, [])
    
    def get_search_instructions(self, category: SearchCategory) -> str:
        """
        Get specialized search instructions for each category.
        
        Args:
            category: The search category
            
        Returns:
            Instructions for the AI to handle this category effectively
        """
        
        instructions = {
            SearchCategory.POLICY: """
You are searching POLICY documents. These are company policies that employees must follow.
Focus on:
- Health & Safety policies and procedures
- HR policies and employee handbooks  
- IT policies and security guidelines
- Disciplinary procedures and codes of conduct
- Wellness and workplace policies

Provide authoritative answers about what employees must do or follow.
""",
            
            SearchCategory.PROCEDURES: """
You are searching PROCEDURE documents (H2H - How To Handbooks). These are best practices and workflows.
Focus on:
- Technical procedures and engineering workflows
- Administrative procedures and processes
- Step-by-step guides and methodologies
- Software usage instructions
- Best practice guidelines

Provide practical, step-by-step guidance on how to accomplish tasks.
""",
            
            SearchCategory.STANDARDS: """
You are searching NZ ENGINEERING STANDARDS documents. These are official standards and codes.
Focus on:
- NZ Standards (NZS) documents
- Building codes and design criteria
- Engineering specifications and requirements
- Compliance standards and regulations
- Technical specifications

Provide precise references to standards, codes, and technical requirements.
""",
            
            SearchCategory.PROJECTS: """
You are searching PROJECT documents. These contain information about past and current projects.
Focus on:
- Project details and specifications
- Construction and development projects
- Site information and project history
- Project methodologies and approaches
- Case studies and project outcomes

Note: Project data may be less structured. Cross-reference with project spreadsheets when available.
""",
            
            SearchCategory.CLIENTS: """
You are searching CLIENT information. These contain client-related documents and communications.
Focus on:
- Client contact information and details
- Client project history and relationships
- NZTA and council project information
- Client communications and correspondence
- Client-specific requirements and preferences

Note: Combine with project information for comprehensive client insights.
"""
        }
        
        return instructions.get(category, "Search all available documents for relevant information.")
