"""
Intent Classification Service

Single Responsibility: Classify user queries into appropriate categories
"""

from typing import Dict, Any
import json
import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger(__name__)


class IntentClassifier:
    """
    Responsible for classifying user queries into predefined categories.
    
    Enhanced Categories for Engineering Firm Operations:
    - project_search: Direct search for a specific project by number/name
    - keyword_project_search: Search for projects using scope/work keywords
    - template_search: Looking for document templates or similar documents
    - file_analysis: User uploading/analyzing documents
    - email_search: Search for email correspondence
    - client_info: Request for client contact information
    - client_project_history: All projects for a specific client
    - scope_based_search: Projects matching specific engineering scope
    - policy: H&S policies, HR policies, mandatory company rules
    - technical_procedures: H2H handbooks, how-to guides, best practices
    - nz_standards: NZS codes, engineering standards, specifications
    - general: Other engineering questions
    """
    
    def __init__(self, openai_client: AsyncOpenAI, model_name: str = "gpt-4"):
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def classify_intent(self, question: str) -> Dict[str, Any]:
        """
        Classify the user's question into an appropriate category.
        
        Args:
            question: The user's question
            
        Returns:
            Dict containing category, confidence, reasoning, and search keywords
        """
        try:
            intent_prompt = self._build_classification_prompt(question)
            
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert at classifying engineering questions. Always respond with valid JSON."
                    },
                    {"role": "user", "content": intent_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            classification = json.loads(response.choices[0].message.content)
            logger.info("Intent classified", 
                       category=classification.get('category'),
                       confidence=classification.get('confidence'))
            return classification
            
        except Exception as e:
            logger.error("Intent classification failed", error=str(e))
            return self._get_fallback_classification(question)
    
    def _build_classification_prompt(self, question: str) -> str:
        """Build the classification prompt."""
        return f"""Classify this engineering question into one of these categories:

QUESTION: "{question}"

CATEGORIES:
1. **project_search** - Direct search for a specific project by number/name
   Examples: "Show me project 225001", "Find project ABC-2024", "What is project 224050?"
   
2. **keyword_project_search** - Search for projects using scope/work keywords
   Examples: "Find all projects with steel portal frames", "Projects involving retaining walls"
   
3. **template_search** - Looking for document templates or similar documents
   Examples: "Do we have a template for PS1 report?", "Find template for geotech report"
   
4. **file_analysis** - User uploading/analyzing documents (indicated by context)
   Examples: "Analyze this document", "What does this file contain?", "Summarize this report"
   
5. **email_search** - Search for email correspondence
   Examples: "Find emails with client for project 225001", "Show email history with contractor"
   
6. **client_info** - Request for client contact information or relationship queries
   Examples: "Who is the contact for project 225001?", "Client details for ABC Construction", "Does anyone work with Aaron from TGCS?", "Who works with XYZ Company?", "Contact person for Smith & Associates"
   
7. **client_project_history** - All projects for a specific client
   Examples: "Show me all projects for ABC Construction", "What work have we done for NZTA?"
   
8. **scope_based_search** - Projects matching specific engineering scope
   Examples: "Find projects with seismic strengthening", "Show all bridge inspection work"
   
9. **policy** - Questions about company policies (H&S, HR, wellness, mandatory rules)
   Examples: "What is our wellness policy?", "What are the H&S requirements?"
   
10. **technical_procedures** - Questions about how-to guides, procedures, best practices  
    Examples: "How do I use the wind speed spreadsheet?", "What's the process for..."
   
11. **nz_standards** - Questions about NZ engineering standards, codes, specifications
    Examples: "What are the minimum cover requirements per NZS?", "NZS 3101 requirements"
   
12. **general** - Other engineering questions not fitting above categories

Respond with JSON:
{{
    "category": "project_search|keyword_project_search|template_search|file_analysis|email_search|client_info|client_project_history|scope_based_search|policy|technical_procedures|nz_standards|general",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this category was chosen",
    "search_keywords": ["relevant", "search", "terms"]
}}"""
    
    def _get_fallback_classification(self, question: str) -> Dict[str, Any]:
        """Provide fallback classification when AI classification fails."""
        return {
            "category": "general",
            "confidence": 0.5,
            "reasoning": "Classification failed, defaulting to general",
            "search_keywords": question.split()[:3]
        }
