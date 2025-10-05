"""
Intent Detection Service
Uses GPT to intelligently classify user queries into categories
"""
import structlog
from typing import Dict, Optional
from openai import AsyncAzureOpenAI
import json
import re

logger = structlog.get_logger(__name__)


class IntentDetector:
    """
    Intelligent intent classification using GPT to route queries to the right data sources.
    """
    
    INTENTS = {
        "policy": {
            "description": "Company policies (H&S, IT, HR, etc.) - strict documents employees must follow",
            "folders": ["Policies", "Health and Safety", "H&S", "HR Policies", "IT Policies", "Company Documents"],
            "filter": "search.ismatch('policies|company documents|health and safety|wellbeing|wellness', 'folder', 'any')"
        },
        "procedure": {
            "description": "Technical & admin procedures (How-To Handbooks/H2H) - best practices, not strict rules",
            "folders": ["Procedures", "How to Handbooks", "H2H", "Technical Procedures", "Engineering"],
            "filter": "search.ismatch('procedures|how to|h2h|technical', 'folder', 'any')"
        },
        "standard": {
            "description": "NZ Engineering Standards (NZS codes, AS/NZS standards) - official technical standards",
            "folders": ["Standards", "NZ Standards", "NZS", "Engineering Standards", "Codes", "Technical Library"],
            "filter": "search.ismatch('standards|nzs|technical library|codes', 'folder', 'any')"
        },
        "project": {
            "description": "Past project information (job folders, project documents) - structured by job number (e.g., 225221)",
            "folders": ["Projects", "Jobs", "Clients"],
            "filter": "search.ismatch('219|220|221|222|223|224|225', 'folder', 'any')"
        },
        "client": {
            "description": "Client information (contact details, client history) - found in client folders",
            "folders": ["Clients"],
            "filter": "search.ismatch('clients', 'folder', 'any')"
        },
        "general": {
            "description": "General knowledge, company info, or unclear intent - search everything",
            "folders": [],
            "filter": None
        }
    }
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def detect_intent(self, user_query: str, conversation_history: list = None) -> Dict:
        """
        Use GPT to intelligently detect the intent of the user's query.
        Returns: {intent: str, confidence: float, reasoning: str, search_filter: str}
        """
        try:
            # Build conversation context
            context = ""
            if conversation_history:
                recent = conversation_history[-3:]
                context = "\n".join([f"{t['role']}: {t['content']}" for t in recent])
            
            # Create intent detection prompt
            intent_prompt = f"""You are an intent classifier for an engineering company's AI assistant.

User Question: "{user_query}"

{f"Recent Conversation:\n{context}\n" if context else ""}

Your job: Classify this question into ONE of these categories:

1. **policy** - Questions about company policies, rules, H&S procedures, HR/IT policies, employee requirements
   Examples: "what's the wellness policy?", "H&S procedures", "sick leave policy", "harassment policy"

2. **procedure** - Questions about how to do things, best practices, technical procedures, How-To guides
   Examples: "how do I use the wind speed spreadsheet?", "procedure for site inspections", "best practice for..."

3. **standard** - Questions about NZ engineering standards, codes, AS/NZS specifications, technical standards
   Examples: "what does NZS 3604 say about...", "timber framing standards", "seismic design code"

4. **project** - Questions about past projects, job numbers, project details, work history
   Examples: "what is project 225?", "tell me about job 219208", "projects from 2025", "project 225"

5. **client** - Questions about clients, contact details, client history, client relationships
   Examples: "who is the client for...", "contact details for...", "projects with client X"

6. **general** - General questions, company info, or unclear intent that doesn't fit above
   Examples: "who works here?", "company overview", "tell me about DTCE"

IMPORTANT: When someone asks "project 225" or "job 219208", they want PROJECT information, not technical specs like "225mm beam depth"!

Think about what the user REALLY wants to know. Return ONLY valid JSON:
{{"intent": "policy", "confidence": 0.95, "reasoning": "brief explanation"}}"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert at understanding user intent. Always return valid JSON only, no other text."},
                    {"role": "user", "content": intent_prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            # Parse response
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                intent = result.get('intent', 'general')
                confidence = result.get('confidence', 0.5)
                reasoning = result.get('reasoning', '')
                
                # Validate intent
                if intent not in self.INTENTS:
                    intent = 'general'
                
                # Get search filter for this intent
                search_filter = self.INTENTS[intent].get('filter')
                
                logger.info("Intent detected using AI", 
                           query=user_query, 
                           intent=intent, 
                           confidence=confidence,
                           reasoning=reasoning)
                
                return {
                    'intent': intent,
                    'confidence': confidence,
                    'reasoning': reasoning,
                    'search_filter': search_filter,
                    'folders': self.INTENTS[intent].get('folders', [])
                }
            else:
                raise ValueError("No JSON found in response")
                
        except Exception as e:
            logger.error("Intent detection failed", error=str(e), query=user_query)
            # Fallback to general intent
            return {
                'intent': 'general',
                'confidence': 0.0,
                'reasoning': f'Error in detection: {str(e)}',
                'search_filter': None,
                'folders': []
            }
