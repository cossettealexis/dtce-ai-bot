"""
Smart Semantic Search Service for DTCE AI Bot
Uses intelligent routing to search in the right folders with the right keywords
"""

import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient

logger = structlog.get_logger(__name__)


class SemanticSearchService:
    """
    Smart semantic search service that uses router guidance for targeted searches.
    """
    
    def __init__(self, search_client: SearchClient):
        self.search_client = search_client
        
    async def smart_search(self, routing_info: Dict[str, any]) -> List[Dict[str, any]]:
        """
        Perform smart search using router guidance.
        
        Args:
            routing_info: Output from SmartQueryRouter.route_query()
            
        Returns:
            List of relevant documents ranked by relevance
        """
        try:
            intent = routing_info.get("intent", "general")
            folder = routing_info.get("folder")
            keywords = routing_info.get("enhanced_keywords", [])
            normalized_query = routing_info.get("normalized_query", "")
            
            logger.info("Smart search starting", intent=intent, folder=folder, keywords=keywords[:5])
            
            # Build smart search query
            search_query = self._build_smart_query(normalized_query, keywords, intent)
            
            # Execute targeted search
            documents = await self._execute_smart_search(search_query, folder, intent)
            
            # Filter out superseded documents
            documents = self._filter_quality_documents(documents)
            
            logger.info("Smart search completed", intent=intent, total_found=len(documents))
            
            return documents
            
        except Exception as e:
            logger.error("Smart search failed", error=str(e), routing_info=routing_info)
            # Fallback to basic search
            return await self._fallback_search(routing_info.get("original_query", ""))
    
    def _build_smart_query(self, normalized_query: str, keywords: List[str], intent: str) -> str:
        """Build an optimized search query with synonyms and related terms."""
        
        # Define comprehensive synonym mappings for each intent
        synonym_maps = {
            "policy": {
                # Core terms
                "policy": ["policy", "policies", "rule", "rules", "guideline", "guidelines", "regulation", "regulations"],
                "wellness": ["wellness", "wellbeing", "health", "mental health", "employee health", "workplace health"],
                "safety": ["safety", "health and safety", "occupational safety", "workplace safety", "safe work"],
                "privacy": ["privacy", "data protection", "confidentiality", "personal information", "GDPR"],
                "conduct": ["conduct", "code of conduct", "behavior", "behaviour", "ethics", "professional conduct"],
                "harassment": ["harassment", "bullying", "discrimination", "inappropriate behavior", "workplace harassment"],
                "environment": ["environment", "environmental", "sustainability", "green", "eco", "carbon"],
                "security": ["security", "IT security", "information security", "cyber security", "data security"],
                # Action words
                "what": ["what", "show", "tell", "explain", "describe"],
                "our": ["our", "company", "organization", "workplace", "DTCE"]
            },
            
            "procedure": {
                # Core terms
                "procedure": ["procedure", "procedures", "process", "steps", "how-to", "guide", "instruction"],
                "request": ["request", "apply", "submit", "application", "form"],
                "leave": ["leave", "time off", "vacation", "holiday", "sick leave", "annual leave"],
                "expense": ["expense", "expenses", "claim", "reimbursement", "cost", "spending"],
                "hiring": ["hiring", "recruitment", "recruit", "employ", "staff", "personnel"],
                "incident": ["incident", "report", "accident", "emergency", "issue", "problem"],
                "procurement": ["procurement", "purchase", "buying", "acquisition", "vendor", "supplier"],
                "access": ["access", "entry", "building", "after hours", "security", "key card"],
                "evacuation": ["evacuation", "emergency", "fire drill", "exit", "escape"],
                # Action words
                "how": ["how", "steps", "process", "way", "method"],
                "submit": ["submit", "send", "file", "lodge", "apply"]
            },
            
            "standard": {
                # Core terms
                "standard": ["standard", "standards", "specification", "specs", "requirement", "criteria"],
                "quality": ["quality", "QA", "quality assurance", "quality control", "excellence"],
                "ISO": ["ISO", "certification", "accreditation", "compliance", "audit"],
                "building": ["building", "construction", "structural", "architectural", "civil"],
                "codes": ["codes", "building codes", "regulations", "bylaws", "compliance"],
                "design": ["design", "engineering", "technical", "specifications", "drawings"],
                "safety": ["safety", "safe", "protection", "risk", "hazard"],
                "compliance": ["compliance", "conform", "meet", "adhere", "follow"],
                "environmental": ["environmental", "green", "sustainable", "eco", "carbon"],
                # Action words
                "what": ["what", "which", "show", "tell", "explain"],
                "follow": ["follow", "use", "apply", "implement", "comply"]
            },
            
            "project": {
                # Core terms
                "project": ["project", "development", "construction", "build", "site", "work"],
                "Auckland": ["Auckland", "Auckland CBD", "city center", "downtown Auckland"],
                "waterfront": ["waterfront", "harbour", "marina", "coastal", "wharf"],
                "hospital": ["hospital", "medical", "healthcare", "health facility"],
                "timeline": ["timeline", "schedule", "dates", "milestones", "phases"],
                "status": ["status", "progress", "update", "current", "state"],
                "CBD": ["CBD", "central business district", "city center", "downtown"],
                "residential": ["residential", "housing", "apartment", "home", "dwelling"],
                "school": ["school", "education", "learning", "academic", "campus"],
                "infrastructure": ["infrastructure", "utilities", "roads", "transport", "services"],
                "Wellington": ["Wellington", "capital", "Wellington city"],
                "commercial": ["commercial", "business", "office", "retail", "shopping"],
                "housing": ["housing", "residential", "homes", "apartments", "accommodation"],
                "roadway": ["roadway", "road", "highway", "street", "transport"],
                # Action words
                "tell": ["tell", "show", "explain", "describe", "about"],
                "about": ["about", "regarding", "concerning", "on"]
            },
            
            "client": {
                # Core terms
                "client": ["client", "customer", "stakeholder", "partner", "organization"],
                "contact": ["contact", "representative", "liaison", "person", "details"],
                "requirements": ["requirements", "needs", "expectations", "specifications", "demands"],
                "feedback": ["feedback", "review", "comments", "opinion", "satisfaction"],
                "contract": ["contract", "agreement", "arrangement", "terms", "deal"],
                "communication": ["communication", "correspondence", "discussion", "meeting", "email"],
                "government": ["government", "public sector", "council", "ministry", "department"],
                "private": ["private", "private sector", "business", "corporate", "company"],
                "portfolio": ["portfolio", "list", "collection", "group", "set"],
                # Action words
                "who": ["who", "which", "what", "show", "tell"],
                "show": ["show", "display", "list", "provide", "give"]
            }
        }
        
        # Start with the normalized query
        query_parts = [normalized_query]
        
        # Get synonyms for this intent
        intent_synonyms = synonym_maps.get(intent, {})
        
        # Expand keywords with synonyms
        expanded_keywords = set()
        
        # Add original keywords
        for keyword in keywords:
            expanded_keywords.add(keyword.lower())
            
            # Find synonyms for this keyword
            for base_term, synonyms in intent_synonyms.items():
                if keyword.lower() in [s.lower() for s in synonyms]:
                    # Add all synonyms for this term
                    expanded_keywords.update([s.lower() for s in synonyms])
        
        # Add intent-specific boost terms
        if intent == "policy":
            expanded_keywords.update(["policy", "employee", "workplace", "company"])
        elif intent == "procedure":
            expanded_keywords.update(["procedure", "how-to", "guide", "steps"])
        elif intent == "standard":
            expanded_keywords.update(["standard", "code", "engineering", "specification"])
        elif intent == "project":
            expanded_keywords.update(["project", "site", "construction", "development"])
        elif intent == "client":
            expanded_keywords.update(["client", "contact", "correspondence", "stakeholder"])
        
        # Add the most relevant expanded keywords
        expanded_list = list(expanded_keywords)
        query_parts.extend(expanded_list[:10])  # Top 10 expanded terms
        
        # Join with spaces and remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in query_parts:
            if term and term.strip() and term.lower() not in seen:
                unique_terms.append(term.strip())
                seen.add(term.lower())
        
        final_query = " ".join(unique_terms)
        
        logger.debug("Built smart query with synonyms", 
                    original=normalized_query, 
                    enhanced=final_query,
                    intent=intent,
                    expanded_terms=len(expanded_keywords))
        
        return final_query
    
    async def _execute_smart_search(self, search_query: str, folder: Optional[str], intent: str) -> List[Dict[str, any]]:
        """Execute the smart search with enhanced keywords instead of folder filters."""
        
        # Build base search parameters for semantic search
        search_params = {
            'search_text': search_query,
            'top': 20,
            'select': ["id", "filename", "content", "blob_url", "project_name", "folder"],
            'query_type': 'semantic',
            'semantic_configuration_name': 'default',
            'query_caption': 'extractive',
            'query_answer': 'extractive'
        }
        
        # Build filters - only quality filters, NO folder filters since folders are empty
        filters = [
            "not search.ismatch('*superseded*', 'filename')",
            "not search.ismatch('*superceded*', 'filename')",
            "not search.ismatch('*archive*', 'filename')",
            "not search.ismatch('*trash*', 'filename')"
        ]
        
        # Don't add folder filters since folder field is empty in the index
        # Instead rely on the enhanced search query to find the right documents
        
        if filters:
            search_params['filter'] = ' and '.join(filters)
        
        # Execute search
        try:
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Smart search executed", 
                       intent=intent, 
                       folder=folder,
                       documents_found=len(documents),
                       query=search_query[:100])
            
            return documents
            
        except Exception as e:
            logger.warning("Smart search failed, trying fallback", error=str(e))
            # Remove semantic parameters and try keyword search
            search_params.pop('query_type', None)
            search_params.pop('semantic_configuration_name', None)
            search_params.pop('query_caption', None)
            search_params.pop('query_answer', None)
            
            results = self.search_client.search(**search_params)
            return [dict(result) for result in results]
    
    async def _fallback_search(self, query: str) -> List[Dict[str, any]]:
        """Fallback to basic keyword search when smart search fails."""
        try:
            search_params = {
                'search_text': query,
                'top': 10,
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder"]
            }
            
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Fallback search executed", documents_found=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Even fallback search failed", error=str(e))
            return []
    
    def _filter_quality_documents(self, documents: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """Filter out low-quality or superseded documents."""
        filtered_docs = []
        
        for doc in documents:
            filename = doc.get('filename', '').lower()
            
            # Skip superseded/archived documents
            skip_patterns = ['superseded', 'superceded', 'archive', 'trash', 'old', 'backup']
            if any(pattern in filename for pattern in skip_patterns):
                continue
                
            # Skip very short content (likely not useful)
            content = doc.get('content', '')
            if len(content.strip()) < 50:
                continue
                
            filtered_docs.append(doc)
        
        return filtered_docs

    # Keep the old method for backward compatibility during transition
    async def search_documents(self, query: str, project_filter: Optional[str] = None) -> List[Dict[str, any]]:
        """
        Backward compatibility method. Will use basic search without routing.
        
        For new code, use smart_search() with routing_info instead.
        """
        logger.warning("Using deprecated search_documents method", query=query[:100])
        
        # Create a basic routing info for backward compatibility
        routing_info = {
            "intent": "general",
            "folder": None,
            "enhanced_keywords": query.split(),
            "original_query": query,
            "normalized_query": query.lower().strip()
        }
        
        return await self.smart_search(routing_info)
