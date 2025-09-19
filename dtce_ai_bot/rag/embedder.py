"""
Embedding Generation Module

Handles vector embeddings for document chunks and queries.
"""

from typing import List, Dict, Any, Optional, Union
import asyncio
import logging
from openai import AzureOpenAI
import numpy as np

from .config import RAGConfig, ModelConfig
from .chunker import Chunk

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generate embeddings using Azure OpenAI
    """
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.model_config = config.models
        
        self.client = AzureOpenAI(
            api_key=config.azure.openai_api_key,
            api_version=config.azure.openai_api_version,
            azure_endpoint=config.azure.openai_endpoint
        )
        
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        try:
            # Clean and truncate text if needed
            cleaned_text = self._prepare_text(text)
            
            response = self.client.embeddings.create(
                input=cleaned_text,
                model=self.model_config.embedding_model
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return zero vector on error
            return [0.0] * self.model_config.embedding_dimensions
    
    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 16) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process per batch
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self._process_batch(batch)
            embeddings.extend(batch_embeddings)
            
        return embeddings
    
    def _process_batch(self, texts: List[str]) -> List[List[float]]:
        """Process a batch of texts"""
        try:
            # Clean all texts
            cleaned_texts = [self._prepare_text(text) for text in texts]
            
            response = self.client.embeddings.create(
                input=cleaned_texts,
                model=self.model_config.embedding_model
            )
            
            return [data.embedding for data in response.data]
            
        except Exception as e:
            logger.error(f"Error in batch embedding: {e}")
            # Return zero vectors for the batch
            return [[0.0] * self.model_config.embedding_dimensions] * len(texts)
    
    def embed_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Add embeddings to document chunks
        
        Args:
            chunks: List of chunks to embed
            
        Returns:
            Chunks with embeddings added to metadata
        """
        if not chunks:
            return chunks
            
        # Extract texts for embedding
        texts = [chunk.content for chunk in chunks]
        
        # Generate embeddings
        embeddings = self.generate_embeddings_batch(texts)
        
        # Add embeddings to chunk metadata
        for chunk, embedding in zip(chunks, embeddings):
            chunk.metadata['embedding'] = embedding
            chunk.metadata['embedding_model'] = self.model_config.embedding_model
            
        return chunks
    
    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for search query
        
        Args:
            query: Search query text
            
        Returns:
            Query embedding vector
        """
        return self.generate_embedding(query)
    
    def embed_queries(self, queries: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple queries
        
        Args:
            queries: List of query texts
            
        Returns:
            List of query embedding vectors
        """
        return self.generate_embeddings_batch(queries)
    
    def _prepare_text(self, text: str) -> str:
        """
        Prepare text for embedding
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned and truncated text
        """
        if not text or not text.strip():
            return ""
        
        # Remove excessive whitespace
        text = " ".join(text.split())
        
        # Truncate if too long (embedding models have token limits)
        # Rough estimate: 1 token ≈ 0.75 words
        max_words = int(8192 * 0.75)  # Conservative limit
        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words])
            logger.warning(f"Text truncated to {max_words} words for embedding")
        
        return text
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            similarity = dot_product / (norm1 * norm2)
            
            # Ensure result is between 0 and 1
            return max(0.0, min(1.0, (similarity + 1) / 2))
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def find_most_similar(self, query_embedding: List[float], 
                         candidate_embeddings: List[List[float]], 
                         top_k: int = 5) -> List[tuple]:
        """
        Find most similar embeddings to query
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embeddings
            top_k: Number of top results to return
            
        Returns:
            List of (index, similarity_score) tuples
        """
        similarities = []
        
        for i, candidate in enumerate(candidate_embeddings):
            similarity = self.calculate_similarity(query_embedding, candidate)
            similarities.append((i, similarity))
        
        # Sort by similarity (descending) and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
