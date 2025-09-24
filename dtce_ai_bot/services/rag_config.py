"""
Advanced RAG Configuration Service
Manages settings and parameters for the enhanced RAG system
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class SearchMode(Enum):
    """Search modes for different query types."""
    HYBRID = "hybrid"          # Vector + keyword + semantic
    VECTOR_ONLY = "vector"     # Semantic similarity only  
    KEYWORD_ONLY = "keyword"   # Full-text search only
    SEMANTIC = "semantic"      # Azure Cognitive Search semantic


class ChunkingStrategy(Enum):
    """Document chunking strategies."""
    SEMANTIC = "semantic"      # Based on content meaning
    FIXED_SIZE = "fixed"       # Fixed character count
    PARAGRAPH = "paragraph"    # Natural paragraph breaks
    SECTION = "section"        # Document sections


@dataclass
class RAGConfig:
    """Configuration settings for RAG operations."""
    
    # Query type configurations
    query_configs: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'factual': {
            'max_sources': 3,
            'chunk_overlap': 100,
            'temperature': 0.1,
            'prompt_template': 'factual_template'
        },
        'comparative': {
            'max_sources': 5,
            'chunk_overlap': 150,
            'temperature': 0.2,
            'prompt_template': 'comparative_template'
        },
        'analytical': {
            'max_sources': 7,
            'chunk_overlap': 200,
            'temperature': 0.3,
            'prompt_template': 'analytical_template'
        },
        'procedural': {
            'max_sources': 4,
            'chunk_overlap': 100,
            'temperature': 0.1,
            'prompt_template': 'procedural_template'
        },
        'design': {
            'max_sources': 6,
            'chunk_overlap': 150,
            'temperature': 0.2,
            'prompt_template': 'design_template'
        }
    })
    
    # Advanced RAG settings
    advanced_rag_config: Dict[str, Any] = field(default_factory=lambda: {
        'enable_query_rewriting': True,
        'enable_semantic_chunking': True,
        'enable_hybrid_search': True,
        'enable_reranking': True,
        'max_query_rewrites': 3,
        'semantic_chunk_size': 512,
        'hybrid_search_weights': {'vector': 0.6, 'keyword': 0.4},
        'reranking_top_k': 10
    })
    
    # Chunking strategies
    chunking_strategies: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'semantic': {
            'method': 'semantic_similarity',
            'threshold': 0.75,
            'min_chunk_size': 200,
            'max_chunk_size': 800
        },
        'fixed': {
            'method': 'fixed_size',
            'chunk_size': 500,
            'overlap': 100
        },
        'adaptive': {
            'method': 'adaptive_size',
            'base_size': 400,
            'min_size': 200,
            'max_size': 1000
        }
    })
    
    # Prompt templates
    prompt_templates: Dict[str, str] = field(default_factory=lambda: {
        'factual_template': """Based on the provided documents, answer the following question with specific facts and details.
        
Question: {query}

Context: {context}

Requirements:
- Provide accurate, specific information
- Reference relevant standards or codes
- Include technical details where appropriate
- If information is incomplete, state what's missing

Answer:""",

        'comparative_template': """Compare and analyze the following aspects based on the provided documents.

Question: {query}

Context: {context}

Requirements:
- Provide clear comparisons with specific criteria
- Highlight key differences and similarities
- Reference relevant standards for each option
- Consider pros and cons where applicable

Analysis:""",

        'analytical_template': """Analyze the following query using engineering principles and the provided documentation.

Question: {query}

Context: {context}

Requirements:
- Provide thorough technical analysis
- Consider multiple perspectives and factors
- Reference relevant codes and standards
- Include potential risks or considerations
- Suggest best practices where appropriate

Analysis:""",

        'procedural_template': """Provide step-by-step guidance based on the documentation and industry best practices.

Question: {query}

Context: {context}

Requirements:
- Break down into clear, actionable steps
- Reference relevant standards and procedures
- Include safety considerations
- Note any prerequisites or requirements
- Highlight critical checkpoints

Procedure:""",

        'design_template': """Provide design guidance and recommendations based on the engineering documentation.

Question: {query}

Context: {context}

Requirements:
- Consider design criteria and constraints
- Reference applicable standards and codes
- Include calculation methods where relevant
- Consider constructability and practicality
- Highlight key design decisions

Design Guidance:"""
    })


class RAGConfigService:
    """Service for managing RAG configuration and query type detection."""
    
    def __init__(self):
        self.config = RAGConfig()
        logger.info("RAG Configuration Service initialized")
    
    def detect_query_type(self, query: str) -> str:
        """Detect the type of query for appropriate processing."""
        
        query_lower = query.lower()
        
        # Comparative queries
        comparative_keywords = [
            'compare', 'comparison', 'versus', 'vs', 'difference', 'differences',
            'better', 'best', 'worst', 'pros and cons', 'advantages', 'disadvantages'
        ]
        
        if any(keyword in query_lower for keyword in comparative_keywords):
            return 'comparative'
        
        # Analytical queries
        analytical_keywords = [
            'analyze', 'analysis', 'evaluate', 'assessment', 'impact', 'effect',
            'relationship', 'correlation', 'trend', 'pattern', 'implication'
        ]
        
        if any(keyword in query_lower for keyword in analytical_keywords):
            return 'analytical'
        
        # Procedural queries
        procedural_keywords = [
            'how to', 'steps', 'procedure', 'process', 'method', 'guide',
            'tutorial', 'instruction', 'calculate', 'design process'
        ]
        
        if any(keyword in query_lower for keyword in procedural_keywords):
            return 'procedural'
        
        # Design queries
        design_keywords = [
            'design', 'sizing', 'specification', 'requirement', 'criteria',
            'dimension', 'capacity', 'load', 'strength', 'stability'
        ]
        
        if any(keyword in query_lower for keyword in design_keywords):
            return 'design'
        
        # Default to factual
        return 'factual'
    
    def get_query_config(self, query_type: str) -> Dict[str, Any]:
        """Get configuration for a specific query type."""
        return self.config.query_configs.get(query_type, self.config.query_configs['factual'])
    
    def get_advanced_rag_config(self) -> Dict[str, Any]:
        """Get advanced RAG configuration."""
        return self.config.advanced_rag_config
    
    def get_chunking_strategy(self, strategy_name: str) -> Dict[str, Any]:
        """Get configuration for a chunking strategy."""
        return self.config.chunking_strategies.get(strategy_name, self.config.chunking_strategies['semantic'])
    
    def get_prompt_template(self, template_name: str) -> str:
        """Get a prompt template."""
        return self.config.prompt_templates.get(template_name, self.config.prompt_templates['factual_template'])


class AdvancedRAGConfigService:
    """Service for managing Advanced RAG configuration."""
    
    def __init__(self):
        self.config = RAGConfig()
        self.query_type_configs = self._initialize_query_type_configs()
        logger.info("Advanced RAG Configuration Service initialized")
    
    def _initialize_query_type_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize specialized configurations for different query types."""
        
        return {
            'technical_analysis': {
                'search_mode': SearchMode.HYBRID,
                'max_results': 25,
                'enable_decomposition': True,
                'rerank_threshold': 0.7,
                'context_window': 1500
            },
            
            'nz_standards': {
                'search_mode': SearchMode.SEMANTIC,
                'max_results': 15,
                'prioritize_standards_docs': True,
                'exact_clause_matching': True,
                'context_window': 800
            },
            
            'project_search': {
                'search_mode': SearchMode.HYBRID,
                'max_results': 30,
                'enable_project_filtering': True,
                'include_metadata': True,
                'context_window': 1200
            },
            
            'policy_query': {
                'search_mode': SearchMode.KEYWORD_ONLY,
                'max_results': 10,
                'exact_policy_matching': True,
                'require_policy_source': True,
                'context_window': 1000
            },
            
            'conversational': {
                'search_mode': SearchMode.VECTOR_ONLY,
                'max_results': 10,
                'use_conversation_context': True,
                'lower_threshold': True,
                'context_window': 800
            },
            
            'multi_project_analysis': {
                'search_mode': SearchMode.HYBRID,
                'max_results': 40,
                'enable_cross_project_comparison': True,
                'aggregate_similar_projects': True,
                'context_window': 2000
            }
        }
    
    def get_config_for_query_type(self, query_type: str, 
                                  complexity_score: float = 0.5) -> Dict[str, Any]:
        """
        Get optimized configuration for a specific query type.
        
        Args:
            query_type: Type of query (technical_analysis, nz_standards, etc.)
            complexity_score: Query complexity score (0.0 to 1.0)
            
        Returns:
            Optimized configuration dictionary
        """
        
        base_config = self.query_type_configs.get(query_type, {})
        
        # Adjust configuration based on complexity
        if complexity_score > 0.8:  # High complexity
            base_config.update({
                'max_results': int(base_config.get('max_results', 20) * 1.5),
                'enable_decomposition': True,
                'context_window': int(base_config.get('context_window', 1000) * 1.3)
            })
        elif complexity_score < 0.3:  # Low complexity
            base_config.update({
                'max_results': max(10, int(base_config.get('max_results', 20) * 0.7)),
                'context_window': max(500, int(base_config.get('context_window', 1000) * 0.8))
            })
        
        logger.info("Generated query-specific config", 
                   query_type=query_type, 
                   complexity=complexity_score,
                   max_results=base_config.get('max_results'))
        
        return base_config
    
    def get_chunking_config(self, document_type: str) -> Dict[str, Any]:
        """Get optimized chunking configuration for document type."""
        
        chunking_configs = {
            'engineering_report': {
                'strategy': ChunkingStrategy.SECTION,
                'max_size': 1200,
                'overlap': 200,
                'preserve_tables': True
            },
            
            'nz_standard': {
                'strategy': ChunkingStrategy.PARAGRAPH,
                'max_size': 800,
                'overlap': 100,
                'preserve_clause_numbers': True
            },
            
            'email': {
                'strategy': ChunkingStrategy.SEMANTIC,
                'max_size': 600,
                'overlap': 50,
                'preserve_thread_structure': True
            },
            
            'calculation': {
                'strategy': ChunkingStrategy.SECTION,
                'max_size': 1000,
                'overlap': 150,
                'preserve_equations': True
            },
            
            'drawing': {
                'strategy': ChunkingStrategy.FIXED_SIZE,
                'max_size': 500,
                'overlap': 100,
                'extract_text_only': True
            }
        }
        
        return chunking_configs.get(document_type, {
            'strategy': self.config.chunking_strategy,
            'max_size': self.config.max_chunk_size,
            'overlap': self.config.chunk_overlap
        })
    
    def get_search_filters(self, intent: str, user_context: Dict[str, Any] = None) -> List[str]:
        """Generate search filters based on intent and user context."""
        
        filters = []
        
        # Intent-based filters
        if intent == 'nz_standards':
            filters.append("folder eq 'NZ Standards' or folder eq 'Standards'")
        elif intent == 'policy':
            filters.append("folder eq 'Policies' or folder eq 'HR' or folder eq 'H&S'")
        elif intent == 'project_specific' and user_context:
            project_id = user_context.get('project_id')
            if project_id:
                filters.append(f"project_name eq '{project_id}'")
        
        # Date-based filters for recent documents
        if self.config.prioritize_recent_documents:
            # This would need to be implemented based on your document schema
            pass
        
        # File type filters for technical queries
        if intent in ['technical_analysis', 'engineering_calculation']:
            filters.append("file_type in ('pdf', 'docx') and folder ne 'Archive'")
        
        return filters
    
    def get_prompt_template(self, intent: str, complexity: str = 'medium') -> str:
        """Get specialized prompt template for intent and complexity level."""
        
        templates = {
            'technical_analysis': {
                'high': """You are a senior structural engineer providing comprehensive technical analysis.

Analyze the following engineering documents and provide a detailed technical assessment including:
- Design methodologies and approaches used
- Compliance with NZ standards and building codes  
- Structural considerations and load analysis
- Risk factors and mitigation strategies
- Recommendations for similar future projects

Base your analysis strictly on the provided documentation.""",
                
                'medium': """You are a structural engineer providing technical guidance.

Review the engineering documents and provide:
- Key technical findings and approaches
- Relevant NZ standards compliance
- Important design considerations
- Practical recommendations

Use only information from the provided documents.""",
                
                'low': """Provide a technical summary of the engineering documents focusing on:
- Main design approach
- Key requirements and standards
- Important findings

Base response on provided documentation only."""
            },
            
            'nz_standards': {
                'high': """You are an expert in New Zealand engineering standards providing detailed code guidance.

Reference the NZ standards documents to provide:
- Exact clause numbers and requirements
- Specific values, tolerances, and limits  
- Code interpretation and application guidance
- Compliance verification steps
- Interrelated standard requirements

Quote directly from standards where possible.""",
                
                'medium': """Provide NZ standards guidance including:
- Relevant standard clauses and sections
- Required values and specifications
- Compliance requirements
- Application notes

Reference specific standards documents.""",
                
                'low': """Summarize the NZ standard requirements for this topic:
- Key requirements and values
- Applicable standard clauses
- Compliance notes"""
            }
        }
        
        return templates.get(intent, {}).get(complexity, templates['technical_analysis']['medium'])
    
    def should_include_safety_disclaimer(self, question: str, response: str) -> bool:
        """Determine if safety disclaimer should be included."""
        
        safety_indicators = any(
            keyword in question.lower() or keyword in response.lower()
            for keyword in self.config.safety_disclaimer_threshold
        )
        
        return safety_indicators
    
    def get_confidence_thresholds(self) -> Dict[str, float]:
        """Get confidence scoring thresholds for response quality."""
        
        return {
            'high_confidence': 0.8,
            'medium_confidence': 0.6,
            'low_confidence': 0.4,
            'min_acceptable': 0.3
        }
    
    def update_config(self, **kwargs):
        """Update configuration parameters."""
        
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Updated RAG config: {key} = {value}")
            else:
                logger.warning(f"Unknown config parameter: {key}")


# Global configuration instance
rag_config_service = AdvancedRAGConfigService()
