"""
Intent Detection Service
Classifies user queries into categories to route to appropriate document folders
"""
import re
from typing import Optional, Dict
from enum import Enum


class QueryIntent(Enum):
    """Query intent categories"""
    POLICY = "policy"  # H&S, IT policies, employee rules
    PROCEDURE = "procedure"  # H2H (How to Handbooks), best practices
    STANDARD = "standard"  # NZ Engineering Standards, codes
    PROJECT = "project"  # Past project information
    CLIENT = "client"  # Client details, contact info
    GENERAL = "general"  # Default: search everything


class IntentDetector:
    """
    Detects user intent to route queries to appropriate document folders
    """
    
    # Keywords for each intent
    INTENT_PATTERNS = {
        QueryIntent.POLICY: {
            'keywords': [
                'policy', 'policies', 'h&s', 'health and safety', 'safety',
                'hr', 'human resources', 'it policy', 'employee', 'staff',
                'must', 'required', 'rule', 'regulation', 'compliance',
                'wellbeing', 'wellness', 'leave', 'sick leave', 'annual leave',
                'disciplinary', 'harassment', 'bullying', 'alcohol', 'drugs'
            ],
            'folders': ['Company Documents', 'Policies', 'H&S', 'IT', 'HR']
        },
        
        QueryIntent.PROCEDURE: {
            'keywords': [
                'how to', 'how do i', 'procedure', 'process', 'h2h',
                'handbook', 'guide', 'steps', 'instructions', 'tutorial',
                'best practice', 'workflow', 'spreadsheet', 'template',
                'use', 'operate', 'setup', 'configure'
            ],
            'folders': ['Procedures', 'Technical Library', 'Admin', 'Engineering']
        },
        
        QueryIntent.STANDARD: {
            'keywords': [
                'nzs', 'nz standard', 'code', 'standard', 'specification',
                'as/nzs', 'compliance', 'building code', 'structural code',
                'seismic', 'wind load', 'snow load', 'design code',
                'nzs 3604', 'nzs 1170', 'nzs 3101', 'eurocode'
            ],
            'folders': ['Standards', 'NZ Standards', 'Engineering Standards']
        },
        
        QueryIntent.PROJECT: {
            'keywords': [
                'project', 'job', 'past project', 'previous project',
                'what was', 'tell me about project', 'show me project',
                'project details', 'project info', 'job number'
            ],
            'patterns': [
                r'\bproject\s+\d{3,6}\b',  # "project 225" or "project 225221"
                r'\bjob\s+\d{3,6}\b',       # "job 225221"
                r'\b(2[0-9]{2}\d{3})\b',    # 6-digit job number "225221"
                r'\bwhat\s+is\s+\d{3}\b',   # "what is 225"
            ],
            'folders': ['Projects', 'Clients/*/Jobs']
        },
        
        QueryIntent.CLIENT: {
            'keywords': [
                'client', 'customer', 'contact', 'phone', 'email',
                'address', 'past clients', 'who is', 'client name',
                'client details', 'contact details', 'company contact'
            ],
            'folders': ['Clients']
        }
    }
    
    def detect_intent(self, query: str) -> Dict:
        """
        Detect the intent of a user query.
        
        Returns:
            {
                'intent': QueryIntent,
                'confidence': float (0-1),
                'folders': list of folder patterns to search,
                'explanation': str
            }
        """
        query_lower = query.lower()
        
        # Check each intent
        intent_scores = {}
        
        for intent, config in self.INTENT_PATTERNS.items():
            score = 0
            
            # Check keyword matches
            keyword_matches = sum(1 for keyword in config['keywords'] if keyword in query_lower)
            score += keyword_matches * 2  # Weight keywords heavily
            
            # Check pattern matches (for PROJECT intent)
            if 'patterns' in config:
                for pattern in config['patterns']:
                    if re.search(pattern, query, re.IGNORECASE):
                        score += 5  # Patterns are very strong signals
            
            intent_scores[intent] = score
        
        # Get highest scoring intent
        max_score = max(intent_scores.values())
        
        if max_score == 0:
            # No clear intent - default to GENERAL
            return {
                'intent': QueryIntent.GENERAL,
                'confidence': 0.0,
                'folders': [],  # Search all folders
                'explanation': 'No specific intent detected, searching all documents'
            }
        
        detected_intent = max(intent_scores, key=intent_scores.get)
        confidence = min(max_score / 10, 1.0)  # Normalize to 0-1
        
        return {
            'intent': detected_intent,
            'confidence': confidence,
            'folders': self.INTENT_PATTERNS[detected_intent]['folders'],
            'explanation': f"Detected {detected_intent.value} query (confidence: {confidence:.2f})"
        }
    
    def get_search_filter(self, intent_result: Dict) -> Optional[str]:
        """
        Convert intent detection result to Azure Search filter.
        
        Returns OData filter string for Azure Search, or None for general search.
        """
        intent = intent_result['intent']
        folders = intent_result.get('folders', [])
        
        if not folders or intent == QueryIntent.GENERAL:
            return None
        
        # Build filter to search in specific folders
        # OData syntax: search.ismatch('pattern', 'field')
        folder_patterns = []
        for folder in folders:
            if '*' in folder:
                # Wildcard pattern (e.g., "Clients/*/Jobs")
                pattern = folder.replace('*', '.*')
                folder_patterns.append(f"search.ismatch('{pattern}', 'folder')")
            else:
                # Exact folder match or starts with
                folder_patterns.append(f"search.ismatch('{folder}*', 'folder')")
        
        # Combine with OR
        if folder_patterns:
            return " or ".join(folder_patterns)
        
        return None
