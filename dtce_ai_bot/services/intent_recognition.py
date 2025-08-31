"""
Intent Recognition Service for DTCE AI Bot
Classifies user queries into specific intents for better routing and search targeting
"""

import re
from typing import Dict, List, Optional, Tuple
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class QueryIntent(Enum):
    """Enumeration of DTCE-specific user query intents."""
    POLICY = "policy"  # H&S, IT, Employment policies - strict documents employees must follow
    TECHNICAL_PROCEDURE = "technical_procedure"  # H2H handbooks - best practices and how-to guides
    NZ_STANDARDS = "nz_standards"  # NZ engineering standards and codes
    PROJECT_REFERENCE = "project_reference"  # Past project information and examples
    CLIENT_REFERENCE = "client_reference"  # Client contact details and project history
    GENERAL = "general"  # Fallback for unclear queries


class IntentRecognitionService:
    """
    Service to classify user queries into specific intents for targeted search.
    
    This replaces keyword-based query enhancement with proper intent classification
    that routes queries to the most relevant document types and search strategies.
    """
    
    def __init__(self):
        """Initialize intent patterns and classifications."""
        self.intent_patterns = self._initialize_intent_patterns()
        self.confidence_threshold = 0.7
        
    def _initialize_intent_patterns(self) -> Dict[QueryIntent, Dict[str, any]]:
        """Define patterns and keywords for each DTCE-specific intent type."""
        return {
            QueryIntent.POLICY: {
                "keywords": [
                    # Policy-specific terms
                    "policy", "policies", "must follow", "required", "compliance",
                    "h&s", "health and safety", "safety policy", "it policy", 
                    "employment policy", "hr policy", "quality policy",
                    "wellness", "wellbeing", "well-being", "mental health",
                    "employee assistance", "eap", "work life balance",
                    "leave policy", "vacation policy", "sick leave",
                    "code of conduct", "ethics", "discrimination", "harassment"
                ],
                "patterns": [
                    r"what.*(?:our|company|dtce).*policy",
                    r"(?:policy|policies).*(?:on|about|regarding|for)",
                    r"(?:h&s|safety|employment|wellness|it).*policy",
                    r"policy.*(?:say|state|require)",
                    r"(?:must|should|required).*(?:follow|comply)",
                    r"employee.*(?:handbook|policy|guideline)"
                ],
                "document_types": [],  # Don't restrict - policies could be in any format
                "folders": ["Health & Safety", "IT Policy", "Employment", "Quality", "Operations"],
                "description": "Company policies that employees must follow (H&S, IT, Employment, etc.)"
            },
            
            QueryIntent.TECHNICAL_PROCEDURE: {
                "keywords": [
                    # H2H and procedure terms
                    "how to", "h2h", "handbook", "procedure", "process", "method",
                    "best practice", "how do i", "how we do", "steps", "guide",
                    "workflow", "approach", "technique", "way to",
                    "spreadsheet", "tool", "software", "calculation method",
                    "wind speed", "site", "analysis", "design process"
                ],
                "patterns": [
                    r"how\s+(?:to|do|we)",
                    r"(?:procedure|process|method).*(?:for|to|on)",
                    r"(?:h2h|handbook).*(?:for|on|about)",
                    r"best.*(?:practice|way|approach)",
                    r"(?:steps|guide).*(?:for|to|on)",
                    r"how.*(?:use|operate|work).*(?:spreadsheet|tool|software)"
                ],
                "document_types": [],  # Don't restrict - procedures could be PDFs, spreadsheets, etc.
                "folders": ["H2H", "Technical Procedures", "Admin Procedures", "Engineering Procedures"],
                "description": "How-to handbooks and best practice procedures (H2H documents)"
            },
            
            QueryIntent.NZ_STANDARDS: {
                "keywords": [
                    # NZ Standards specific
                    "nzs", "nz standard", "new zealand standard", "building code",
                    "standard", "code", "specification", "requirement",
                    "compliance", "regulation", "guideline", "nzbc",
                    "seismic", "wind", "steel", "concrete", "timber", "loading"
                ],
                "patterns": [
                    r"nzs?\s*\d+",  # NZS 3404, NZS3404, etc.
                    r"(?:nz|new zealand).*standard",
                    r"building.*code",
                    r"standard.*(?:for|on|about|regarding)",
                    r"code.*(?:requirement|specification)",
                    r"compliance.*(?:with|to).*(?:nzs|standard|code)"
                ],
                "document_types": [],  # Don't restrict - standards could be in various formats
                "folders": ["Engineering Standards", "NZ Standards", "Codes"],
                "description": "NZ engineering standards and building codes (NZS documents)"
            },
            
            QueryIntent.PROJECT_REFERENCE: {
                "keywords": [
                    # Project search terms
                    "project", "job", "past project", "previous project", "similar project",
                    "project example", "project reference", "case study", "experience",
                    "building", "structure", "construction", "development",
                    "assessment", "analysis", "report", "scope", "brief",
                    "client work", "past work", "similar work", "project like"
                ],
                "patterns": [
                    r"(?:past|previous|similar).*project",
                    r"project.*(?:like|similar|about|on|for)",
                    r"(?:have|did).*(?:we|you).*(?:work|project|job)",
                    r"(?:example|reference).*project",
                    r"project.*(?:with|involving|regarding)",
                    r"(?:building|structure).*project"
                ],
                "document_types": [],  # Don't restrict - projects have diverse file types
                "folders": ["Projects", "225", "224", "223", "222", "221", "220"],  # Include year folders
                "description": "Past project information, examples, and references"
            },
            
            QueryIntent.CLIENT_REFERENCE: {
                "keywords": [
                    # Client-specific terms
                    "client", "client contact", "contact details", "client information",
                    "past client", "client project", "client work", "who worked",
                    "contact", "phone", "email", "address", "client details",
                    "client history", "projects with", "work for"
                ],
                "patterns": [
                    r"client.*(?:contact|detail|information|phone|email)",
                    r"contact.*(?:for|of).*client",
                    r"(?:projects|work).*(?:with|for).*client",
                    r"client.*(?:history|past|previous)",
                    r"who.*(?:contact|client|worked)",
                    r"(?:phone|email|address).*(?:for|of).*client"
                ],
                "document_types": [],  # Don't restrict - client info could be anywhere
                "folders": ["Projects", "01 Admin Documents", "Clients"],
                "description": "Client contact details and project history"
            }
        }
    
    def classify_intent(self, query: str) -> Dict[str, any]:
        """
        Classify a user query into the most likely intent.
        
        Args:
            query: User's query string
            
        Returns:
            Dictionary containing:
            - intent: QueryIntent enum value
            - confidence: Float between 0-1
            - metadata: Intent-specific metadata for search optimization
        """
        query_lower = query.lower().strip()
        intent_scores = {}
        
        # Score each intent based on keyword matches and pattern matches
        for intent, config in self.intent_patterns.items():
            score = 0.0
            
            # Keyword matching (weighted)
            keyword_matches = sum(1 for keyword in config["keywords"] 
                                if keyword.lower() in query_lower)
            keyword_score = keyword_matches / len(config["keywords"])
            
            # Pattern matching (higher weight)
            pattern_matches = sum(1 for pattern in config["patterns"] 
                                if re.search(pattern, query_lower, re.IGNORECASE))
            pattern_score = pattern_matches / len(config["patterns"]) if config["patterns"] else 0
            
            # Combined score (patterns weighted more heavily)
            score = (keyword_score * 0.4) + (pattern_score * 0.6)
            intent_scores[intent] = score
        
        # Find best intent
        best_intent = max(intent_scores.keys(), key=lambda k: intent_scores[k])
        confidence = intent_scores[best_intent]
        
        # Fallback to general if confidence is too low
        if confidence < self.confidence_threshold:
            best_intent = QueryIntent.GENERAL
            confidence = 0.5
        
        # Get metadata for the classified intent
        metadata = self._get_intent_metadata(best_intent, query)
        
        logger.info("Intent classification completed",
                   query=query,
                   intent=best_intent.value,
                   confidence=confidence,
                   all_scores={intent.value: score for intent, score in intent_scores.items()})
        
        return {
            "intent": best_intent,
            "confidence": confidence,
            "metadata": metadata,
            "debug_scores": intent_scores
        }
    
    def _get_intent_metadata(self, intent: QueryIntent, query: str) -> Dict[str, any]:
        """Get search optimization metadata for a classified intent."""
        if intent == QueryIntent.GENERAL:
            return {
                "document_types": [],
                "priority_folders": [],
                "search_strategy": "general_semantic",
                "description": "General search across all document types"
            }
        
        config = self.intent_patterns[intent]
        
        # Extract year information for project searches
        year_context = None
        if intent in [QueryIntent.PROJECT_REFERENCE, QueryIntent.CLIENT_REFERENCE]:
            year_matches = re.findall(r'\b(20[0-2][0-9])\b', query)
            if year_matches:
                year_context = year_matches[0]
                # Convert to folder code (2024 -> 224)
                folder_code = year_context[1:]  # Remove first digit: 2024 -> 024 -> 24
                if folder_code.startswith('0'):
                    folder_code = folder_code[1:]  # Remove leading zero: 024 -> 24
                folder_code = '2' + folder_code  # Add 2 prefix: 24 -> 224
                
        return {
            "document_types": config["document_types"],
            "priority_folders": config["folders"],
            "search_strategy": "targeted_semantic",
            "description": config["description"],
            "year_context": year_context,
            "folder_code": folder_code if year_context else None
        }
    
    def get_search_strategy(self, intent_result: Dict[str, any]) -> Dict[str, any]:
        """
        Convert intent classification into concrete search strategy for DTCE.
        
        Args:
            intent_result: Result from classify_intent()
            
        Returns:
            Search strategy configuration optimized for DTCE document types
        """
        intent = intent_result["intent"]
        metadata = intent_result["metadata"]
        confidence = intent_result["confidence"]
        
        base_strategy = {
            "intent_type": intent.value,
            "confidence": confidence,
            "description": metadata["description"]
        }
        
        # High confidence: use targeted search with specific folder filtering
        if confidence > 0.8:
            strategy = {
                **base_strategy,
                "search_type": "targeted_semantic",
                "document_types": metadata["document_types"],
                "folder_filters": metadata["priority_folders"],
                "use_strict_filtering": True,
                "boost_folder_matches": True
            }
            
            # Special handling for project/client searches with year context
            if intent in [QueryIntent.PROJECT_REFERENCE, QueryIntent.CLIENT_REFERENCE]:
                if metadata.get("folder_code"):
                    strategy["folder_filters"] = [metadata["folder_code"]]
                    strategy["description"] += f" (filtered to {metadata['year_context']})"
            
            return strategy
        
        # Medium confidence: light targeting with document type filtering
        elif confidence > 0.6:
            return {
                **base_strategy,
                "search_type": "light_semantic",
                "document_types": metadata["document_types"],
                "folder_filters": metadata["priority_folders"],
                "use_strict_filtering": False,
                "boost_folder_matches": True
            }
        
        # Low confidence: general semantic search with minimal filtering
        else:
            return {
                **base_strategy,
                "search_type": "general_semantic", 
                "document_types": [],
                "folder_filters": [],
                "use_strict_filtering": False,
                "boost_folder_matches": False
            }
