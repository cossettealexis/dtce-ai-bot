"""
Document Chunking Module

Strategic document chunking with semantic boundaries.
"""

from typing import List, Dict, Any, Optional
import re
import tiktoken
from dataclasses import dataclass

from .config import ChunkingConfig


@dataclass
class Chunk:
    """Represents a document chunk with metadata"""
    content: str
    metadata: Dict[str, Any]
    chunk_id: str
    start_char: int
    end_char: int
    token_count: int


class DocumentChunker:
    """
    Document chunking with semantic boundary respect
    """
    
    def __init__(self, config: ChunkingConfig):
        self.config = config
        self.encoding = tiktoken.get_encoding("cl100k_base")
        
    def chunk_document(self, content: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        Chunk document content into semantic chunks
        
        Args:
            content: Document content to chunk
            metadata: Document metadata to inherit
            
        Returns:
            List of document chunks
        """
        if not content.strip():
            return []
        
        metadata = metadata or {}
        
        # Clean and normalize content
        content = self._normalize_content(content)
        
        # Split into paragraphs first if enabled
        if self.config.respect_paragraph_boundaries:
            paragraphs = self._split_paragraphs(content)
            chunks = []
            for para in paragraphs:
                chunks.extend(self._chunk_text(para, metadata))
        else:
            chunks = self._chunk_text(content, metadata)
            
        return self._post_process_chunks(chunks)
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content for consistent chunking"""
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        # Normalize quotes and dashes
        content = content.replace('"', '"').replace('"', '"')
        content = content.replace(''', "'").replace(''', "'")
        content = content.replace('—', '-').replace('–', '-')
        
        return content.strip()
    
    def _split_paragraphs(self, content: str) -> List[str]:
        """Split content into paragraphs"""
        paragraphs = re.split(r'\n\s*\n', content)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _chunk_text(self, text: str, base_metadata: Dict[str, Any]) -> List[Chunk]:
        """
        Chunk text with overlapping windows
        """
        chunks = []
        
        if self.config.respect_sentence_boundaries:
            sentences = self._split_sentences(text)
            chunks = self._chunk_by_sentences(sentences, base_metadata)
        else:
            chunks = self._chunk_by_tokens(text, base_metadata)
            
        return chunks
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Improved sentence splitting pattern
        sentence_pattern = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\!|\?)\s+'
        sentences = re.split(sentence_pattern, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _chunk_by_sentences(self, sentences: List[str], base_metadata: Dict[str, Any]) -> List[Chunk]:
        """Chunk by grouping sentences"""
        chunks = []
        current_chunk = []
        current_tokens = 0
        start_char = 0
        
        for sentence in sentences:
            sentence_tokens = len(self.encoding.encode(sentence))
            
            # Check if adding this sentence exceeds chunk size
            if (current_tokens + sentence_tokens > self.config.chunk_size and 
                current_chunk and 
                current_tokens >= self.config.min_chunk_size):
                
                # Create chunk from current sentences
                chunk_content = ' '.join(current_chunk)
                chunk = self._create_chunk(
                    content=chunk_content,
                    metadata=base_metadata,
                    start_char=start_char,
                    token_count=current_tokens
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(current_chunk)
                current_chunk = overlap_sentences + [sentence]
                current_tokens = len(self.encoding.encode(' '.join(current_chunk)))
                start_char = start_char + len(' '.join(current_chunk[:len(current_chunk)-len(overlap_sentences)-1])) + 1
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        # Add final chunk
        if current_chunk and current_tokens >= self.config.min_chunk_size:
            chunk_content = ' '.join(current_chunk)
            chunk = self._create_chunk(
                content=chunk_content,
                metadata=base_metadata,
                start_char=start_char,
                token_count=current_tokens
            )
            chunks.append(chunk)
            
        return chunks
    
    def _chunk_by_tokens(self, text: str, base_metadata: Dict[str, Any]) -> List[Chunk]:
        """Chunk by token count with character-based overlap"""
        chunks = []
        tokens = self.encoding.encode(text)
        
        start_idx = 0
        while start_idx < len(tokens):
            end_idx = min(start_idx + self.config.chunk_size, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_content = self.encoding.decode(chunk_tokens)
            
            chunk = self._create_chunk(
                content=chunk_content,
                metadata=base_metadata,
                start_char=start_idx,  # Approximate
                token_count=len(chunk_tokens)
            )
            chunks.append(chunk)
            
            # Move start position accounting for overlap
            start_idx = end_idx - self.config.overlap_size
            if start_idx >= end_idx:
                break
                
        return chunks
    
    def _get_overlap_sentences(self, sentences: List[str]) -> List[str]:
        """Get sentences for overlap based on token count"""
        if not sentences:
            return []
            
        overlap_sentences = []
        overlap_tokens = 0
        
        # Work backwards to get recent sentences for overlap
        for sentence in reversed(sentences):
            sentence_tokens = len(self.encoding.encode(sentence))
            if overlap_tokens + sentence_tokens <= self.config.overlap_size:
                overlap_sentences.insert(0, sentence)
                overlap_tokens += sentence_tokens
            else:
                break
                
        return overlap_sentences
    
    def _create_chunk(self, content: str, metadata: Dict[str, Any], 
                     start_char: int, token_count: int) -> Chunk:
        """Create a chunk object with metadata"""
        chunk_metadata = metadata.copy()
        chunk_metadata.update({
            'chunk_length': len(content),
            'token_count': token_count,
            'chunk_method': 'semantic' if self.config.respect_sentence_boundaries else 'token'
        })
        
        chunk_id = f"{metadata.get('document_id', 'unknown')}_{start_char}_{start_char + len(content)}"
        
        return Chunk(
            content=content,
            metadata=chunk_metadata,
            chunk_id=chunk_id,
            start_char=start_char,
            end_char=start_char + len(content),
            token_count=token_count
        )
    
    def _post_process_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """Post-process chunks for quality"""
        processed_chunks = []
        
        for chunk in chunks:
            # Skip chunks that are too small
            if chunk.token_count < self.config.min_chunk_size:
                continue
                
            # Truncate chunks that are too large
            if chunk.token_count > self.config.max_chunk_size:
                tokens = self.encoding.encode(chunk.content)
                truncated_tokens = tokens[:self.config.max_chunk_size]
                chunk.content = self.encoding.decode(truncated_tokens)
                chunk.token_count = len(truncated_tokens)
                chunk.end_char = chunk.start_char + len(chunk.content)
                
            processed_chunks.append(chunk)
            
        return processed_chunks
