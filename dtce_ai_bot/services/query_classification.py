"""
Intelligent query classification service using AI to understand user intent.
"""

import asyncio
import re
from typing import Dict, List, Optional, Tuple
import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger(__name__)

class QueryClassificationService:
    """AI-powered service to intelligently classify user queries by intent."""
    
    def __init__(self, openai_client: AsyncOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def classify_query_intent(self, question: str) -> Dict[str, any]:
        """
        Use AI to intelligently classify the user's intent and determine routing.
        
        Returns:
            Dict with classification results including:
            - primary_intent: The main intent category
            - confidence: How confident the AI is in the classification
            - reasoning: Why this classification was chosen
            - suggested_routing: Which handler should process this query
        """
        
        classification_prompt = f"""
You are an expert AI assistant that analyzes engineering queries to determine user intent.

Analyze this user question and classify it into ONE primary intent category:

1. **STANDARDS_CODES**: User wants specific building codes, standards, or regulatory information (NZS, AS/NZS, etc.)
2. **TEMPLATE_DOCUMENT**: User wants specific templates, forms, spreadsheets, or design tools (PS1, PS3, design spreadsheets, etc.)
3. **PROJECT_HISTORY**: User wants to find past DTCE projects, examples, or case studies 
4. **SCOPE_COMPARISON**: User wants to find similar past projects for fee proposals or scope comparison
5. **SCENARIO_TECHNICAL**: User wants technical examples matching specific scenarios (building type + conditions + location)
6. **REGULATORY_PRECEDENT**: User wants examples of regulatory challenges, council interactions, alternative solutions, or consent precedents
7. **COST_TIME_INSIGHTS**: User wants project timeline analysis, cost information, duration estimates, or scope expansion examples
8. **BEST_PRACTICES_TEMPLATES**: User wants standard approaches, best practice examples, calculation templates, or design methodologies
9. **MATERIALS_METHODS**: User wants comparisons of materials, construction methods, or technical specifications across projects
10. **INTERNAL_KNOWLEDGE**: User wants to identify engineers with specific expertise, find work by specific team members, or access internal knowledge
11. **WEB_EXTERNAL**: User wants online resources, forums, external discussions, or public references
12. **TECHNICAL_DESIGN**: User wants technical design guidance, calculations, or how-to information
13. **CONTRACTOR_BUILDER**: User wants information about builders, contractors, or construction companies
14. **CONTACT_EXTRACTION**: User wants contact details extracted from SuiteFiles documents for clients or builders

User Question: "{question}"

Respond with ONLY a JSON object in this exact format:
{{
    "primary_intent": "STANDARDS_CODES|TEMPLATE_DOCUMENT|PROJECT_HISTORY|SCOPE_COMPARISON|WEB_EXTERNAL|TECHNICAL_DESIGN|CONTRACTOR_BUILDER|CONTACT_EXTRACTION",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this intent was chosen",
    "keywords": ["key", "terms", "identified"],
    "suggested_routing": "nz_standards|template_search|project_search|scope_comparison|scenario_technical|regulatory_precedent|web_search|general_search|contractor_search|contact_search"
}}
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,  # Use your Azure deployment model
                messages=[
                    {"role": "system", "content": "You are an expert query classifier for engineering queries. Respond only with valid JSON."},
                    {"role": "user", "content": classification_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=300
            )
            
            # Parse the JSON response
            import json
            classification = json.loads(response.choices[0].message.content.strip())
            
            logger.info("Query classified", 
                       question=question,
                       intent=classification.get('primary_intent'),
                       confidence=classification.get('confidence'))
            
            return classification
            
        except Exception as e:
            logger.error("Query classification failed", error=str(e), question=question)
            
            # Fallback to rule-based classification
            return self._fallback_classification(question)
    
    def _fallback_classification(self, question: str) -> Dict[str, any]:
        """Fallback rule-based classification if AI classification fails."""
        question_lower = question.lower()
        
        # Simple keyword-based fallback
        if any(term in question_lower for term in ['nzs', 'standard', 'code', 'as/nzs', 'building code']):
            return {
                "primary_intent": "STANDARDS_CODES",
                "confidence": 0.8,
                "reasoning": "Contains standards/codes keywords",
                "keywords": ["standards", "codes"],
                "suggested_routing": "nz_standards"
            }
        elif any(term in question_lower for term in ['online', 'forum', 'thread', 'external', 'public', 'web']):
            return {
                "primary_intent": "WEB_EXTERNAL", 
                "confidence": 0.8,
                "reasoning": "Contains web/external keywords",
                "keywords": ["online", "external"],
                "suggested_routing": "web_search"
            }
        elif any(term in question_lower for term in ['past project', 'previous', 'dtce', 'worked on', 'done before']):
            return {
                "primary_intent": "PROJECT_HISTORY",
                "confidence": 0.8,
                "reasoning": "Asking about past projects",
                "keywords": ["project", "history"],
                "suggested_routing": "project_search"
            }
        elif any(term in question_lower for term in ['builder', 'contractor', 'construction company', 'built']):
            return {
                "primary_intent": "CONTRACTOR_BUILDER",
                "confidence": 0.8,
                "reasoning": "Asking about builders/contractors",
                "keywords": ["builder", "contractor"],
                "suggested_routing": "contractor_search"
            }
        else:
            return {
                "primary_intent": "TECHNICAL_DESIGN",
                "confidence": 0.6,
                "reasoning": "General technical question",
                "keywords": ["technical"],
                "suggested_routing": "general_search"
            }

class SmartQueryRouter:
    """Smart query router that uses AI classification to route queries appropriately."""
    
    def __init__(self, classification_service: QueryClassificationService):
        self.classification_service = classification_service
    
    async def route_query(self, question: str) -> Tuple[str, Dict[str, any]]:
        """
        Route a query to the appropriate handler based on AI classification.
        
        Returns:
            Tuple of (handler_name, classification_details)
        """
        
        # Get AI classification
        classification = await self.classification_service.classify_query_intent(question)
        
        # Map intent to handler
        routing_map = {
            "STANDARDS_CODES": "nz_standards",
            "TEMPLATE_DOCUMENT": "template_search",
            "PROJECT_HISTORY": "project_search",
            "SCOPE_COMPARISON": "scope_comparison",
            "SCENARIO_TECHNICAL": "scenario_technical",
            "REGULATORY_PRECEDENT": "regulatory_precedent",
            "COST_TIME_INSIGHTS": "cost_time_insights",
            "BEST_PRACTICES_TEMPLATES": "best_practices_templates",
            "MATERIALS_METHODS": "materials_methods",
            "INTERNAL_KNOWLEDGE": "internal_knowledge",
            "WEB_EXTERNAL": "web_search",
            "TECHNICAL_DESIGN": "general_search",
            "CONTRACTOR_BUILDER": "contractor_search",
            "CONTACT_EXTRACTION": "contact_search"
        }
        
        primary_intent = classification.get('primary_intent', 'TECHNICAL_DESIGN')
        handler = routing_map.get(primary_intent, 'general_search')
        
        logger.info("Query routed",
                   question=question,
                   intent=primary_intent,
                   handler=handler,
                   confidence=classification.get('confidence'))
        
        return handler, classification
