# Search Flow: Code Walkthrough

## Real Code Example: "what is project 225?"

Here's the ACTUAL code execution path with real values:

```python
# ============================================================================
# USER ASKS: "what is project 225?"
# ============================================================================

# Entry Point: rag_handler.py
result = await rag_handler.rag_orchestrator.process_question(
    question="what is project 225?",
    session_id="user-123"
)

# ============================================================================
# STEP 1: INTENT CLASSIFICATION
# File: intent_detector_ai.py, Line 61
# ============================================================================

async def classify_intent(user_query: str) -> str:
    classification_prompt = f"""
    Categories:
    - Policy, Procedure, Standards, Project, Client, General_Knowledge
    
    User Query: "what is project 225?"
    
    Output ONLY the category name.
    """
    
    response = await self.openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You classify queries into categories."},
            {"role": "user", "content": classification_prompt}
        ],
        temperature=0.1,
        max_tokens=50
    )
    
    intent = response.choices[0].message.content.strip()
    # Returns: "Project"
    
    return intent

# Result: intent = "Project"
# Time: ~0.3 seconds


# ============================================================================
# STEP 2: METADATA EXTRACTION
# File: intent_detector_ai.py, Line 117
# ============================================================================

def extract_project_metadata(user_query: str) -> Optional[Dict[str, str]]:
    query_lower = user_query.lower()  # "what is project 225?"
    
    # Pattern 1: Look for 6-digit job number (2\d{5})
    job_match = re.search(r'\b(2\d{5})\b', user_query)
    # Result: None (225 is only 3 digits)
    
    # Pattern 2: Look for 3-digit year code (2[0-9]{2})
    year_match = re.search(r'\b(2[0-9]{2})\b', user_query)
    # Result: MATCH! group(1) = "225"
    
    # Check if it's project-related
    if year_match and any(keyword in query_lower for keyword in ['project', 'job', 'what is']):
        year_code = year_match.group(1)  # "225"
        logger.info("Extracted year code", year_code=year_code)
        return {"year": year_code}
    
    return None

# Result: {"year": "225"}
# Time: <0.001 seconds (regex is instant)


# ============================================================================
# STEP 3: FILTER CONSTRUCTION
# File: intent_detector_ai.py, Line 155
# ============================================================================

def build_search_filter(intent: str, user_query: str) -> Optional[str]:
    category = self.CATEGORIES.get(intent)
    # category = {
    #     "description": "Past project information...",
    #     "folder_field": "folder",
    #     "folder_values": ["Projects"],
    #     "requires_extraction": True
    # }
    
    if intent == "Project":
        project_meta = self.extract_project_metadata(user_query)
        # project_meta = {"year": "225"}
        
        if project_meta and "year" in project_meta:
            year = project_meta["year"]  # "225"
            filter_str = f"search.ismatch('{year}*', 'folder,project_name', 'full', 'any')"
            # Result: "search.ismatch('225*', 'folder,project_name', 'full', 'any')"
            
            logger.info("Built year filter", filter=filter_str, year=year)
            return filter_str
    
    return None

# Result: "search.ismatch('225*', 'folder,project_name', 'full', 'any')"
# Time: <0.001 seconds


# ============================================================================
# STEP 4: GENERATE QUERY EMBEDDING
# File: azure_rag_service_v2.py, Line 196
# ============================================================================

async def _get_query_embedding(query: str) -> List[float]:
    response = await self.openai_client.embeddings.create(
        model="text-embedding-3-small",
        input="what is project 225?"
    )
    return response.data[0].embedding

# Result: [0.123, -0.456, 0.789, ..., 0.321]  # 1536 dimensions
# Time: ~0.2 seconds


# ============================================================================
# STEP 5: HYBRID SEARCH EXECUTION
# File: azure_rag_service_v2.py, Line 133
# ============================================================================

async def _hybrid_search_with_ranking(query: str, filter_str: str, top_k: int = 10):
    # Create vector query
    query_vector = await self._get_query_embedding(query)
    # query_vector = [0.123, -0.456, ..., 0.321]
    
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=10,
        fields="content_vector"
    )
    
    # Build search parameters
    search_params = {
        # KEYWORD SEARCH (BM25)
        "search_text": "what is project 225?",
        
        # VECTOR SEARCH (Semantic)
        "vector_queries": [vector_query],
        
        # SEMANTIC RANKING
        "query_type": "semantic",
        "semantic_configuration_name": "default",
        
        # INTENT-BASED FILTER (KEY PART!)
        "filter": "search.ismatch('225*', 'folder,project_name', 'full', 'any')",
        
        # FIELDS TO RETRIEVE
        "select": ["content", "filename", "folder", "project_name", "chunk_id"],
        
        # LIMIT
        "top": 10,
        "include_total_count": True
    }
    
    # Execute search
    search_results = self.search_client.search(**search_params)
    
    # Process results
    results = []
    for result in search_results:
        results.append({
            'content': result.get('content', ''),
            'filename': result.get('filename', 'Unknown'),
            'folder': result.get('folder', ''),
            'project_name': result.get('project_name', ''),
            'chunk_id': result.get('chunk_id', ''),
            'search_score': result.get('@search.score', 0),
            'reranker_score': result.get('@search.reranker_score', 0)
        })
    
    return results

# Result: [
#     {
#         'content': "Project 225221 is a commercial building...",
#         'filename': "225221_Project_Scope.pdf",
#         'folder': "Projects/225/225221",
#         'project_name': "Job 225221 (2025)",
#         'search_score': 8.5,
#         'reranker_score': 0.95
#     },
#     # ... 9 more results
# ]
# Time: ~0.5 seconds


# ============================================================================
# STEP 6: ANSWER SYNTHESIS
# File: azure_rag_service_v2.py, Line 215
# ============================================================================

async def _synthesize_answer(user_query: str, search_results: List[Dict], ...):
    # Build context from top 5 results
    context_chunks = []
    for i, result in enumerate(search_results[:5], 1):
        filename = result.get('filename', 'Unknown')
        folder = result.get('folder', '')
        content = result.get('content', '')
        
        chunk = f"[Source {i}: {filename} from {folder}]\n{content}"
        context_chunks.append(chunk)
    
    context = "\n\n".join(context_chunks)
    # context = """
    # [Source 1: 225221_Project_Scope.pdf from Projects/225/225221]
    # Project 225221 is a commercial building development...
    # 
    # [Source 2: 225189_Design_Brief.docx from Projects/225/225189]
    # Job 225189 involves residential development...
    # ...
    # """
    
    system_prompt = """You are an expert DTCE Assistant. 
    Answer using ONLY the provided context.
    Rules: Synthesize, Citations, Professional tone, Accurate."""
    
    user_prompt = f"""Context from DTCE Knowledge Base:
{context}

User Query: "what is project 225?"

Answer using ONLY the information from the context."""
    
    response = await self.openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=1500
    )
    
    answer = response.choices[0].message.content
    
    return answer

# Result: 
# """
# Project 225 refers to projects from the year 2025. Here are the active jobs:
# 
# **Job 225221** - Commercial building development in Wellington...
# **Job 225189** - Residential development in Auckland...
# 
# Sources:
# - 225221_Project_Scope.pdf (Projects/225/225221)
# - 225189_Design_Brief.docx (Projects/225/225189)
# """
# Time: ~1.5 seconds


# ============================================================================
# STEP 7: RETURN RESULT
# File: azure_rag_service_v2.py, Line 89
# ============================================================================

return {
    'answer': "Project 225 refers to projects from the year 2025...",
    'sources': [
        {
            'title': '225221_Project_Scope.pdf',
            'folder': 'Projects/225/225221',
            'project_name': 'Job 225221 (2025)',
            'relevance_score': 0.95,
            'excerpt': 'Project 225221 is a commercial building...'
        },
        # ... 4 more sources
    ],
    'intent': 'Project',
    'search_filter': "search.ismatch('225*', 'folder,project_name', 'full', 'any')",
    'total_documents': 10,
    'search_type': 'hybrid_rag_with_intent_routing'
}

# ============================================================================
# TOTAL TIME BREAKDOWN:
# ============================================================================
# Intent Classification:     ~0.3s (GPT-4o-mini)
# Metadata Extraction:       <0.001s (regex)
# Filter Construction:       <0.001s (string formatting)
# Query Embedding:           ~0.2s (text-embedding-3-small)
# Hybrid Search:             ~0.5s (Azure AI Search)
# Answer Synthesis:          ~1.5s (GPT-4o)
# ============================================================================
# TOTAL:                     ~2.5 seconds
# ============================================================================
```

---

## Key Code Locations

| Step | File | Function | Line |
|------|------|----------|------|
| 1. Intent Classification | `intent_detector_ai.py` | `classify_intent()` | 61 |
| 2. Metadata Extraction | `intent_detector_ai.py` | `extract_project_metadata()` | 117 |
| 3. Filter Building | `intent_detector_ai.py` | `build_search_filter()` | 155 |
| 4. Orchestration | `azure_rag_service_v2.py` | `process_query()` | 48 |
| 5. Hybrid Search | `azure_rag_service_v2.py` | `_hybrid_search_with_ranking()` | 108 |
| 6. Embedding | `azure_rag_service_v2.py` | `_get_query_embedding()` | 196 |
| 7. Answer Synthesis | `azure_rag_service_v2.py` | `_synthesize_answer()` | 215 |
| 8. Entry Point | `rag_handler.py` | `RAGHandler.__init__()` | 30 |

---

## What Makes This Different From Basic Search?

### Basic Search (No Intent Detection):
```python
# Just searches everything
results = search_client.search(search_text="what is project 225?", top=10)
# Problem: Returns "225mm beam depth" documents mixed with project docs
```

### Our Intent-Based Search:
```python
# Step 1: Understand what user wants
intent = "Project"

# Step 2: Build smart filter
filter = "search.ismatch('225*', 'folder,project_name', 'full', 'any')"

# Step 3: Search with filter
results = search_client.search(
    search_text="what is project 225?",
    filter=filter,  # <-- This is the magic!
    vector_queries=[...],
    query_type="semantic",
    top=10
)
# Result: ONLY returns project documents, ignores "225mm" in technical specs
```

The **filter parameter** is what prevents the "225mm beam depth" problem! 🎯
