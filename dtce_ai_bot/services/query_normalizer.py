"""
Query Normalizer Service
Handles query preprocessing, abbreviation expansion, and query enhancement for better search results.
"""

from typing import Dict, List, Any, Optional
import structlog
import re
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class QueryNormalizer:
    """
    Service for normalizing and enhancing user queries for improved search results.
    
    Features:
    - Engineering abbreviation expansion
    - Query standardization and cleanup
    - Alternative phrasing generation
    - Project context extraction
    - Technical term identification
    """
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
        
        # Engineering abbreviations specific to DTCE and NZ engineering
        self.abbreviations = {
            # Structural engineering
            'rc': 'reinforced concrete',
            'rcp': 'reinforced concrete pipe',
            'sls': 'serviceability limit state',
            'uls': 'ultimate limit state',
            'slb': 'simply supported beam',
            'psb': 'prestressed beam',
            'shw': 'shear wall',
            'clb': 'continuous beam',
            'glu': 'glulam',
            'lvl': 'laminated veneer lumber',
            'psw': 'precast wall',
            'clt': 'cross laminated timber',
            
            # NZ Standards
            'nzs': 'new zealand standard',
            'nzs3101': 'nzs 3101 concrete design',
            'nzs3404': 'nzs 3404 steel design',
            'nzs1170': 'nzs 1170 structural design actions',
            'nzbc': 'new zealand building code',
            'as/nzs': 'australian new zealand standard',
            
            # Materials
            'conc': 'concrete',
            'reinf': 'reinforcement',
            'rebar': 'reinforcement bar',
            'fy': 'yield strength',
            'fc': 'concrete compressive strength',
            'mpa': 'megapascals',
            'kpa': 'kilopascals',
            'gpa': 'gigapascals',
            
            # Loads and forces
            'dl': 'dead load',
            'll': 'live load',
            'eq': 'earthquake',
            'sw': 'self weight',
            'imp': 'imposed load',
            'wl': 'wind load',
            'sl': 'snow load',
            'kn': 'kilonewtons',
            'knm': 'kilonewton metres',
            
            # Geotechnical
            'cbr': 'california bearing ratio',
            'spt': 'standard penetration test',
            'cpt': 'cone penetration test',
            'dcp': 'dynamic cone penetrometer',
            'fos': 'factor of safety',
            'phi': 'angle of internal friction',
            'c': 'cohesion',
            'cu': 'undrained shear strength',
            
            # Common engineering terms
            'fem': 'finite element method',
            'cad': 'computer aided design',
            'bim': 'building information modelling',
            'qc': 'quality control',
            'qa': 'quality assurance',
            'coa': 'certificate of acceptance',
            'ps1': 'producer statement 1',
            'ps4': 'producer statement 4',
            'rfi': 'request for information',
            'rfp': 'request for proposal',
            'ror': 'record of resolution',
            
            # DTCE specific
            'dtce': 'don thomson consultants engineers',
            'h2h': 'how to how',
            'cpd': 'continuing professional development',
            'pe': 'professional engineer',
            'cpe': 'chartered professional engineer'
        }
    
    async def normalize_query(self, query: str) -> Dict[str, Any]:
        """
        Normalize and enhance a user query for better search performance.
        
        Args:
            query: Raw user query
            
        Returns:
            Dictionary with normalized query and metadata
        """
        try:
            logger.info("Normalizing query", original_query=query)
            
            # Step 1: Basic cleanup
            cleaned_query = self._basic_cleanup(query)
            
            # Step 2: Expand abbreviations
            expanded_query = self._expand_abbreviations(cleaned_query)
            
            # Step 3: Extract technical terms
            technical_terms = self._extract_technical_terms(expanded_query)
            
            # Step 4: Extract project information
            project_info = self._extract_project_info(expanded_query)
            
            # Step 5: Generate alternative phrasings using AI
            alternative_phrasings = await self._generate_alternative_phrasings(expanded_query)
            
            # Step 6: Create final enhanced query
            final_query = self._create_enhanced_query(expanded_query, technical_terms, alternative_phrasings)
            
            result = {
                'original_query': query,
                'cleaned_query': cleaned_query,
                'expanded_query': expanded_query,
                'final_query': final_query,
                'technical_terms': technical_terms,
                'project_info': project_info,
                'alternative_phrasings': alternative_phrasings,
                'abbreviations_expanded': self._get_expanded_abbreviations(query)
            }
            
            logger.info("Query normalization completed", 
                       final_query=final_query,
                       technical_terms_count=len(technical_terms))
            
            return result
            
        except Exception as e:
            logger.error("Query normalization failed", error=str(e), query=query)
            # Return basic normalization on error
            return {
                'original_query': query,
                'cleaned_query': query,
                'expanded_query': query,
                'final_query': query,
                'technical_terms': [],
                'project_info': {},
                'alternative_phrasings': [],
                'abbreviations_expanded': {}
            }
    
    def _basic_cleanup(self, query: str) -> str:
        """Perform basic query cleanup."""
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', query.strip())
        
        # Remove special characters that might interfere with search
        cleaned = re.sub(r'[^\w\s\-\.\(\)\/]', ' ', cleaned)
        
        # Normalize case for common terms
        cleaned = re.sub(r'\bnzs\b', 'NZS', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bdtce\b', 'DTCE', cleaned, flags=re.IGNORECASE)
        
        return cleaned
    
    def _expand_abbreviations(self, query: str) -> str:
        """Expand known engineering abbreviations."""
        expanded = query
        expanded_terms = {}
        
        # Split query into words for abbreviation matching
        words = expanded.lower().split()
        
        for word in words:
            # Clean word of punctuation for matching
            clean_word = re.sub(r'[^\w]', '', word)
            
            if clean_word in self.abbreviations:
                expansion = self.abbreviations[clean_word]
                # Use case-insensitive replacement
                pattern = r'\b' + re.escape(word) + r'\b'
                expanded = re.sub(pattern, expansion, expanded, flags=re.IGNORECASE)
                expanded_terms[clean_word] = expansion
        
        return expanded
    
    def _extract_technical_terms(self, query: str) -> List[str]:
        """Extract technical engineering terms from the query."""
        technical_terms = []
        
        # Standard patterns for technical terms
        patterns = [
            r'\bNZS\s+\d{4}(?:\.\d+)?\b',  # NZ Standards
            r'\b\d+\s*MPa\b',              # Strength values
            r'\b\d+\s*kPa\b',              # Pressure values
            r'\b\d+\s*kN\b',               # Force values
            r'\b\d+\s*mm\b',               # Dimensions
            r'\b\d+\s*m\b',                # Dimensions
            r'\bC\d{2,3}\b',               # Concrete grades
            r'\bGrade\s+\d+\b',            # Material grades
            r'\b[A-Z]{2,6}\d+\b',          # Technical codes
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            technical_terms.extend(matches)
        
        # Add expanded abbreviations as technical terms
        for word in query.split():
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word in self.abbreviations:
                technical_terms.append(self.abbreviations[clean_word])
        
        return list(set(technical_terms))
    
    def _extract_project_info(self, query: str) -> Dict[str, Any]:
        """Extract project-related information from the query."""
        project_info = {}
        
        # Project number patterns
        project_patterns = [
            r'project\s+(\d{3,6})',
            r'job\s+(\d{3,6})',
            r'(\d{6})',  # 6-digit project numbers
            r'(\d{3})\s*[-/]\s*(\d{3})',  # Year-project format
        ]
        
        for pattern in project_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                if len(match.groups()) == 1:
                    project_info['project_number'] = match.group(1)
                elif len(match.groups()) == 2:
                    project_info['year'] = match.group(1)
                    project_info['project_number'] = match.group(2)
                break
        
        # Client/location patterns
        location_match = re.search(r'(?:at|in|for)\s+([A-Za-z\s]+)', query, re.IGNORECASE)
        if location_match:
            project_info['location'] = location_match.group(1).strip()
        
        return project_info
    
    async def _generate_alternative_phrasings(self, query: str) -> List[str]:
        """Generate alternative phrasings using AI for better search coverage."""
        try:
            prompt = f"""Given this engineering query: "{query}"

Generate 3-5 alternative ways to phrase this same question that might help find relevant documents. Focus on:
- Engineering synonyms and technical variations
- Different ways engineers might describe the same concept
- Formal vs informal engineering language
- NZ/Australian vs international terminology

Return only the alternative phrasings, one per line, without numbering or explanation."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in engineering terminology. Generate alternative phrasings for engineering queries to improve search results."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            alternative_text = response.choices[0].message.content.strip()
            alternatives = [line.strip() for line in alternative_text.split('\n') if line.strip()]
            
            return alternatives[:5]  # Limit to 5 alternatives
            
        except Exception as e:
            logger.warning("Alternative phrasing generation failed", error=str(e))
            return []
    
    def _create_enhanced_query(self, base_query: str, technical_terms: List[str], alternatives: List[str]) -> str:
        """Create the final enhanced query for search."""
        # Start with the expanded base query
        enhanced = base_query
        
        # Add important technical terms with slight boost
        if technical_terms:
            # Add technical terms that aren't already in the query
            new_terms = [term for term in technical_terms if term.lower() not in enhanced.lower()]
            if new_terms:
                enhanced += " " + " ".join(new_terms[:3])  # Add up to 3 new technical terms
        
        return enhanced
    
    def _get_expanded_abbreviations(self, original_query: str) -> Dict[str, str]:
        """Get a mapping of abbreviations that were expanded."""
        expanded_abbrevs = {}
        words = original_query.lower().split()
        
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self.abbreviations:
                expanded_abbrevs[word] = self.abbreviations[clean_word]
        
        return expanded_abbrevs
    
    def enhance_query_for_category(self, query: str, category: str) -> str:
        """Enhance query based on specific document category."""
        enhanced = query
        
        # Category-specific enhancements
        if category == 'standards':
            if 'nzs' not in enhanced.lower():
                enhanced += " NZS standard"
                
        elif category == 'projects':
            if not re.search(r'\d{3,6}', enhanced):
                enhanced += " project"
                
        elif category == 'procedures':
            if 'how' not in enhanced.lower() and 'procedure' not in enhanced.lower():
                enhanced += " procedure how"
                
        elif category == 'policies':
            if 'policy' not in enhanced.lower():
                enhanced += " policy"
        
        return enhanced
