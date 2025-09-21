"""
Document Processing and Indexing System
Handles document chunking, embedding generation, and Azure AI Search indexing
"""

import asyncio
import hashlib
import json
from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass, asdict
from pathlib import Path
import structlog
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, VectorSearch,
    VectorSearchProfile, HnswAlgorithmConfiguration, SemanticConfiguration,
    SemanticPrioritizedFields, SemanticField, SemanticSearch
)
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


@dataclass
class DocumentChunk:
    """Represents a document chunk ready for indexing"""
    id: str
    content: str
    title: str
    source: str
    chunk_index: int
    metadata: Dict[str, Any]
    content_vector: Optional[List[float]] = None
    
    def to_search_doc(self) -> Dict[str, Any]:
        """Convert to Azure Search document format"""
        return {
            "id": self.id,
            "content": self.content,
            "title": self.title,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "metadata": json.dumps(self.metadata),
            "content_vector": self.content_vector
        }


class DocumentProcessor:
    """Handles document parsing, chunking, and embedding generation"""
    
    def __init__(self, openai_client: AsyncAzureOpenAI, embedding_model: str = "text-embedding-ada-002"):
        self.openai_client = openai_client
        self.embedding_model = embedding_model
    
    async def process_document(self, 
                             content: str, 
                             title: str, 
                             source: str, 
                             metadata: Optional[Dict] = None) -> List[DocumentChunk]:
        """Process a single document into searchable chunks"""
        try:
            logger.info("Processing document", title=title, source=source)
            
            if metadata is None:
                metadata = {}
            
            # Chunk the document
            chunks = self._chunk_document(content, title, source, metadata)
            
            # Generate embeddings for each chunk
            for chunk in chunks:
                chunk.content_vector = await self._generate_embedding(chunk.content)
            
            logger.info("Document processed", 
                       title=title, 
                       chunks_created=len(chunks))
            
            return chunks
            
        except Exception as e:
            logger.error("Document processing failed", 
                        error=str(e), 
                        title=title, 
                        source=source)
            raise
    
    def _chunk_document(self, 
                       content: str, 
                       title: str, 
                       source: str, 
                       metadata: Dict,
                       max_chunk_size: int = 1000,
                       overlap: int = 200) -> List[DocumentChunk]:
        """Split document into overlapping chunks"""
        
        # Clean and prepare content
        content = content.strip()
        if not content:
            return []
        
        chunks = []
        sentences = self._split_into_sentences(content)
        
        current_chunk = ""
        current_size = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # If adding this sentence would exceed max size, create a chunk
            if current_size + sentence_size > max_chunk_size and current_chunk:
                # Create chunk
                chunk_id = self._generate_chunk_id(title, source, chunk_index)
                chunk = DocumentChunk(
                    id=chunk_id,
                    content=current_chunk.strip(),
                    title=title,
                    source=source,
                    chunk_index=chunk_index,
                    metadata=metadata.copy()
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk, overlap)
                current_chunk = overlap_text + " " + sentence
                current_size = len(current_chunk)
                chunk_index += 1
            else:
                # Add sentence to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_size += sentence_size
        
        # Add final chunk if any content remains
        if current_chunk.strip():
            chunk_id = self._generate_chunk_id(title, source, chunk_index)
            chunk = DocumentChunk(
                id=chunk_id,
                content=current_chunk.strip(),
                title=title,
                source=source,
                chunk_index=chunk_index,
                metadata=metadata.copy()
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences with simple sentence boundary detection"""
        import re
        
        # Simple sentence splitting on periods, exclamation marks, and question marks
        sentences = re.split(r'[.!?]+', text)
        
        # Clean and filter sentences
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:  # Skip very short sentences
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    def _get_overlap_text(self, text: str, overlap_size: int) -> str:
        """Get the last 'overlap_size' characters from text for overlap"""
        if len(text) <= overlap_size:
            return text
        
        # Try to find a word boundary for cleaner overlap
        overlap_text = text[-overlap_size:]
        space_index = overlap_text.find(' ')
        if space_index > 0:
            return overlap_text[space_index + 1:]
        
        return overlap_text
    
    def _generate_chunk_id(self, title: str, source: str, chunk_index: int) -> str:
        """Generate unique ID for document chunk"""
        # Create a hash based on title, source, and chunk index
        content_string = f"{title}_{source}_{chunk_index}"
        hash_object = hashlib.md5(content_string.encode())
        return hash_object.hexdigest()
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Azure OpenAI"""
        try:
            response = await self.openai_client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e), text_length=len(text))
            raise


class IndexManager:
    """Manages Azure AI Search index creation and document indexing"""
    
    def __init__(self, search_endpoint: str, search_key: str, index_name: str):
        self.search_endpoint = search_endpoint
        self.search_key = search_key
        self.index_name = index_name
        self.index_client = SearchIndexClient(
            endpoint=search_endpoint,
            credential=search_key
        )
        self.search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=search_key
        )
    
    async def create_index(self, embedding_dimensions: int = 1536) -> bool:
        """Create Azure AI Search index with vector and semantic search capabilities"""
        try:
            logger.info("Creating search index", index_name=self.index_name)
            
            # Define fields
            fields = [
                SearchField(name="id", type=SearchFieldDataType.String, key=True, sortable=True),
                SearchField(name="content", type=SearchFieldDataType.String, searchable=True, retrievable=True),
                SearchField(name="title", type=SearchFieldDataType.String, searchable=True, retrievable=True, sortable=True),
                SearchField(name="source", type=SearchFieldDataType.String, filterable=True, retrievable=True, sortable=True),
                SearchField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, retrievable=True, sortable=True),
                SearchField(name="metadata", type=SearchFieldDataType.String, retrievable=True),
                SearchField(
                    name="content_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=embedding_dimensions,
                    vector_search_profile_name="my-vector-config"
                )
            ]
            
            # Configure vector search
            vector_search = VectorSearch(
                profiles=[
                    VectorSearchProfile(
                        name="my-vector-config",
                        algorithm_configuration_name="my-hnsw"
                    )
                ],
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="my-hnsw",
                        parameters={
                            "m": 4,
                            "efConstruction": 400,
                            "efSearch": 500,
                            "metric": "cosine"
                        }
                    )
                ]
            )
            
            # Configure semantic search
            semantic_config = SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    keywords_fields=[SemanticField(field_name="source")],
                    content_fields=[SemanticField(field_name="content")]
                )
            )
            
            semantic_search = SemanticSearch(configurations=[semantic_config])
            
            # Create index
            index = SearchIndex(
                name=self.index_name,
                fields=fields,
                vector_search=vector_search,
                semantic_search=semantic_search
            )
            
            result = self.index_client.create_or_update_index(index)
            logger.info("Index created successfully", index_name=self.index_name)
            return True
            
        except Exception as e:
            logger.error("Index creation failed", error=str(e), index_name=self.index_name)
            return False
    
    async def index_documents(self, chunks: List[DocumentChunk], batch_size: int = 100) -> Dict[str, Any]:
        """Index document chunks in batches"""
        try:
            logger.info("Starting document indexing", 
                       total_chunks=len(chunks), 
                       batch_size=batch_size)
            
            # Convert chunks to search documents
            search_docs = [chunk.to_search_doc() for chunk in chunks]
            
            # Index in batches
            indexed_count = 0
            failed_count = 0
            
            for i in range(0, len(search_docs), batch_size):
                batch = search_docs[i:i + batch_size]
                
                try:
                    result = self.search_client.upload_documents(documents=batch)
                    
                    # Check results
                    for item in result:
                        if item.succeeded:
                            indexed_count += 1
                        else:
                            failed_count += 1
                            logger.warning("Document indexing failed", 
                                         document_id=item.key, 
                                         error=item.error_message)
                    
                    logger.info("Batch indexed", 
                               batch_number=i // batch_size + 1,
                               batch_size=len(batch),
                               indexed_in_batch=sum(1 for item in result if item.succeeded))
                    
                except Exception as e:
                    logger.error("Batch indexing failed", 
                               batch_number=i // batch_size + 1, 
                               error=str(e))
                    failed_count += len(batch)
            
            logger.info("Document indexing completed", 
                       indexed_count=indexed_count, 
                       failed_count=failed_count)
            
            return {
                "indexed_count": indexed_count,
                "failed_count": failed_count,
                "total_processed": len(chunks),
                "success_rate": indexed_count / len(chunks) if chunks else 0
            }
            
        except Exception as e:
            logger.error("Document indexing failed", error=str(e))
            raise
    
    async def delete_all_documents(self) -> bool:
        """Delete all documents from the index"""
        try:
            # Search for all documents
            results = self.search_client.search(search_text="*", select=["id"])
            
            # Collect all document IDs
            doc_ids = [{"id": result["id"]} for result in results]
            
            if doc_ids:
                # Delete documents
                result = self.search_client.delete_documents(documents=doc_ids)
                logger.info("Documents deleted", count=len(doc_ids))
                return True
            else:
                logger.info("No documents to delete")
                return True
                
        except Exception as e:
            logger.error("Failed to delete documents", error=str(e))
            return False
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        try:
            # Get document count
            results = self.search_client.search(search_text="*", include_total_count=True, top=0)
            doc_count = results.get_count()
            
            # Get index info
            index_info = self.index_client.get_index(self.index_name)
            
            return {
                "index_name": self.index_name,
                "document_count": doc_count,
                "fields_count": len(index_info.fields),
                "has_vector_search": index_info.vector_search is not None,
                "has_semantic_search": index_info.semantic_search is not None
            }
            
        except Exception as e:
            logger.error("Failed to get index stats", error=str(e))
            return {"error": str(e)}


class DataIngestionPipeline:
    """Complete data ingestion pipeline for RAG system"""
    
    def __init__(self, 
                 openai_client: AsyncAzureOpenAI,
                 index_manager: IndexManager,
                 embedding_model: str = "text-embedding-ada-002"):
        self.processor = DocumentProcessor(openai_client, embedding_model)
        self.index_manager = index_manager
    
    async def ingest_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ingest multiple documents into the RAG system
        
        Args:
            documents: List of dicts with keys: content, title, source, metadata (optional)
        """
        try:
            logger.info("Starting document ingestion", document_count=len(documents))
            
            all_chunks = []
            processed_docs = 0
            failed_docs = 0
            
            # Process each document
            for doc in documents:
                try:
                    chunks = await self.processor.process_document(
                        content=doc["content"],
                        title=doc["title"],
                        source=doc["source"],
                        metadata=doc.get("metadata", {})
                    )
                    all_chunks.extend(chunks)
                    processed_docs += 1
                    
                except Exception as e:
                    logger.error("Document processing failed", 
                               title=doc.get("title", "unknown"),
                               error=str(e))
                    failed_docs += 1
            
            # Index all chunks
            if all_chunks:
                index_result = await self.index_manager.index_documents(all_chunks)
            else:
                index_result = {"indexed_count": 0, "failed_count": 0}
            
            logger.info("Document ingestion completed",
                       processed_docs=processed_docs,
                       failed_docs=failed_docs,
                       total_chunks=len(all_chunks),
                       indexed_chunks=index_result["indexed_count"])
            
            return {
                "processed_documents": processed_docs,
                "failed_documents": failed_docs,
                "total_chunks_created": len(all_chunks),
                "indexed_chunks": index_result["indexed_count"],
                "failed_chunks": index_result["failed_count"],
                "success": processed_docs > 0 and index_result["indexed_count"] > 0
            }
            
        except Exception as e:
            logger.error("Document ingestion pipeline failed", error=str(e))
            raise
