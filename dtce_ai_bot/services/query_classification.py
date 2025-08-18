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
You are an expert AI assistant that analyzes user queries for an engineering document AI system.

Your job is to determine if this is a legitimate engineering question and if so, how to handle it.

First, evaluate if this is a meaningful engineering-related query:
- Is it a complete, coherent question?
- Does it relate to engineering, construction, or technical topics?
- Is it asking for specific information (not just "hey", "what", random words)?

If it's NOT a meaningful engineering query (like greetings, random words, unclear input), classify as CONVERSATIONAL.

If it IS a meaningful engineering query, classify into the most appropriate category:

**DOCUMENT SEARCH CATEGORIES** (for DTCE internal documents):
1. **STANDARDS_CODES**: Specific building codes, standards, regulatory information (NZS, AS/NZS, etc.)
2. **TEMPLATE_DOCUMENT**: Templates, forms, spreadsheets, design tools (PS1, PS3, design spreadsheets)
3. **PROJECT_HISTORY**: Past DTCE projects, examples, case studies 
4. **SCOPE_COMPARISON**: Similar past projects for fee proposals or scope comparison
5. **SCENARIO_TECHNICAL**: Technical examples matching specific scenarios (building type + conditions)
6. **REGULATORY_PRECEDENT**: Regulatory challenges, council interactions, consent precedents
7. **COST_TIME_INSIGHTS**: Project timeline analysis, cost information, duration estimates, scope expansion
8. **BEST_PRACTICES_TEMPLATES**: Standard approaches, best practice examples, calculation templates, methodologies
9. **MATERIALS_METHODS**: Comparisons of materials, construction methods, technical specifications
10. **INTERNAL_KNOWLEDGE**: Engineers with specific expertise, work by team members, internal knowledge
11. **CONTRACTOR_BUILDER**: Information about builders, contractors, construction companies
12. **CONTACT_EXTRACTION**: Contact details from documents

**EXTERNAL/GPT CATEGORIES** (for external resources or general knowledge):
13. **WEB_EXTERNAL**: User specifically wants online forums, external discussions, public references
14. **TECHNICAL_DESIGN**: General engineering how-to questions, calculations, design guidance that GPT can answer
15. **CONVERSATIONAL**: Greetings, unclear input, random words, non-engineering chatter

User Question: "{question}"

Respond with ONLY a JSON object in this exact format:
{{
    "primary_intent": "CONVERSATIONAL|STANDARDS_CODES|TEMPLATE_DOCUMENT|PROJECT_HISTORY|SCOPE_COMPARISON|SCENARIO_TECHNICAL|REGULATORY_PRECEDENT|COST_TIME_INSIGHTS|BEST_PRACTICES_TEMPLATES|MATERIALS_METHODS|INTERNAL_KNOWLEDGE|WEB_EXTERNAL|TECHNICAL_DESIGN|CONTRACTOR_BUILDER|CONTACT_EXTRACTION",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this intent was chosen",
    "keywords": ["key", "terms", "identified"],
    "is_meaningful_query": true/false,
    "suggested_routing": "conversational|nz_standards|template_search|project_search|scope_comparison|scenario_technical|regulatory_precedent|cost_time_insights|best_practices_templates|materials_methods|internal_knowledge|web_search|general_search|contractor_search|contact_search"
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
        question_lower = question.lower().strip()
        
        # Check for obviously conversational/invalid queries
        if (len(question.strip()) < 3 or 
            question_lower in ['hey', 'hi', 'hello', 'what', 'really', 'ok', 'yes', 'no'] or
            not any(c.isalpha() for c in question) or  # No letters at all
            len(question.split()) < 2 or  # Less than 2 words
            any(phrase in question_lower for phrase in ['hey what', 'ahowa', 'howa are you', 'how are you', 'what are you', 'who are you'])):  # Common conversational patterns
            return {
                "primary_intent": "CONVERSATIONAL",
                "confidence": 0.9,
                "reasoning": "Query appears to be conversational or too brief to be meaningful",
                "keywords": [],
                "is_meaningful_query": False,
                "suggested_routing": "conversational"
            }
        
        # Simple keyword-based fallback for meaningful queries
        if any(term in question_lower for term in ['nzs', 'standard', 'code', 'as/nzs', 'building code']):
            return {
                "primary_intent": "STANDARDS_CODES",
                "confidence": 0.8,
                "reasoning": "Contains standards/codes keywords",
                "keywords": ["standards", "codes"],
                "is_meaningful_query": True,
                "suggested_routing": "nz_standards"
            }
        elif any(term in question_lower for term in ['online', 'forum', 'thread', 'external', 'public', 'web']):
            return {
                "primary_intent": "WEB_EXTERNAL", 
                "confidence": 0.8,
                "reasoning": "Contains web/external keywords",
                "keywords": ["online", "external"],
                "is_meaningful_query": True,
                "suggested_routing": "web_search"
            }
        elif any(term in question_lower for term in ['past project', 'previous', 'dtce', 'worked on', 'done before']):
            return {
                "primary_intent": "PROJECT_HISTORY",
                "confidence": 0.8,
                "reasoning": "Asking about past projects",
                "keywords": ["project", "history"],
                "is_meaningful_query": True,
                "suggested_routing": "project_search"
            }
        elif any(term in question_lower for term in ['builder', 'contractor', 'construction company', 'built']):
            return {
                "primary_intent": "CONTRACTOR_BUILDER",
                "confidence": 0.8,
                "reasoning": "Asking about builders/contractors",
                "keywords": ["builder", "contractor"],
                "is_meaningful_query": True,
                "suggested_routing": "contractor_search"
            }
        else:
            return {
                "primary_intent": "TECHNICAL_DESIGN",
                "confidence": 0.6,
                "reasoning": "General technical question",
                "keywords": ["technical"],
                "is_meaningful_query": True,
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
            "CONVERSATIONAL": "conversational",
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
