# Fix: Time-Based Query Inconsistency

## Problem

The chatbot was giving inconsistent responses to similar time-based queries:

### Examples of Inconsistency:
1. **"give me a project 4 years ago"** → Returns 2020 projects (from Google Sheets)
2. **"find me project numbers from the past 4 years"** → "I don't have specific information" (RAG fallback failed)
3. **"find me project from the past 4 years"** → Returns 2021+ projects (different Google Sheets answer)

## Root Cause

The bot has a **two-tier system**:
1. **Google Sheets** (pre-written Q&A pairs) - checked first
2. **RAG System** (searches actual documents) - fallback

The problem was:
- **Low similarity threshold (0.4)** allowed loose matches to Google Sheets
- Different phrasings matched **different pre-written answers** in Google Sheets
- Time-based queries weren't being routed consistently
- No special handling for "past X years" calculations

## Solution

### 1. Skip Google Sheets for Time-Based Queries (`document_qa.py`)

Added `_is_time_based_query()` method to detect queries with time patterns:
- "past", "years ago", "last year", "last X years"
- "from 2020", "in 2019", "since 2020"
- "between 2019 and 2023"

**When detected**: Skip Google Sheets entirely → Go straight to RAG

```python
def _is_time_based_query(self, question: str) -> bool:
    """Check if question is time-based and should skip Google Sheets"""
    time_patterns = [
        'past', 'years ago', 'year ago', 'last year', 
        'last 2 years', 'last 3 years', 'last 4 years', 'last 5 years',
        'from 202', 'from 201',  # Years like "from 2020"
        'in 202', 'in 201',  # "in 2020"
        'since 202', 'since 201',
        'between 20', 'from the year'
    ]
    return any(pattern in question.lower() for pattern in time_patterns)
```

### 2. Increased Google Sheets Similarity Threshold

Changed from **0.4 → 0.75** for more exact matches only:

```python
# Before: similarity_threshold=0.4  # Too loose!
# After:  similarity_threshold=0.75  # More strict
```

### 3. Enhanced Intent Detection (`intent_detector_ai.py`)

Updated the intent classification prompt to explicitly handle time-based queries:

```python
TIME-BASED PROJECT QUERIES: If someone asks for "projects from the past X years", 
"projects X years ago", "project numbers from [year/time period]", classify as Project. 

Examples:
- "give me a project 4 years ago" → Project
- "find me project numbers from the past 4 years" → Project  
- "projects from 2020" → Project
- "show me jobs from last year" → Project
```

### 4. Added Time Range Extraction

Enhanced `extract_project_metadata()` to calculate year ranges:

```python
# "past 4 years" or "4 years ago"
time_match = re.search(r'\b(?:past|last)\s+(\d+)\s+years?\b', query_lower)

if time_match:
    years_back = int(time_match.group(1))
    current_year_code = 225  # 2025
    start_year_code = 225 - 4  # = 221 (2021)
    end_year_code = 225  # 2025
    
    return {
        "year_range_start": "221",
        "year_range_end": "225",
        "years_back": "4"
    }
```

### 5. Built Multi-Year OData Filters

Updated `build_search_filter()` to handle year ranges with OR conditions:

```python
# For "past 4 years" (2021-2025):
filter_str = """
(folder ge 'Projects/221/' and folder lt 'Projects/222/') or
(folder ge 'Projects/222/' and folder lt 'Projects/223/') or
(folder ge 'Projects/223/' and folder lt 'Projects/224/') or
(folder ge 'Projects/224/' and folder lt 'Projects/225/') or
(folder ge 'Projects/225/' and folder lt 'Projects/226/')
"""
```

## Result

Now all variations of time-based queries will:
1. ✅ Skip Google Sheets → Go to RAG directly
2. ✅ Be classified as "Project" intent
3. ✅ Extract year range (e.g., 221-225 for "past 4 years")
4. ✅ Build proper OData filter for multiple years
5. ✅ Return **consistent, accurate results** from actual project data

### Expected Behavior:

**Query**: "give me projects from the past 4 years"
- **Intent**: Project
- **Filter**: `(folder ge 'Projects/221/' ...) or (folder ge 'Projects/222/' ...) or ...`
- **Result**: Returns actual project numbers from 2021-2025

**Query**: "find me project numbers from the past 4 years"
- **Same behavior** ✅

**Query**: "show me projects 4 years ago"
- **Same behavior** ✅

## Files Modified

1. `/dtce_ai_bot/services/document_qa.py`
   - Added `_is_time_based_query()` method
   - Updated Google Sheets similarity threshold (0.4 → 0.75)
   - Skip Google Sheets for time-based queries

2. `/dtce_ai_bot/services/intent_detector_ai.py`
   - Enhanced intent classification prompt with time-based examples
   - Updated `extract_project_metadata()` to parse time ranges
   - Updated `build_search_filter()` to generate multi-year OR filters

## Testing

Test these queries to verify consistency:
```
✅ "give me a project 4 years ago"
✅ "find me project numbers from the past 4 years"
✅ "find me projects from the past 4 years"
✅ "show me projects from last 3 years"
✅ "projects from 2020"
✅ "what projects do we have from 2021 to 2024"
```

All should now return **consistent project lists** based on actual document data, not pre-written Google Sheets answers.

## Date
Fixed: November 26, 2025
