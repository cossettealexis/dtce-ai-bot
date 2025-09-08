"""
Query Normalization Service for DTCE AI Bot

Converts natural language queries into optimized semantic search terms to improve
search consistency and accuracy. Handles query expansion, entity extraction,
and keyword normalization for better document retrieval.

This service addresses the core issue where "wellness policy" works but 
"what's our wellness policy" fails by normalizing both to effective search terms.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import structlog
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class QueryNormalizer:
    """
    Normalizes natural language queries using AI semantic understanding.
    
    This service solves the core inconsistency issue where "wellness policy" works
    but "what's our wellness policy" fails by using AI to understand the true 
    intent and meaning behind queries, then generating search terms that match
    how documents are actually written.
    
    Key Features:
    - AI-powered semantic understanding of user intent
    - Generation of document-appropriate search terms
    - Multiple alternative search variations for better recall
    - Fallback to rule-based normalization when AI is unavailable
    - Focus on meaning rather than keyword extraction
    """
    
    def __init__(self, openai_client: Optional[AsyncAzureOpenAI] = None, model_name: str = "gpt-4"):
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def normalize_query(self, query: str) -> Dict[str, Any]:
        """
        Normalize a natural language query using AI semantic understanding.
        
        This method uses AI to understand the true intent and meaning behind
        queries, then generates search terms that match how documents are
        actually written, rather than relying on keyword extraction.
        
        Args:
            query: Original natural language query
            
        Returns:
            Dictionary containing semantically optimized search queries
        """
        try:
            logger.info("Normalizing query with semantic understanding", original_query=query)
            
            # Use AI-powered semantic understanding as primary method
            if self.openai_client:
                ai_result = await self._ai_semantic_normalization(query)
                if ai_result.get('success'):
                    logger.info("AI semantic normalization successful", 
                               primary_query=ai_result['primary_search_query'])
                    return ai_result
            
            # Fallback to rule-based normalization if AI fails
            logger.info("Using fallback rule-based normalization")
            return await self._fallback_normalization(query)
            
        except Exception as e:
            logger.error("Query normalization failed", error=str(e), query=query)
            # Ultimate fallback
            return {
                'original_query': query,
                'primary_search_query': query,
                'alternative_queries': [query],
                'semantic_concepts': [],
                'document_terms': [],
                'confidence': 0.3,
                'method': 'fallback'
            }
    
    async def _ai_semantic_normalization(self, query: str) -> Dict[str, Any]:
        """
        Use AI to understand query intent and generate semantically equivalent search terms.
        
        This is the core method that solves the "wellness policy" vs "what's our wellness policy"
        inconsistency by understanding meaning rather than parsing keywords.
        """
        try:
            prompt = f"""You are an expert at understanding user intent and generating effective search queries for an engineering document database.

USER QUERY: "{query}"

TASK: Analyze this query and generate optimal search terms that will find relevant documents.

CONTEXT: This is a DTCE engineering document database containing:
- Company policies (wellness, IT, safety, HR, etc.)
- Project templates and forms
- Technical standards and procedures  
- Engineering documentation
- Safety and regulatory documents

INSTRUCTIONS:
1. Understand the TRUE INTENT behind the user's question
2. Think about how relevant documents would actually be titled or written
3. Generate search terms that match document language, not conversational language
4. Consider multiple ways the same concept might be expressed in formal documents

EXAMPLES:
- "what's our wellness policy" → "wellness policy" + "employee wellness" + "health safety policy"
- "how do I submit a project" → "project submission" + "project template" + "project process"
- "where can I find safety rules" → "safety procedures" + "safety policy" + "safety guidelines"

OUTPUT FORMAT (JSON):
{{
    "primary_search_query": "main search terms that best match document titles/content",
    "alternative_queries": ["alternative1", "alternative2", "alternative3"],
    "semantic_concepts": ["concept1", "concept2"],
    "document_terms": ["formal term1", "formal term2"],
    "reasoning": "brief explanation of the approach"
}}

Analyze the query and respond with JSON only:"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=300
            )
            
            # Parse the JSON response
            import json
            result_text = response.choices[0].message.content.strip()
            
            # Clean up the response to ensure it's valid JSON
            if result_text.startswith('```json'):
                result_text = result_text.replace('```json', '').replace('```', '')
            elif result_text.startswith('```'):
                result_text = result_text.replace('```', '')
            
            ai_result = json.loads(result_text)
            
            # Enhance the result with metadata
            final_result = {
                'original_query': query,
                'primary_search_query': ai_result.get('primary_search_query', query),
                'alternative_queries': ai_result.get('alternative_queries', []),
                'semantic_concepts': ai_result.get('semantic_concepts', []),
                'document_terms': ai_result.get('document_terms', []),
                'reasoning': ai_result.get('reasoning', ''),
                'confidence': 0.85,  # High confidence for AI-generated results
                'method': 'ai_semantic',
                'success': True
            }
            
            logger.info("AI semantic normalization completed",
                       primary_query=final_result['primary_search_query'],
                       alternatives_count=len(final_result['alternative_queries']),
                       reasoning=final_result['reasoning'])
            
            return final_result
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse AI response as JSON", error=str(e), response=result_text[:200])
            # Try to extract at least the primary query from the response
            return await self._extract_query_from_text_response(query, result_text)
            
        except Exception as e:
            logger.error("AI semantic normalization failed", error=str(e))
            return {'success': False}
    
    async def _extract_query_from_text_response(self, original_query: str, ai_response: str) -> Dict[str, Any]:
        """Extract search query from AI response even if JSON parsing fails."""
        try:
            # Look for quoted search terms or clean text
            import re
            
            # Try to find quoted search terms
            quoted_terms = re.findall(r'"([^"]*)"', ai_response)
            
            if quoted_terms and len(quoted_terms[0]) > 2:
                primary_query = quoted_terms[0]
                alternatives = quoted_terms[1:4] if len(quoted_terms) > 1 else []
                
                return {
                    'original_query': original_query,
                    'primary_search_query': primary_query,
                    'alternative_queries': alternatives,
                    'semantic_concepts': [],
                    'document_terms': [],
                    'reasoning': 'Extracted from AI response',
                    'confidence': 0.7,
                    'method': 'ai_text_extraction',
                    'success': True
                }
            
            # Fallback to using the response directly (cleaned up)
            cleaned_response = re.sub(r'[^\w\s]', ' ', ai_response)
            cleaned_response = ' '.join(cleaned_response.split()[:10])  # Take first 10 words
            
            return {
                'original_query': original_query,
                'primary_search_query': cleaned_response or original_query,
                'alternative_queries': [original_query],
                'semantic_concepts': [],
                'document_terms': [],
                'reasoning': 'AI response cleanup fallback',
                'confidence': 0.5,
                'method': 'ai_fallback',
                'success': True
            }
            
        except Exception as e:
            logger.error("Failed to extract query from AI response", error=str(e))
            return {'success': False}
    
    async def _fallback_normalization(self, query: str) -> Dict[str, Any]:
        """
        Fallback normalization using rule-based approach when AI is unavailable.
        
        This is much simpler and focuses on basic cleanup rather than keyword extraction.
        """
        # Simple cleaning - remove question words and common noise
        cleaned = query.lower()
        
        # Remove common question patterns
        question_patterns = [
            r"what(?:'s|\s+is|\s+are)\s+",
            r"where(?:'s|\s+is|\s+are)\s+",
            r"how(?:\s+do\s+i|\s+can\s+i|\s+to)\s+",
            r"when(?:\s+is|\s+are|\s+do)\s+",
            r"why(?:\s+is|\s+are|\s+do)\s+",
            r"which(?:\s+is|\s+are)\s+",
            r"who(?:\s+is|\s+are)\s+",
        ]
        
        for pattern in question_patterns:
            cleaned = re.sub(pattern, '', cleaned)
        
        # Remove possessive words
        cleaned = re.sub(r'\b(?:our|my|your|their|the)\s+', '', cleaned)
        
        # Remove question marks and normalize spacing
        cleaned = re.sub(r'[?!.]+', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Generate alternatives by keeping original and adding variations
        alternatives = [query, cleaned]
        
        # Add domain-specific alternatives if we recognize key terms
        domain_alts = []
        if 'policy' in cleaned.lower():
            domain_alts.extend(['policy', 'procedure', 'guideline'])
        if 'template' in cleaned.lower():
            domain_alts.extend(['template', 'form', 'format'])
        if 'safety' in cleaned.lower():
            domain_alts.extend(['safety', 'security', 'risk'])
        
        if domain_alts:
            alternatives.extend(domain_alts)
        
        # Remove duplicates while preserving order
        unique_alternatives = []
        for alt in alternatives:
            if alt and alt not in unique_alternatives:
                unique_alternatives.append(alt)
        
        return {
            'original_query': query,
            'primary_search_query': cleaned or query,
            'alternative_queries': unique_alternatives[1:],  # Exclude the primary query
            'semantic_concepts': domain_alts,
            'document_terms': [],
            'reasoning': 'Rule-based cleanup and domain recognition',
            'confidence': 0.6,
            'method': 'rule_based',
            'success': True
        }


# Utility function for easy integration
async def normalize_search_query(query: str, openai_client: Optional[AsyncAzureOpenAI] = None) -> str:
    """
    Quick utility function to normalize a search query.
    
    Args:
        query: Original natural language query
        openai_client: Optional OpenAI client for AI enhancement
        
    Returns:
        Optimized search query string
    """
    normalizer = QueryNormalizer(openai_client)
    result = await normalizer.normalize_query(query)
    return result['primary_search_query']
