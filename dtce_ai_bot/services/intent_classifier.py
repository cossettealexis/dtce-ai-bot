"""
Intent Classifier Service - Determines the intent and category of user queries
Implements intelligent query routing for different document types
"""

from typing import Dict, Any, List
import structlog
from openai import AsyncAzureOpenAI
from enum import Enum

logger = structlog.get_logger(__name__)


class QueryCategory(Enum):
    """Categories for different types of queries."""
    POLICY = "policy"
    PROCEDURES = "procedures"
    NZ_STANDARDS = "nz_standards"
    PROJECT_REFERENCE = "project_reference"
    CLIENT_REFERENCE = "client_reference"
    GENERAL_ENGINEERING = "general_engineering"


class IntentClassifier:
    """
    Classifies user queries into categories and determines search strategy.
    This implements the intelligent routing described in the RAG requirements.
    """
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def classify_query(self, query: str) -> Dict[str, Any]:
        """
        Classify user query and determine search strategy.
        
        Returns:
            Dictionary with classification results and search strategy
        """
        try:
            logger.info("Classifying query intent", query=query)
            
            # Use LLM to classify the query
            classification = await self._llm_classify_query(query)
            
            # Enhance with rule-based patterns
            enhanced_classification = self._enhance_with_rules(query, classification)
            
            # Determine search strategy
            search_strategy = self._determine_search_strategy(enhanced_classification)
            
            result = {
                **enhanced_classification,
                'search_strategy': search_strategy
            }
            
            logger.info("Query classification completed", 
                       category=result.get('category'),
                       confidence=result.get('confidence'))
            
            return result
            
        except Exception as e:
            logger.error("Query classification failed", error=str(e))
            return self._fallback_classification(query)
    
    async def _llm_classify_query(self, query: str) -> Dict[str, Any]:
        """
        Use LLM to classify the query into categories.
        """
        try:
            classification_prompt = f"""Analyze this user query and classify it into one of these categories:

1. **POLICY** - Questions about company policies, health & safety, IT policies
2. **PROCEDURES** - Questions about processes, procedures, how-to guides, handbooks
3. **NZ_STANDARDS** - Questions about New Zealand engineering standards, codes, regulations
4. **PROJECT_REFERENCE** - Questions about specific projects, project details, project history
5. **CLIENT_REFERENCE** - Questions about clients, contacts, client information
6. **GENERAL_ENGINEERING** - General engineering questions that don't need DTCE-specific documents

User Query: "{query}"

Analyze the query and respond with:
- Category: [one of the above categories]
- Confidence: [0.0 to 1.0]
- Reasoning: [brief explanation]
- Keywords: [key terms that indicate this category]

Format your response as JSON:
{{
    "category": "category_name",
    "confidence": 0.85,
    "reasoning": "explanation here",
    "keywords": ["keyword1", "keyword2"]
}}"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at classifying engineering queries. Analyze the user's question and classify it accurately."
                    },
                    {"role": "user", "content": classification_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            # Parse the JSON response
            import json
            result_text = response.choices[0].message.content.strip()
            
            # Try to extract JSON from the response
            try:
                if result_text.startswith('```json'):
                    result_text = result_text.replace('```json', '').replace('```', '').strip()
                
                classification = json.loads(result_text)
                
                # Normalize category name
                category = classification.get('category', 'general_engineering').lower()
                if category in [cat.value for cat in QueryCategory]:
                    classification['category'] = category
                else:
                    classification['category'] = 'general_engineering'
                
                return classification
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM classification JSON", response=result_text)
                return self._parse_classification_text(result_text)
            
        except Exception as e:
            logger.error("LLM classification failed", error=str(e))
            return {
                'category': 'general_engineering',
                'confidence': 0.5,
                'reasoning': 'LLM classification failed',
                'keywords': []
            }
    
    def _parse_classification_text(self, text: str) -> Dict[str, Any]:
        """
        Parse classification from free text if JSON parsing fails.
        """
        text_lower = text.lower()
        
        # Simple pattern matching
        if any(word in text_lower for word in ['policy', 'policies', 'health', 'safety']):
            category = 'policy'
        elif any(word in text_lower for word in ['procedure', 'process', 'handbook', 'guide']):
            category = 'procedures'
        elif any(word in text_lower for word in ['standard', 'nzs', 'code', 'regulation']):
            category = 'nz_standards'
        elif any(word in text_lower for word in ['project', 'proj', 'site', 'job']):
            category = 'project_reference'
        elif any(word in text_lower for word in ['client', 'contact', 'customer', 'who']):
            category = 'client_reference'
        else:
            category = 'general_engineering'
        
        return {
            'category': category,
            'confidence': 0.7,
            'reasoning': 'Parsed from text patterns',
            'keywords': []
        }
    
    def _enhance_with_rules(self, query: str, classification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance LLM classification with rule-based patterns.
        """
        query_lower = query.lower()
        
        # Project number detection
        import re
        project_patterns = [
            r'project\s+(\d{3,6})',
            r'proj\s+(\d{3,6})',
            r'(?:^|\s)(\d{6})(?:\s|$)',  # 6-digit project numbers
            r'(?:^|\s)22[0-9](\d{3})(?:\s|$)'  # 22XXXX format
        ]
        
        for pattern in project_patterns:
            match = re.search(pattern, query_lower)
            if match:
                classification['has_project_number'] = True
                classification['project_number'] = match.group(1) if len(match.groups()) > 0 else match.group(0)
                if classification['category'] != 'project_reference':
                    classification['category'] = 'project_reference'
                    classification['confidence'] = min(classification['confidence'] + 0.2, 1.0)
                break
        
        # Client/contact detection
        contact_indicators = [
            'who is', 'contact for', 'who works', 'client contact',
            'project manager', 'engineer for', 'responsible for'
        ]
        
        if any(indicator in query_lower for indicator in contact_indicators):
            if classification['category'] not in ['project_reference', 'client_reference']:
                classification['category'] = 'client_reference'
                classification['confidence'] = min(classification['confidence'] + 0.1, 1.0)
        
        # Standards detection
        nz_standards_indicators = [
            'nzs', 'nz standard', 'building code', 'as/nzs', 'nzbc',
            'seismic', 'wind load', 'concrete standard', 'steel standard'
        ]
        
        if any(indicator in query_lower for indicator in nz_standards_indicators):
            if classification['category'] != 'nz_standards':
                classification['category'] = 'nz_standards'
                classification['confidence'] = min(classification['confidence'] + 0.15, 1.0)
        
        return classification
    
    def _determine_search_strategy(self, classification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine the search strategy based on classification.
        """
        category = classification['category']
        confidence = classification.get('confidence', 0.5)
        
        strategy = {
            'needs_dtce_search': True,
            'search_folders': [],
            'doc_types': [],
            'use_semantic': True,
            'use_hybrid': True
        }
        
        # Category-specific search strategies
        if category == 'policy':
            strategy['search_folders'] = ['Health and Safety', 'IT', 'Policies', 'Administration']
            strategy['doc_types'] = ['pdf', 'docx']
            
        elif category == 'procedures':
            strategy['search_folders'] = ['H2H - Head to Head', 'Procedures', 'Engineering', 'Administration']
            strategy['doc_types'] = ['pdf', 'docx']
            
        elif category == 'nz_standards':
            strategy['search_folders'] = ['Standards', 'Engineering', 'Reference']
            strategy['doc_types'] = ['pdf']
            
        elif category == 'project_reference':
            strategy['search_folders'] = ['Projects']
            strategy['doc_types'] = ['pdf', 'docx', 'xlsx']
            if classification.get('has_project_number'):
                strategy['project_filter'] = classification.get('project_number')
                
        elif category == 'client_reference':
            strategy['search_folders'] = ['Projects', 'Clients', 'Administration']
            strategy['doc_types'] = ['pdf', 'docx', 'xlsx']
            
        elif category == 'general_engineering':
            strategy['needs_dtce_search'] = False
            strategy['use_general_knowledge'] = True
        
        # Adjust strategy based on confidence
        if confidence < 0.6:
            # Low confidence - use broader search
            strategy['search_folders'] = []  # Search all folders
            strategy['use_hybrid'] = True
        
        return strategy
    
    def _fallback_classification(self, query: str) -> Dict[str, Any]:
        """
        Fallback classification when all else fails.
        """
        return {
            'category': 'general_engineering',
            'confidence': 0.3,
            'reasoning': 'Fallback classification due to errors',
            'keywords': [],
            'search_strategy': {
                'needs_dtce_search': True,
                'search_folders': [],
                'doc_types': [],
                'use_semantic': True,
                'use_hybrid': True
            }
        }
