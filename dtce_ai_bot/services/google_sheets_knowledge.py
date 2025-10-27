"""
Google Sheets Knowledge Service
Primary knowledge source that checks for Q&A pairs before falling back to RAG system
"""

import os
from typing import List, Dict, Any, Optional
import structlog
from difflib import SequenceMatcher
import json
import httpx

logger = structlog.get_logger(__name__)

class GoogleSheetsKnowledgeService:
    """Service to check Google Sheets for predefined Q&A pairs before using RAG"""
    
    def __init__(self, sheet_id: str = None, sheet_range: str = "Sheet1!A:B"):
        """
        Initialize Google Sheets service
        
        Args:
            sheet_id: Google Sheets ID (from environment or sharing URL)
            sheet_range: Range containing questions (A) and answers (B)
        """
        # Extract sheet ID from sharing URL or use direct ID
        self.sheet_id = self._extract_sheet_id(sheet_id or os.getenv('GOOGLE_SHEETS_ID') or os.getenv('GOOGLE_SHEETS_URL'))
        self.sheet_range = sheet_range
        
        # Default to your provided sheet ID if nothing is configured
        if not self.sheet_id:
            self.sheet_id = "1mMaMi7FAZDp2wic3M48av3nadXDl6R69H2X_6YQR2Gs"
            logger.info("Using default Google Sheets knowledge base")
        
        logger.info(f"Google Sheets service initialized with sheet ID: {self.sheet_id}")
        
        # Cache for storing Q&A pairs
        self._qa_cache = {}
        self._cache_timestamp = None
        self._cache_duration = 300  # 5 minutes cache
        
    async def find_similar_question(self, user_question: str, similarity_threshold: float = 0.7) -> Optional[Dict[str, Any]]:
        """
        Find similar question in Google Sheets knowledge base
        
        Args:
            user_question: User's question to match
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            Dict with 'question', 'answer', and 'similarity' if match found, None otherwise
        """
        try:
            if not self.sheet_id:
                logger.debug("Google Sheets not configured - skipping knowledge check")
                return None
            
            # Get Q&A pairs from sheets
            qa_pairs = await self._get_qa_pairs()
            
            if not qa_pairs:
                logger.debug("No Q&A pairs found in Google Sheets")
                return None
            
            # Find best matching question
            best_match = None
            best_similarity = 0.0
            
            for qa_pair in qa_pairs:
                question = qa_pair.get('question', '').strip()
                answer = qa_pair.get('answer', '').strip()
                
                if not question or not answer:
                    continue
                
                # Calculate similarity using multiple methods
                similarity = self._calculate_similarity(user_question.lower(), question.lower())
                
                # Debug logging for similarity scores
                logger.debug(f"Comparing '{user_question}' vs '{question}' = {similarity:.3f}")
                
                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_similarity = similarity
                    best_match = {
                        'question': question,
                        'answer': answer,
                        'similarity': similarity
                    }
            
            if best_match:
                logger.info("Found matching question in Google Sheets", 
                           similarity=best_match['similarity'],
                           matched_question=best_match['question'][:100])
            
            return best_match
            
        except Exception as e:
            logger.error("Error finding similar question in Google Sheets", error=str(e))
            return None
    
    async def _get_qa_pairs(self) -> List[Dict[str, str]]:
        """Fetch Q&A pairs from Google Sheets with caching (using public CSV export)"""
        try:
            import time
            current_time = time.time()
            
            # Check cache validity
            if (self._cache_timestamp and 
                current_time - self._cache_timestamp < self._cache_duration and 
                self._qa_cache):
                logger.debug("Using cached Google Sheets data")
                return self._qa_cache
            
            # Use public CSV export (no API key required)
            # Format: https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0
            url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/export?format=csv&gid=0"
            
            # Configure client to follow redirects
            async with httpx.AsyncClient(
                timeout=10.0, 
                follow_redirects=True,
                headers={'User-Agent': 'DTCE-AI-Bot/1.0'}
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Parse CSV data
                import csv
                import io
                
                csv_content = response.text
                csv_reader = csv.reader(io.StringIO(csv_content))
                rows = list(csv_reader)
                
                logger.debug(f"Raw CSV data: {len(rows)} rows")
                if rows:
                    logger.debug(f"First row (header): {rows[0]}")
                    if len(rows) > 1:
                        logger.debug(f"Second row (first data): {rows[1]}")
                
                qa_pairs = []
                for i, row in enumerate(rows):
                    # Skip header row
                    if i == 0:
                        continue
                        
                    if len(row) >= 2:
                        question = row[0].strip() if row[0] else ""
                        answer = row[1].strip() if row[1] else ""
                        
                        if question and answer:
                            qa_pairs.append({
                                'question': question,
                                'answer': answer
                            })
                
                # Update cache
                self._qa_cache = qa_pairs
                self._cache_timestamp = current_time
                
                logger.info(f"Loaded {len(qa_pairs)} Q&A pairs from Google Sheets")
                
                # Debug: Log first few Q&A pairs
                for i, qa in enumerate(qa_pairs[:3]):
                    logger.debug(f"Q&A {i+1}: Q='{qa['question'][:50]}...' A='{qa['answer'][:50]}...'")
                
                return qa_pairs
                
        except Exception as e:
            logger.error("Error fetching data from Google Sheets", error=str(e))
            return []
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts using AI embeddings and traditional methods
        
        Returns value between 0.0 and 1.0
        """
        try:
            # Normalize texts for comparison
            norm_text1 = text1.lower().strip()
            norm_text2 = text2.lower().strip()
            
            # Exact match gets highest score
            if norm_text1 == norm_text2:
                return 1.0
            
            # Method 1: AI Semantic Similarity using embeddings (primary method)
            semantic_similarity = 0.0
            try:
                # Use Azure OpenAI embeddings for semantic similarity
                from openai import AzureOpenAI
                import math
                
                # Initialize Azure OpenAI client if not already done
                if not hasattr(self, '_openai_client'):
                    from dtce_ai_bot.config.settings import get_settings
                    settings = get_settings()
                    self._openai_client = AzureOpenAI(
                        api_key=settings.azure_openai_api_key,
                        api_version=settings.azure_openai_api_version,
                        azure_endpoint=settings.azure_openai_endpoint
                    )
                
                # Get embeddings for both texts using the configured embedding model
                from dtce_ai_bot.config.settings import get_settings
                settings = get_settings()
                embedding_model = settings.azure_openai_embedding_model
                
                embedding1_response = self._openai_client.embeddings.create(
                    model=embedding_model,
                    input=text1
                )
                embedding2_response = self._openai_client.embeddings.create(
                    model=embedding_model, 
                    input=text2
                )
                
                embedding1 = embedding1_response.data[0].embedding
                embedding2 = embedding2_response.data[0].embedding
                
                # Calculate cosine similarity manually
                def cosine_similarity(vec1, vec2):
                    dot_product = sum(a * b for a, b in zip(vec1, vec2))
                    magnitude1 = math.sqrt(sum(a * a for a in vec1))
                    magnitude2 = math.sqrt(sum(a * a for a in vec2))
                    
                    if magnitude1 == 0 or magnitude2 == 0:
                        return 0.0
                    
                    return dot_product / (magnitude1 * magnitude2)
                
                semantic_similarity = cosine_similarity(embedding1, embedding2)
                
                # Ensure it's in valid range
                semantic_similarity = max(0.0, min(1.0, semantic_similarity))
                
                logger.debug("AI semantic similarity calculated", 
                           text1=text1[:50], text2=text2[:50], 
                           semantic_similarity=semantic_similarity)
                
            except Exception as embedding_error:
                logger.warning("AI embeddings failed, falling back to traditional methods", 
                             error=str(embedding_error))
                semantic_similarity = 0.0
            
            # Method 2: Sequence matching (fallback)
            seq_similarity = SequenceMatcher(None, norm_text1, norm_text2).ratio()
            
            # Method 3: Word overlap (Jaccard similarity)
            words1 = set(norm_text1.split())
            words2 = set(norm_text2.split())
            
            word_similarity = 0.0
            if words1 and words2:
                intersection = words1.intersection(words2)
                union = words1.union(words2)
                word_similarity = len(intersection) / len(union) if union else 0.0
            
            # Method 4: Substring matching
            substring_similarity = 0.0
            if norm_text1 in norm_text2 or norm_text2 in norm_text1:
                substring_similarity = 0.3
            
            # If AI embeddings worked, use them as primary with traditional methods as support
            if semantic_similarity > 0.0:
                combined_similarity = (
                    semantic_similarity * 0.7 +  # AI embeddings are primary
                    seq_similarity * 0.15 +      # Traditional methods as support
                    word_similarity * 0.1 +
                    substring_similarity * 0.05
                )
            else:
                # Fallback to traditional methods only
                combined_similarity = (
                    seq_similarity * 0.4 +
                    word_similarity * 0.4 +
                    substring_similarity * 0.2
                )
            
            return min(combined_similarity, 1.0)
            
        except Exception as e:
            logger.error("Error calculating similarity", error=str(e))
            return 0.0
    
    def _extract_sheet_id(self, sheet_input: str) -> Optional[str]:
        """
        Extract sheet ID from Google Sheets URL or return direct ID
        
        Args:
            sheet_input: Either a sharing URL or direct sheet ID
            
        Returns:
            Sheet ID if valid, None otherwise
        """
        if not sheet_input:
            return None
            
        # If it's already just an ID (no slashes), return as-is
        if '/' not in sheet_input:
            return sheet_input
            
        # Extract from sharing URL
        # Format: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit...
        try:
            if '/spreadsheets/d/' in sheet_input:
                parts = sheet_input.split('/spreadsheets/d/')
                if len(parts) > 1:
                    sheet_id = parts[1].split('/')[0]
                    return sheet_id
        except Exception as e:
            logger.error("Error extracting sheet ID from URL", error=str(e), url=sheet_input)
            
        return None

    async def add_qa_pair(self, question: str, answer: str) -> bool:
        """
        Add a new Q&A pair to the Google Sheets (read-only mode)
        
        Args:
            question: Question to add
            answer: Answer to add
            
        Returns:
            False (read-only mode)
        """
        logger.info("Q&A pair addition requested (read-only mode)", 
                   question=question[:50], answer=answer[:50])
        return False
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the current cache state"""
        import time
        return {
            'cached_pairs': len(self._qa_cache),
            'cache_timestamp': self._cache_timestamp,
            'cache_age_seconds': time.time() - self._cache_timestamp if self._cache_timestamp else None,
            'cache_valid': bool(self._cache_timestamp and 
                              time.time() - self._cache_timestamp < self._cache_duration)
        }
