# RAG Architecture V2: Intent-Based Routing with Hybrid Search

## Overview

This document describes the **production-ready RAG system** built for DTCE AI Bot, following industry best practices for retrieval-augmented generation.

## Architecture Diagram

```
User Query
    ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 1: Intent Classification (GPT-4o-mini)                      │
│ ─────────────────────────────────────────────────────────────────│
│ Classify into: Policy | Procedure | Standards | Project |       │
│                Client | General_Knowledge                         │
└──────────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 2: Dynamic Filter Construction                              │
│ ─────────────────────────────────────────────────────────────────│
│ • Extract metadata (job numbers, year codes, client names)       │
│ • Build OData filters for Azure AI Search                        │
│ • Example: "search.ismatch('225*', 'folder,project_name')"      │
└──────────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 3: Hybrid Search + Semantic Ranking (Azure AI Search)      │
│ ─────────────────────────────────────────────────────────────────│
│ • Vector Search (semantic similarity via embeddings)             │
│ • Keyword Search (BM25 for exact matches)                        │
│ • Semantic Ranking (L2 re-ranker)                                │
│ • Dynamic Filtering (intent-based folder routing)                │
└──────────────────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 4: Answer Synthesis (GPT-4o)                                │
│ ─────────────────────────────────────────────────────────────────│
│ • Synthesize: Combine information from multiple sources          │
│ • Citations: Provide source references                           │
│ • Constraints: Handle insufficient context gracefully            │
│ • Tone: Professional, conversational, accurate                   │
└──────────────────────────────────────────────────────────────────┘
    ↓
Answer + Sources + Metadata
```

---

## 1. Data Preparation & Index Schema

### Azure AI Search Index: `dtce-documents-index`

| Field Name       | Type              | Purpose                                      | Filterable | Searchable | Vector |
|------------------|-------------------|----------------------------------------------|------------|------------|--------|
| `content`        | String            | Document text (chunked)                      | ❌         | ✅         | ❌     |
| `content_vector` | Collection(Single)| Embedding vector (1536-dim)                  | ❌         | ❌         | ✅     |
| `filename`       | String            | Original file name                           | ❌         | ✅         | ❌     |
| `folder`         | String            | Top-level category (Policy, Projects, etc.)  | ✅         | ✅         | ❌     |
| `project_name`   | String            | Project identifier (e.g., "Job 225221")      | ✅         | ✅         | ❌     |
| `year`           | String            | Year code extracted from job number          | ✅         | ✅         | ❌     |
| `chunk_id`       | String (Key)      | Unique chunk identifier                      | ✅         | ❌         | ❌     |

### Metadata Enrichment During Indexing

**Project Reference Data:**
- Extract year code from job numbers (e.g., `225221` → year: `225`)
- Parse folder structure: `Projects/225/225221`
- Populate `project_name` field with "Job 225221 (2025)"

**Document Content:**
- Use Azure Form Recognizer to extract text from PDFs/DOCX
- Chunk documents into 1000-token segments with 200-token overlap
- Generate embeddings using `text-embedding-3-small`

---

## 2. Intent Detection & Classification

### Intent Categories

| Category          | Description                                                    | Example Queries                                        |
|-------------------|----------------------------------------------------------------|--------------------------------------------------------|
| **Policy**        | Company policies, H&S procedures, HR/IT rules                  | "what's the wellness policy?"                          |
| **Procedure**     | How-to guides, technical procedures, best practices            | "how do I use the wind spreadsheet?"                   |
| **Standards**     | NZ Engineering Standards (NZS, AS/NZS codes)                   | "what does NZS 3604 say about wind loads?"             |
| **Project**       | Past project information, job folders (requires job number)    | "what is project 225?", "tell me about job 225221"     |
| **Client**        | Client information, contact details, relationships             | "who is the client for job 225221?"                    |
| **General_Knowledge** | General engineering questions, company info             | "what is the maximum wind load on a commercial building?" |

### Classification Prompt (GPT-4o-mini)

```python
system_message = """You classify queries into knowledge categories. 
Output ONLY the category name, nothing else."""

user_message = f"""Goal: Classify the user's query into one of the following categories:
- Policy, Procedure, Standards, Project, Client, General_Knowledge

User Query: "{user_query}"

CRITICAL: When someone asks "project 225", they want PROJECT information, 
not technical measurements like "225mm beam depth"!

Output ONLY the category name."""
```

**Key Design Decisions:**
- ✅ **Fast & Cheap:** Uses GPT-4o-mini for sub-second classification
- ✅ **Simple Output:** Returns single category name (no JSON parsing complexity)
- ✅ **Clear Instructions:** Explicit guidance on ambiguous cases (e.g., "project 225" vs "225mm")

---

## 3. Dynamic Filter Construction

### Filter Building Logic

The system dynamically builds OData filters based on:
1. **Intent Category** (determines which folders to search)
2. **Extracted Metadata** (job numbers, year codes, client names)

### Examples

#### Policy Intent
```python
filter = "search.ismatch('Policies|Health and Safety|Company Documents', 'folder', 'full', 'any')"
```

#### Project Intent with Job Number
```python
# User: "what is project 225221?"
filter = "search.ismatch('225221', 'folder,project_name', 'full', 'any')"
```

#### Project Intent with Year Code
```python
# User: "what is project 225?"
filter = "search.ismatch('225*', 'folder,project_name', 'full', 'any')"
```

#### Client Intent
```python
# User: "who is the client for Smith Project?"
filter = "search.ismatch('Clients', 'folder', 'full', 'any') and search.ismatch('Smith', 'content,project_name', 'full', 'any')"
```

#### General Knowledge Intent
```python
# No filter applied - search entire index or use LLM's internal knowledge
filter = None
```

### Metadata Extraction

**Project Number Parsing:**
```python
# 6-digit job number (e.g., "225221")
job_match = re.search(r'\b(2\d{5})\b', user_query)
if job_match:
    job_number = job_match.group(1)  # "225221"
    year_code = job_number[:3]        # "225"

# 3-digit year code (e.g., "project 225")
year_match = re.search(r'\b(2[0-9]{2})\b', user_query)
if year_match and 'project' in user_query.lower():
    year_code = year_match.group(1)   # "225"
```

---

## 4. Hybrid Search + Semantic Ranking

### Search Components

#### 4.1 Vector Search (Semantic Similarity)
```python
query_vector = await get_query_embedding(query)  # 1536-dim vector
vector_query = VectorizedQuery(
    vector=query_vector,
    k_nearest_neighbors=10,
    fields="content_vector"
)
```

#### 4.2 Keyword Search (BM25)
```python
search_text = user_query  # Uses BM25 algorithm for exact matches
```

#### 4.3 Semantic Ranking (L2 Re-ranker)
```python
query_type = "semantic"
semantic_configuration_name = "default"
```

### Search Execution

```python
search_results = search_client.search(
    search_text=query,                    # Keyword search
    vector_queries=[vector_query],         # Vector search
    query_type="semantic",                 # Enable semantic ranking
    semantic_configuration_name="default", # Semantic config
    filter=filter_str,                     # Intent-based filter
    select=["content", "filename", "folder", "project_name"],
    top=10
)
```

**Retrieve Only Needed Fields:**
- ✅ Retrieve: `content`, `filename`, `folder`, `project_name`
- ❌ Don't Retrieve: `content_vector` (saves bandwidth)

---

## 5. Answer Synthesis (RAG Generation)

### System Prompt (GPT-4o)

```python
system_prompt = """You are an expert DTCE Assistant. Your primary function is to answer 
the user's question ONLY using the provided context from the company's knowledge base.

Rules:
1. Synthesize: Combine information from the retrieved document chunks into a single, 
   cohesive, and easy-to-read answer.
2. Citations: At the end of the answer, provide a list of sources using the filename 
   and folder metadata. Do not mention file names in the body of your answer.
3. Constraints: If the context is insufficient or contradictory, state: 
   "I cannot provide a complete answer based on the available DTCE knowledge."
4. Tone: Maintain a professional and helpful tone. Be conversational but not robotic - 
   answer like a knowledgeable colleague.
5. Accuracy: NEVER make up information. Only use what's in the provided context.
6. Clarity: Be specific with names, numbers, and details when they're in the documents.
"""
```

### User Prompt Structure

```python
user_prompt = f"""Context from DTCE Knowledge Base:
{context_from_top_5_results}

User Query: "{user_query}"

Please answer the user's question using ONLY the information from the provided context.
"""
```

### Temperature & Token Settings

```python
temperature = 0.3  # Slightly creative for natural language, mostly factual
max_tokens = 1500  # Sufficient for comprehensive answers
```

---

## 6. Code Structure

### File Organization

```
dtce_ai_bot/services/
├── intent_detector_ai.py           # Intent classification + filter building
├── azure_rag_service_v2.py         # Main RAG orchestration
├── rag_handler.py                  # Entry point (uses RAGOrchestrator)
└── project_parser.py               # Project number parsing utilities
```

### Class Hierarchy

```
RAGOrchestrator
    └── AzureRAGService
            ├── IntentDetector
            │   ├── classify_intent()
            │   ├── build_search_filter()
            │   ├── extract_project_metadata()
            │   └── extract_client_name()
            ├── _hybrid_search_with_ranking()
            ├── _get_query_embedding()
            └── _synthesize_answer()
```

---

## 7. Usage Example

### Python Code

```python
from dtce_ai_bot.services.rag_handler import RAGHandler

# Initialize handler
rag_handler = RAGHandler(search_client, openai_client, "gpt-4o")

# Process query
result = await rag_handler.rag_orchestrator.process_question(
    question="what is project 225?",
    session_id="user-123"
)

# Access results
print(result['answer'])        # Natural language answer
print(result['intent'])        # "Project"
print(result['search_filter']) # "search.ismatch('225*', ...)"
print(result['sources'])       # List of source documents
```

### Example Flow

**User Query:** "what is project 225?"

1. **Intent Classification:**
   - Intent: `Project`
   - Confidence: High

2. **Filter Construction:**
   - Extracted year code: `225`
   - Filter: `search.ismatch('225*', 'folder,project_name', 'full', 'any')`

3. **Hybrid Search:**
   - Vector search finds semantically similar project documents
   - Keyword search finds exact "225" matches
   - Semantic ranking prioritizes most relevant chunks
   - Results filtered to `Projects/225/*` folders only

4. **Answer Synthesis:**
   - Combines information from top 5 project documents
   - Generates natural response: "Project 225 refers to projects from 2025. Here are the active jobs: 225221 (Commercial Building - Wellington), 225189 (Residential Development - Auckland)..."
   - Provides source citations

---

## 8. Key Benefits

### 🎯 Accuracy
- **No hallucinations:** Answers ONLY from company documents
- **Proper routing:** "project 225" returns project info, not "225mm beam depth"
- **Semantic understanding:** Finds relevant documents even with different wording

### ⚡ Performance
- **Fast classification:** GPT-4o-mini responds in <1 second
- **Efficient search:** Hybrid search leverages both semantic and keyword strengths
- **Smart filtering:** Reduces search space with intent-based folder filtering

### 🔧 Maintainability
- **Clear separation:** Intent detection → Filter building → Search → Generation
- **Easy to extend:** Add new categories by updating `CATEGORIES` dict
- **Debuggable:** Extensive logging at each pipeline step

### 📊 Scalability
- **No custom reranking:** Uses Azure's built-in semantic ranking (no extra LLM calls)
- **Stateless design:** Can scale horizontally
- **Efficient retrieval:** Returns only needed fields

---

## 9. Future Enhancements

### Near-Term
- [ ] **Named Entity Recognition (NER):** Better client name extraction
- [ ] **Confidence Thresholds:** Fallback to General_Knowledge for low-confidence classifications
- [ ] **Multi-Intent Queries:** Handle queries spanning multiple categories

### Long-Term
- [ ] **Fine-tuned Intent Classifier:** Train custom model for DTCE-specific intents
- [ ] **Query Decomposition:** Break complex queries into sub-queries
- [ ] **Contextual Embeddings:** Generate embeddings with query context for better retrieval

---

## 10. Testing Strategy

### Unit Tests
- Intent classification accuracy (labeled dataset)
- Filter construction correctness
- Metadata extraction precision

### Integration Tests
- End-to-end RAG pipeline
- Search result relevance
- Answer quality assessment

### Production Monitoring
- Intent distribution metrics
- Search result counts per intent
- Answer generation latency
- User feedback signals

---

## Conclusion

This RAG V2 architecture provides a **production-ready, scalable, and maintainable** solution for DTCE AI Bot. By combining intent-based routing with hybrid search and semantic ranking, we achieve:

✅ **Accurate retrieval** (right documents from right folders)  
✅ **Fast responses** (sub-2-second end-to-end)  
✅ **Natural answers** (conversational, citation-backed)  
✅ **Easy maintenance** (clear architecture, good logging)

The system is ready for deployment and can handle the full 100,000+ document corpus with proper indexing.
