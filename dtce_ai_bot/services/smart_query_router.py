"""
Smart Query Router - The "Brain" that understands user intent and guides search
"""

import re
from typing import Dict, List, Tuple, Optional
import structlog
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class SmartQueryRouter:
    """
    The intelligent router that analyzes user queries and determines:
    1. What folder to search in
    2. What keywords to use for search
    3. How to handle the query type
    """
    
    def __init__(self, openai_client: AsyncAzureOpenAI):
        self.openai_client = openai_client
        
        # Enhanced intent mappings with comprehensive synonyms
        self.intent_mappings = {
            "policy": {
                "folder": "policies",
                "triggers": [
                    # Core policy terms
                    "policy", "policies", "rule", "rules", "guideline", "guidelines", 
                    "regulation", "regulations", "code of conduct",
                    # Specific policy types
                    "wellness", "wellbeing", "health policy", "mental health",
                    "safety policy", "health and safety", "occupational safety",
                    "privacy", "data protection", "confidentiality", "GDPR",
                    "harassment", "bullying", "discrimination", "ethics",
                    "environmental policy", "sustainability", "green policy",
                    "IT security", "information security", "cyber security",
                    # Common question patterns
                    "what's our policy", "company policy", "workplace policy",
                    "employee policy", "staff policy", "organizational policy"
                ],
                "search_boost": ["policy", "employee", "workplace", "company", "guideline", "rule"]
            },
            "procedure": {
                "folder": "procedures",
                "triggers": [
                    # Core procedure terms
                    "procedure", "procedures", "process", "steps", "how to", "how-to",
                    "guide", "instruction", "instructions", "method", "way",
                    # Specific procedures
                    "leave request", "time off", "vacation", "holiday", "sick leave",
                    "expense claim", "reimbursement", "cost claim", "expenses",
                    "hiring", "recruitment", "recruit", "employ", "staffing",
                    "incident report", "accident report", "emergency", "issue report",
                    "procurement", "purchase", "buying", "acquisition", "ordering",
                    "building access", "after hours", "key card", "security access",
                    "evacuation", "fire drill", "emergency exit",
                    # Common question patterns
                    "how do I", "how to", "what's the process", "how can I",
                    "steps to", "way to", "submit", "apply for", "request"
                ],
                "search_boost": ["procedure", "process", "how-to", "guide", "steps", "instruction"]
            },
            "standard": {
                "folder": "standards",
                "triggers": [
                    # Core standard terms
                    "standard", "standards", "specification", "specs", "requirement",
                    "criteria", "code", "codes", "regulation", "compliance",
                    # Specific standards
                    "quality standard", "QA", "quality assurance", "quality control",
                    "ISO", "certification", "accreditation", "audit",
                    "building code", "construction standard", "structural standard",
                    "engineering standard", "technical standard", "design standard",
                    "safety standard", "protection standard", "risk standard",
                    "environmental standard", "green standard", "sustainable",
                    "NZS", "AS/NZS", "Australian standard", "New Zealand standard",
                    # Common question patterns
                    "what standards", "which codes", "compliance with", "meet standards",
                    "follow codes", "building requirements", "technical requirements"
                ],
                "search_boost": ["standard", "NZS", "AS/NZS", "code", "engineering", "technical", "compliance"]
            },
            "project": {
                "folder": "projects",
                "triggers": [
                    # Core project terms
                    "project", "projects", "development", "construction", "build",
                    "site", "work", "job", "contract", "engagement",
                    # Specific project types
                    "Auckland", "waterfront", "harbour", "marina", "wharf",
                    "hospital", "medical facility", "healthcare", "health facility",
                    "CBD", "central business district", "city center", "downtown",
                    "residential", "housing", "apartment", "home", "dwelling",
                    "school", "education", "learning", "academic", "campus",
                    "infrastructure", "utilities", "roads", "transport", "services",
                    "Wellington", "capital", "commercial", "business", "office",
                    "roadway", "highway", "street", "bridge", "tunnel",
                    # Project aspects
                    "timeline", "schedule", "dates", "milestones", "phases",
                    "status", "progress", "update", "current state",
                    # Common question patterns
                    "tell me about", "project details", "work on", "building",
                    "construction of", "development of", "site work"
                ],
                "search_boost": ["project", "client", "site", "construction", "engineering", "report", "development"]
            },
            "client": {
                "folder": "clients",
                "triggers": [
                    # Core client terms
                    "client", "clients", "customer", "customers", "stakeholder",
                    "partner", "organization", "contact", "representative",
                    # Client types
                    "government", "public sector", "council", "ministry", "department",
                    "private sector", "business", "corporate", "company",
                    "NZTA", "contractor", "subcontractor", "supplier", "vendor",
                    # Client interactions
                    "contact information", "client details", "liaison", "person",
                    "requirements", "needs", "expectations", "specifications",
                    "feedback", "review", "comments", "opinion", "satisfaction",
                    "contract", "agreement", "arrangement", "terms", "deal",
                    "communication", "correspondence", "discussion", "meeting",
                    "portfolio", "list", "collection", "group",
                    # Common question patterns
                    "who is our client", "client for", "contact for", "working with",
                    "client expects", "client wants", "client feedback"
                ],
                "search_boost": ["client", "contact", "email", "correspondence", "stakeholder", "organization"]
            }
        }
    
    async def route_query(self, user_query: str) -> Dict[str, any]:
        """
        Analyze the user query and return routing information.
        
        Returns:
            {
                "intent": "policy|procedure|standard|project|client|general",
                "folder": "target_folder_name", 
                "enhanced_keywords": ["keyword1", "keyword2"],
                "original_query": "user's original query",
                "normalized_query": "cleaned up version"
            }
        """
        try:
            # Step 1: Clean and normalize the query
            normalized_query = self._normalize_query(user_query)
            
            # Step 2: Try simple pattern matching first (fast)
            intent_match = self._simple_intent_detection(normalized_query)
            
            if intent_match:
                logger.info("Router matched intent", intent=intent_match, query=user_query[:100])
                return self._build_routing_response(intent_match, user_query, normalized_query)
            
            # Step 3: If no simple match, use AI to understand intent (slower but smarter)
            ai_intent = await self._ai_intent_analysis(normalized_query)
            
            logger.info("Router used AI analysis", intent=ai_intent, query=user_query[:100])
            return self._build_routing_response(ai_intent, user_query, normalized_query)
            
        except Exception as e:
            logger.error("Router failed, using fallback", error=str(e), query=user_query[:100])
            # Fallback to general search
            return {
                "intent": "general",
                "folder": None,
                "enhanced_keywords": self._extract_keywords(user_query),
                "original_query": user_query,
                "normalized_query": normalized_query
            }
    
    def _normalize_query(self, query: str) -> str:
        """Clean up the query for better matching."""
        # Fix common typos
        typo_fixes = {
            "welness": "wellness",
            "safty": "safety", 
            "proceedure": "procedure",
            "standrd": "standard",
            "clent": "client"
        }
        
        normalized = query.lower().strip()
        
        # Apply typo fixes
        for typo, correction in typo_fixes.items():
            normalized = normalized.replace(typo, correction)
        
        # Remove unnecessary words
        stop_words = ["what's", "what is", "show me", "find", "get", "tell me about", "where is"]
        for stop_word in stop_words:
            normalized = normalized.replace(stop_word, "")
        
        return normalized.strip()
    
    def _simple_intent_detection(self, query: str) -> Optional[str]:
        """Fast pattern matching for common queries."""
        query_lower = query.lower()
        
        # Score each intent based on trigger word matches
        intent_scores = {}
        
        for intent, config in self.intent_mappings.items():
            score = 0
            for trigger in config["triggers"]:
                if trigger.lower() in query_lower:
                    # Boost score for exact matches
                    if trigger.lower() == query_lower.strip():
                        score += 10
                    else:
                        score += 1
            
            if score > 0:
                intent_scores[intent] = score
        
        # Return the intent with highest score
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            if best_intent[1] >= 1:  # Minimum confidence threshold
                return best_intent[0]
        
        return None
    
    async def _ai_intent_analysis(self, query: str) -> str:
        """Use AI to understand complex or ambiguous queries."""
        
        prompt = f"""Analyze this user query and determine which category it belongs to:

Query: "{query}"

Categories:
1. POLICY - Questions about company policies, HR rules, health & safety policies, IT policies, employee guidelines
2. PROCEDURE - Questions about how to do something, step-by-step guides, procedures, handbooks (H2H)
3. STANDARD - Questions about engineering standards, codes (NZS, AS/NZS), technical standards, building codes
4. PROJECT - Questions about past projects, specific project work, construction projects, engineering reports
5. CLIENT - Questions about clients, contact information, client correspondence, NZTA work
6. GENERAL - Anything else that doesn't fit the above categories

Respond with only the category name: POLICY, PROCEDURE, STANDARD, PROJECT, CLIENT, or GENERAL"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.1
            )
            
            ai_response = response.choices[0].message.content.strip().upper()
            
            # Map AI response to our intent keys
            mapping = {
                "POLICY": "policy",
                "PROCEDURE": "procedure", 
                "STANDARD": "standard",
                "PROJECT": "project",
                "CLIENT": "client",
                "GENERAL": "general"
            }
            
            return mapping.get(ai_response, "general")
            
        except Exception as e:
            logger.warning("AI intent analysis failed", error=str(e))
            return "general"
    
    def _build_routing_response(self, intent: str, original_query: str, normalized_query: str) -> Dict[str, any]:
        """Build the routing response based on detected intent."""
        
        if intent in self.intent_mappings:
            config = self.intent_mappings[intent]
            
            # Extract keywords from query and add boost keywords
            query_keywords = self._extract_keywords(normalized_query)
            boost_keywords = config["search_boost"]
            
            # Combine and deduplicate keywords
            all_keywords = list(set(query_keywords + boost_keywords))
            
            return {
                "intent": intent,
                "folder": config["folder"],
                "enhanced_keywords": all_keywords,
                "original_query": original_query,
                "normalized_query": normalized_query
            }
        else:
            # General/unknown intent
            return {
                "intent": "general",
                "folder": None,
                "enhanced_keywords": self._extract_keywords(normalized_query),
                "original_query": original_query,
                "normalized_query": normalized_query
            }
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from the query."""
        # Remove common stop words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "what", "how", "where", "when", "why", "is", "are", "was", "were", "do", "does", "did", "can", "could", "would", "should", "our", "my", "your"}
        
        # Split into words and clean
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords[:10]  # Limit to top 10 keywords
