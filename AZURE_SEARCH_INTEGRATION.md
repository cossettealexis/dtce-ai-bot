"""
Azure Search Integration Explanation

This document explains how the modular RAG system integrates with your Azure Search index.
"""

# ===========================
# AZURE SEARCH INTEGRATION
# ===========================

"""
CONFIGURATION (config.py):
The system reads your Azure Search credentials from environment variables:

- AZURE_SEARCH_SERVICE_NAME  → your-search-service
- AZURE_SEARCH_ADMIN_KEY     → your-admin-key  
- AZURE_SEARCH_INDEX_NAME    → dtce-docs (or your index name)
- AZURE_OPENAI_ENDPOINT      → https://your-openai.openai.azure.com/
- AZURE_OPENAI_API_KEY       → your-openai-key

These connect to YOUR existing Azure resources.
"""

# ===========================
# INDEX MANAGEMENT (indexer.py)
# ===========================

"""
INDEX CREATION/MANAGEMENT:
The SearchIndexer class manages YOUR Azure Search index:

1. CONNECTS to your Azure Search service using your credentials
2. CREATES/UPDATES the index schema with these fields:
   - chunk_id (unique identifier)
   - content (searchable text)
   - content_vector (1536-dim embeddings for vector search)
   - metadata (document metadata like title, type, etc.)
   - Various filterable fields (document_type, standard_code, etc.)

3. CONFIGURES vector search with HNSW algorithm
4. SETS UP semantic search capabilities
5. INDEXES your documents as chunks with embeddings

The indexer USES YOUR EXISTING Azure Search service - it doesn't create a new one.
"""

# ===========================
# DOCUMENT INGESTION FLOW
# ===========================

"""
WHEN YOU INGEST DOCUMENTS:

1. DocumentChunker breaks your documents into semantic chunks
2. EmbeddingGenerator creates vectors using YOUR Azure OpenAI service
3. SearchIndexer uploads chunks + embeddings to YOUR Azure Search index

Example:
pipeline.ingest_document(content, metadata)
↓
Chunks document → Generates embeddings → Stores in YOUR Azure Search index
"""

# ===========================
# SEARCH/RETRIEVAL FLOW  
# ===========================

"""
WHEN YOU ASK QUESTIONS:

1. HybridRetriever takes your question
2. Generates embedding for the question using YOUR Azure OpenAI
3. Performs HYBRID SEARCH on YOUR Azure Search index:
   
   VECTOR SEARCH:
   - Uses Azure Search's vector search capabilities
   - Searches the "content_vector" field 
   - Finds semantically similar chunks
   
   KEYWORD SEARCH:
   - Uses Azure Search's full-text search
   - Searches the "content" field
   - Finds exact keyword matches
   
4. Combines and re-ranks results
5. Returns top relevant chunks FROM YOUR INDEX

Example Azure Search Query (Vector):
search_client.search(
    search_text=None,
    vector_queries=[VectorizedQuery(vector=query_embedding, fields="content_vector")],
    select=["content", "metadata", "chunk_id"]
)

Example Azure Search Query (Keyword):
search_client.search(
    search_text="fire safety requirements",
    select=["content", "metadata", "chunk_id"]
)
"""

# ===========================
# ANSWER GENERATION FLOW
# ===========================

"""
WHEN GENERATING ANSWERS:

1. Takes relevant chunks retrieved FROM YOUR Azure Search index
2. Builds context from the retrieved content
3. Sends to YOUR Azure OpenAI service for answer generation
4. Returns answer with source citations

The answer is generated using:
- Context from YOUR Azure Search index
- YOUR Azure OpenAI models
- Proper source attribution
"""

# ===========================
# KEY INTEGRATION POINTS
# ===========================

"""
YOUR AZURE SERVICES USED:

1. AZURE SEARCH SERVICE:
   - Stores document chunks and embeddings
   - Performs vector + keyword search
   - Handles filtering and faceting
   - Provides semantic ranking

2. AZURE OPENAI SERVICE:
   - Generates embeddings (text-embedding-ada-002)
   - Generates answers (GPT-4)
   - Processes queries and responses

3. YOUR EXISTING INDEX:
   - Can work with existing index if schema matches
   - Or creates new index with proper schema
   - Stores your domain-specific documents
"""

# ===========================
# EXAMPLE: COMPLETE FLOW
# ===========================

"""
COMPLETE EXAMPLE:

1. You have Azure Search service: "my-dtce-search"
2. You have Azure OpenAI service: "my-dtce-openai"
3. You set environment variables pointing to YOUR services
4. You run:

   pipeline = RAGPipeline()
   pipeline.initialize()  # Connects to YOUR Azure Search
   
   # Ingest YOUR documents
   pipeline.ingest_document(content, metadata)  # Stores in YOUR index
   
   # Ask questions
   response = pipeline.answer_question("What are fire safety requirements?")
   # ↓ Searches YOUR index → Retrieves YOUR content → Generates answer

The system is a CLIENT that uses YOUR Azure services, not a replacement for them.
"""

# ===========================
# CHECKING YOUR INDEX
# ===========================

"""
VERIFY INTEGRATION:

# Check if your index exists and has documents
status = pipeline.get_system_status()
print(status['index_stats'])

# Search your index directly  
documents = pipeline.search_documents("*", top=10)
print(f"Found {len(documents)} documents in your index")

# Get index statistics
stats = pipeline.indexer.get_index_stats()
print(f"Index: {stats['index_name']}")
print(f"Documents: {stats['document_count']}")
"""
