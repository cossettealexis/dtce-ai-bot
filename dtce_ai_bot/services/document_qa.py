"""
GPT integration service for answering questions about documents.
Connects to Azure OpenAI or OpenAI to provide intelligent responses.
"""

import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
from ..config.settings import get_settings

logger = structlog.get_logger(__name__)


class DocumentQAService:
    """Service for answering questions about indexed documents using GPT."""
    
    def __init__(self, search_client: SearchClient):
        """Initialize the QA service."""
        self.search_client = search_client
        settings = get_settings()
        
        # Initialize Azure OpenAI client
        self.openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version
        )
        
        self.model_name = settings.azure_openai_deployment_name
        self.max_context_length = 8000  # Conservative limit for context
        
        # Initialize smart query classification
        from .query_classification import QueryClassificationService, SmartQueryRouter
        self.classification_service = QueryClassificationService(self.openai_client, self.model_name)
        self.smart_router = SmartQueryRouter(self.classification_service)
        
        # Initialize RAG handler for specification-compliant responses
        from .rag_handler import RAGHandler
        self.rag_handler = RAGHandler(self.search_client, self.openai_client, self.model_name)
        
        # Project scoping and analysis configuration
        self.project_analysis_enabled = True
        
    async def answer_question(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Answer a question using document context from the search index.
        
        Args:
            question: The question to answer
            project_filter: Optional project filter to limit search scope
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        try:
            logger.info("Processing question", question=question, project_filter=project_filter)
            
            # Handle basic greetings and help requests
            question_lower = question.lower().strip()
            if question_lower in ["hey", "hi", "hello", "hi there", "good morning", "good afternoon"]:
                return {
                    'answer': """Hi there! 👋 

I'm your DTCE AI assistant. I can help you find engineering documents, reports, and project files.

Just ask me in plain English about what you're looking for:
• "Find structural calculations"
• "Show me bridge drawings" 
• "What reports do we have for the project?"

What can I help you find today?""",
                    'sources': [],
                    'confidence': 'high',
                    'documents_searched': 0,
                    'search_type': 'greeting'
                }
            elif question_lower in ["help", "help me", "how do i use this system?", "what can you help me with?", "what can you do"]:
                return {
                    'answer': """🔧 **DTCE AI Assistant - Here's what I can help you with:**

**Document Search:**
• Find engineering reports, calculations, and drawings
• Search project files and specifications
• Locate building consent documents

**Engineering Guidance:**
• NZS building codes and standards
• Structural engineering questions
• Seismic design requirements
• Material specifications

**Project Information:**
• Past project references and examples
• Client work history
• Template forms and calculations

Just ask me specific questions about DTCE's work!""",
                    'sources': [],
                    'confidence': 'high',
                    'documents_searched': 0,
                    'search_type': 'help'
                }
            # Handle basic conversational responses that should NOT trigger document search
            elif question_lower in ["ok", "okay", "thanks", "thank you", "yes", "no", "sure", "really", "really?", "wow", "nice", "cool", "es", "yep", "yeah", "nah", "hmm", "ah", "oh", "alright", "got it"]:
                return {
                    'answer': """I'm here when you need help with engineering questions! 

Ask me about:
• Finding specific documents or reports
• Engineering standards and codes
• Project information
• Technical calculations

What would you like to know?""",
                    'sources': [],
                    'confidence': 'high',
                    'documents_searched': 0,
                    'search_type': 'conversational'
                }
            elif question_lower in ["what", "what?"] or len(question.strip()) < 3:
                return {
                    'answer': "I need a bit more information to help you. Please ask a specific question about engineering, projects, standards, or anything else I can assist with!",
                    'sources': [],
                    'confidence': 'high', 
                    'documents_searched': 0,
                    'search_type': 'clarification'
                }
            
            # First try RAG pattern matching for specification-compliant responses
            logger.info("Checking RAG patterns", question=question)
            rag_response = await self.rag_handler.process_rag_query(question, project_filter)
            
            # If RAG handler found a specific pattern, use its response
            if rag_response.get('rag_type') != 'general_query':
                logger.info("RAG pattern matched", rag_type=rag_response.get('rag_type'))
                return rag_response
            
            # If no specific RAG pattern found, use intelligent intent understanding
            logger.info("No RAG pattern matched, using intelligent intent understanding", question=question)
            
            # Use GPT to understand intent and search intelligently
            intent_response = await self._handle_intelligent_fallback(question, project_filter)
            return intent_response
            
        except Exception as e:
            logger.error("Question answering failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while processing your question: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }
    
    async def _classify_engineering_intent(self, question: str) -> Dict[str, Any]:
        """Use AI to classify engineering-specific intent and extract domain information."""
        
        classification_prompt = f"""
You are an expert AI assistant for a structural engineering consultancy (DTCE). 
Analyze this user query and classify the engineering intent.

INTENT CATEGORIES:
1. **NZS_CODE_LOOKUP**: User wants specific clause, section, or information from NZ Standards (NZS 3101, AS/NZS, etc.)
2. **PROJECT_REFERENCE**: User wants past DTCE projects with specific characteristics or scope
3. **SCENARIO_TECHNICAL**: User wants projects matching specific building type + conditions + location scenarios
4. **LESSONS_LEARNED**: User wants issues, failures, problems, or lessons from past projects
5. **REGULATORY_PRECEDENT**: User wants examples of council approvals, consents, or regulatory challenges
6. **COST_TIME_INSIGHTS**: User wants project timeline analysis, cost information, scope expansion examples
7. **BEST_PRACTICES_TEMPLATES**: User wants standard approaches, best practice examples, or calculation templates
8. **MATERIALS_METHODS**: User wants comparisons of materials, construction methods, or technical specifications
9. **INTERNAL_KNOWLEDGE**: User wants to find engineers with specific expertise or work by team members
10. **PRODUCT_LOOKUP**: User wants product specs, suppliers, or material information
11. **TEMPLATE_REQUEST**: User wants calculation templates, design spreadsheets, or forms (PS1, PS3, etc.)
12. **CONTACT_LOOKUP**: User wants contact info for builders, contractors, clients we've worked with
13. **EXTERNAL_REFERENCE**: User wants online resources, external references, forums, papers, or discussions from outside DTCE
14. **GENERAL_SEARCH**: Basic document search that doesn't fit other categories

Examples of advanced queries:
- "Show me mid-rise timber buildings in high wind zones" → SCENARIO_TECHNICAL
- "What issues have we had with screw piles in soft soils?" → LESSONS_LEARNED  
- "How have we approached alternative solutions for stairs?" → REGULATORY_PRECEDENT
- "How long does PS1 take for small commercial?" → COST_TIME_INSIGHTS
- "Compare precast vs in-situ concrete decisions" → MATERIALS_METHODS
- "Which engineers have tilt-slab experience?" → INTERNAL_KNOWLEDGE
- "Find online references about tapered composite beams" → EXTERNAL_REFERENCE
- "Looking for forum discussions on seismic retrofitting" → EXTERNAL_REFERENCE

User Question: "{question}"

Respond with ONLY a JSON object:
{{
    "intent": "NZS_CODE_LOOKUP|PROJECT_REFERENCE|SCENARIO_TECHNICAL|LESSONS_LEARNED|REGULATORY_PRECEDENT|COST_TIME_INSIGHTS|BEST_PRACTICES_TEMPLATES|MATERIALS_METHODS|INTERNAL_KNOWLEDGE|PRODUCT_LOOKUP|TEMPLATE_REQUEST|CONTACT_LOOKUP|EXTERNAL_REFERENCE|GENERAL_SEARCH",
    "topic": "extracted technical topic",
    "building_type": "mid-rise|commercial|residential|industrial|etc (if applicable)",
    "conditions": ["high wind", "soft soil", "coastal", "seismic", "etc"],
    "location": "Wellington|Auckland|etc (if mentioned)",
    "comparison_type": "materials|methods|costs|timeline (if comparing)",
    "expertise_area": "tilt-slab|pile design|seismic (if seeking expertise)",
    "standard_reference": "NZS 3101|AS/NZS 1170|etc (if applicable)",
    "output_type": "clause|project_list|comparison|lessons|precedent|expertise|timeline|external_reference",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert engineering query classifier. Respond only with valid JSON."},
                    {"role": "user", "content": classification_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            import json
            intent = json.loads(response.choices[0].message.content.strip())
            
            logger.info("Engineering intent classified",
                       intent=intent.get('intent'),
                       topic=intent.get('topic'),
                       confidence=intent.get('confidence'))
            
            return intent
            
        except Exception as e:
            logger.error("Intent classification failed", error=str(e))
            # Fallback to simple pattern matching
            return self._fallback_intent_classification(question)
    
    def _fallback_intent_classification(self, question: str) -> Dict[str, Any]:
        """Fallback pattern-based intent classification if AI fails."""
        question_lower = question.lower()
        
        # Scenario-based patterns
        if any(pattern in question_lower for pattern in ['examples of', 'show me', 'find projects']) and \
           any(condition in question_lower for condition in ['wind', 'seismic', 'coastal', 'steep', 'soft soil']):
            return {
                "intent": "SCENARIO_TECHNICAL",
                "topic": question,
                "output_type": "project_list",
                "confidence": 0.8,
                "reasoning": "Contains scenario-based project search keywords"
            }
        
        # Lessons learned patterns
        elif any(pattern in question_lower for pattern in ['issues', 'problems', 'lessons learned', 'failed', 'difficulties']):
            return {
                "intent": "LESSONS_LEARNED",
                "topic": question,
                "output_type": "lessons",
                "confidence": 0.8,
                "reasoning": "Contains lessons learned keywords"
            }
        
        # Cost/time patterns
        elif any(pattern in question_lower for pattern in ['how long', 'cost', 'timeline', 'duration', 'expanded']):
            return {
                "intent": "COST_TIME_INSIGHTS",
                "topic": question,
                "output_type": "timeline",
                "confidence": 0.8,
                "reasoning": "Contains cost/time keywords"
            }
        
        # Best practices patterns
        elif any(pattern in question_lower for pattern in ['standard approach', 'best practice', 'how do we', 'our approach']):
            return {
                "intent": "BEST_PRACTICES_TEMPLATES",
                "topic": question,
                "output_type": "guidance",
                "confidence": 0.8,
                "reasoning": "Contains best practices keywords"
            }
        
        # Comparison patterns
        elif any(pattern in question_lower for pattern in ['compare', 'vs', 'versus', 'difference', 'when do we choose']):
            return {
                "intent": "MATERIALS_METHODS",
                "topic": question,
                "comparison_type": "methods",
                "output_type": "comparison",
                "confidence": 0.8,
                "reasoning": "Contains comparison keywords"
            }
        
        # Internal knowledge patterns
        elif any(pattern in question_lower for pattern in ['which engineer', 'who has experience', 'who worked on']):
            return {
                "intent": "INTERNAL_KNOWLEDGE",
                "topic": question,
                "output_type": "expertise",
                "confidence": 0.8,
                "reasoning": "Contains internal expertise keywords"
            }
        
        # NZS/Standards patterns
        if any(pattern in question_lower for pattern in ['nzs', 'clause', 'standard', 'code', 'as/nzs']):
            return {
                "intent": "NZS_CODE_LOOKUP",
                "topic": question,
                "standard_reference": "NZS",
                "output_type": "clause",
                "confidence": 0.8,
                "reasoning": "Contains standards keywords"
            }
        
        # Project patterns
        elif any(pattern in question_lower for pattern in ['project', 'past', 'similar', 'worked on', 'done before']):
            return {
                "intent": "PROJECT_REFERENCE", 
                "topic": question,
                "output_type": "project_list",
                "confidence": 0.8,
                "reasoning": "Contains project keywords"
            }
        
        # Template patterns
        elif any(pattern in question_lower for pattern in ['template', 'ps1', 'ps3', 'form', 'spreadsheet', 'calculation']):
            return {
                "intent": "TEMPLATE_REQUEST",
                "topic": question,
                "output_type": "template",
                "confidence": 0.8,
                "reasoning": "Contains template keywords"
            }
        
        # Contact patterns
        elif any(pattern in question_lower for pattern in ['builder', 'contractor', 'contact', 'client', 'worked with']):
            return {
                "intent": "CONTACT_LOOKUP",
                "topic": question,
                "output_type": "contact_info",
                "confidence": 0.8,
                "reasoning": "Contains contact keywords"
            }
        
        # External reference patterns
        elif any(pattern in question_lower for pattern in ['online', 'reference', 'forum', 'thread', 'external', 'anonymous', 'internet', 'research paper', 'publication', 'literature']):
            return {
                "intent": "EXTERNAL_REFERENCE",
                "topic": question,
                "output_type": "external_reference",
                "confidence": 0.8,
                "reasoning": "User wants external/online references"
            }
        
        else:
            return {
                "intent": "GENERAL_SEARCH",
                "topic": question,
                "output_type": "guidance",
                "confidence": 0.6,
                "reasoning": "General engineering query"
            }
    
    async def _route_to_domain_handler(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Route to specialized handler based on engineering domain intent."""
        
        intent_type = intent.get('intent', 'GENERAL_SEARCH')
        
        try:
            if intent_type == "NZS_CODE_LOOKUP":
                return await self._handle_nzs_code_lookup(intent, project_filter)
            elif intent_type == "PROJECT_REFERENCE":
                return await self._handle_project_reference(intent, project_filter)
            elif intent_type == "SCENARIO_TECHNICAL":
                return await self._handle_scenario_technical(intent, project_filter)
            elif intent_type == "LESSONS_LEARNED":
                return await self._handle_lessons_learned(intent, project_filter)
            elif intent_type == "REGULATORY_PRECEDENT":
                return await self._handle_regulatory_precedent(intent, project_filter)
            elif intent_type == "COST_TIME_INSIGHTS":
                return await self._handle_cost_time_insights(intent, project_filter)
            elif intent_type == "BEST_PRACTICES_TEMPLATES":
                return await self._handle_best_practices_templates(intent, project_filter)
            elif intent_type == "MATERIALS_METHODS":
                return await self._handle_materials_methods(intent, project_filter)
            elif intent_type == "INTERNAL_KNOWLEDGE":
                return await self._handle_internal_knowledge(intent, project_filter)
            elif intent_type == "PRODUCT_LOOKUP":
                return await self._handle_product_lookup(intent, project_filter)
            elif intent_type == "TEMPLATE_REQUEST":
                return await self._handle_template_request(intent, project_filter)
            elif intent_type == "CONTACT_LOOKUP":
                return await self._handle_contact_lookup(intent, project_filter)
            elif intent_type == "EXTERNAL_REFERENCE":
                return await self._handle_external_reference(intent, project_filter)
            else:  # GENERAL_SEARCH
                return await self._handle_general_engineering_search(intent, project_filter)
                
        except Exception as e:
            logger.error("Domain handler failed", error=str(e), intent=intent_type)
            return {
                'answer': "I encountered an error processing your engineering query. Please try rephrasing your question.",
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }
    
    async def _handle_nzs_code_lookup(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle NZ Standards and code lookup queries."""
        topic = intent.get('topic', '')
        logger.info("Handling NZS code lookup", topic=topic)
        
        # Search for standards documents
        documents = self._search_relevant_documents(f"NZS {topic}", project_filter)
        
        if documents:
            # Generate clause-focused answer
            answer = await self._generate_answer_from_documents(
                f"What clause or section in NZ Standards covers {topic}? Please provide the specific clause number and explanation.",
                documents
            )
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high' if len(documents) >= 2 else 'medium',
                'documents_searched': len(documents),
                'search_type': 'nzs_code_lookup'
            }
        else:
            return {
                'answer': f"I couldn't find specific NZ Standards information for '{topic}'. You might need to check the physical standards documents or contact Standards New Zealand.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'nzs_no_results'
            }
    
    async def _handle_project_reference(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle past project reference queries."""
        topic = intent.get('topic', '')
        logger.info("Handling project reference", topic=topic)
        
        # Search for project documents
        documents = self._search_relevant_documents(topic, project_filter)
        
        if documents:
            # Extract unique projects
            projects = self._extract_projects_from_documents(documents)
            
            if projects:
                answer = f"Here are past DTCE projects related to '{topic}':\n\n"
                for i, project in enumerate(projects[:10], 1):
                    answer += f"{i}. **{project['name']}** - {project['summary']}\n"
                    answer += f"   📁 [View in SuiteFiles]({project['suitefiles_url']})\n\n"
                
                if len(projects) > 10:
                    answer += f"... and {len(projects) - 10} more projects found."
                    
                return {
                    'answer': answer,
                    'sources': self._format_sources(documents[:5]),
                    'confidence': 'high' if len(projects) >= 3 else 'medium',
                    'documents_searched': len(documents),
                    'search_type': 'project_reference'
                }
            else:
                return {
                    'answer': f"I found {len(documents)} documents related to '{topic}' but couldn't identify specific project names. The documents might contain relevant examples.",
                    'sources': self._format_sources(documents[:5]),
                    'confidence': 'medium',
                    'documents_searched': len(documents),
                    'search_type': 'project_reference_unclear'
                }
        else:
            return {
                'answer': f"I couldn't find past DTCE projects specifically related to '{topic}'. Try using different keywords or ask about a broader topic.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'project_reference_no_results'
            }
    
    async def _handle_template_request(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle design template and form requests."""
        topic = intent.get('topic', '')
        logger.info("Handling template request", topic=topic)
        
        # Search for templates, spreadsheets, forms
        search_query = f"template calculation spreadsheet form PS1 PS3 {topic}"
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            # Filter for likely templates (Excel files, forms, etc.)
            template_docs = [doc for doc in documents if any(ext in doc.get('filename', '').lower() 
                           for ext in ['.xlsx', '.xls', '.pdf', 'template', 'form', 'ps1', 'ps3'])]
            
            if template_docs:
                answer = f"Here are the design templates and forms related to '{topic}':\n\n"
                for i, doc in enumerate(template_docs[:8], 1):
                    filename = doc.get('filename', 'Unknown')
                    answer += f"{i}. **{filename}**\n"
                    if doc.get('blob_url'):
                        safe_url = self._get_safe_suitefiles_url(doc['blob_url'])
                        answer += f"   📄 [Download]({safe_url})\n\n"
                
                return {
                    'answer': answer,
                    'sources': self._format_sources(template_docs),
                    'confidence': 'high',
                    'documents_searched': len(documents),
                    'search_type': 'template_request'
                }
            else:
                return {
                    'answer': f"I found documents related to '{topic}' but no specific templates or forms. You might need to check the Templates folder in SuiteFiles directly.",
                    'sources': self._format_sources(documents[:3]),
                    'confidence': 'medium',
                    'documents_searched': len(documents),
                    'search_type': 'template_request_no_templates'
                }
        else:
            return {
                'answer': f"I couldn't find templates or forms for '{topic}'. Check the Templates and Resources folders in SuiteFiles, or contact the team for custom templates.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'template_request_no_results'
            }
    
    async def _handle_general_engineering_search(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle general engineering searches."""
        topic = intent.get('topic', '')
        logger.info("Handling general engineering search", topic=topic)
        
        documents = self._search_relevant_documents(topic, project_filter)
        
        if documents:
            answer = await self._generate_answer_from_documents(topic, documents)
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high' if len(documents) >= 5 else 'medium',
                'documents_searched': len(documents),
                'search_type': 'general_engineering'
            }
        else:
            return {
                'answer': f"""I couldn't find specific information about '{topic}' in our project database.

I can help you with:
• **Standards & Codes**: "What clause in NZS 3101 covers..."
• **Past Projects**: "Show me projects with precast connections"
• **Templates**: "Find PS1 forms for steel design"
• **Technical Guidance**: "Best practice for foundation design"

What would you like to know?""",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'general_no_results'
            }
    
    async def _handle_product_lookup(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle product specification and supplier lookup queries."""
        topic = intent.get('topic', '')
        logger.info("Handling product lookup", topic=topic)
        
        # Search for product specs, material info
        search_query = f"product specification material supplier {topic}"
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            answer = await self._generate_answer_from_documents(
                f"What products, specifications, or suppliers are available for {topic}?",
                documents
            )
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'search_type': 'product_lookup'
            }
        else:
            return {
                'answer': f"I couldn't find specific product information for '{topic}'. You might need to check SuiteFiles product catalogs or contact suppliers directly.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'product_lookup_no_results'
            }
    
    async def _handle_contact_lookup(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle contact and contractor lookup queries."""
        topic = intent.get('topic', '')
        logger.info("Handling contact lookup", topic=topic)
        
        # Search for contractor/contact information
        search_query = f"contractor builder client contact {topic}"
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            answer = await self._generate_answer_from_documents(
                f"What contractors, builders, or contacts are associated with {topic}?",
                documents
            )
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'search_type': 'contact_lookup'
            }
        else:
            return {
                'answer': f"I couldn't find contact information related to '{topic}'. Check the project folders in SuiteFiles or contact the project manager directly.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'contact_lookup_no_results'
            }
    
    async def _handle_external_reference(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle requests for external references, online resources, and research papers."""
        topic = intent.get('topic', '')
        logger.info("Handling external reference request", topic=topic)
        
        # This is a request for external resources, not internal DTCE documents
        return {
            'answer': f"""I understand you're looking for external references and online resources about '{topic}'. 

As a DTCE AI assistant, I primarily search our internal engineering database and project files. For external references, online forums, and research papers, I'd recommend:

**🌐 Online Resources:**
• **Eng-Tips Forums** (eng-tips.com) - Excellent discussions by structural engineers
• **Structural Engineering Forums** (structuralengineering.info)
• **Reddit r/StructuralEngineering** - Active community discussions
• **Civil Engineering Forum** (civilengineering.com)

**📚 Research & Academic Sources:**
• **ResearchGate** - Academic papers and discussions
• **Google Scholar** - Academic literature search
• **AISC Steel Construction** - Technical articles and papers
• **Concrete International Magazine**

**🔍 Professional Resources:**
• **SEI (Structural Engineering Institute)** publications
• **NZCS (New Zealand Concrete Society)** resources
• **SESOC (Structural Engineering Society of New Zealand)**

For your specific topic about '{topic}', try searching these platforms with relevant keywords. You'll likely find valuable discussions from anonymous structural engineers and detailed technical papers.

Would you like me to help you find any related information from our internal DTCE database instead?""",
            'sources': [],
            'confidence': 'high',
            'documents_searched': 0,
            'search_type': 'external_reference'
        }
    
    async def _handle_scope_similarity(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle scope similarity queries for fee estimation."""
        topic = intent.get('topic', '')
        logger.info("Handling scope similarity", topic=topic)
        
        # Search for similar project scopes
        documents = self._search_relevant_documents(topic, project_filter)
        
        if documents:
            projects = self._extract_projects_from_documents(documents)
            
            if projects:
                answer = f"Here are past projects with similar scope to '{topic}':\n\n"
                for i, project in enumerate(projects[:8], 1):
                    answer += f"{i}. **{project['name']}** - {project['summary']}\n"
                    answer += f"   📁 [View in SuiteFiles]({project['suitefiles_url']})\n\n"
                
                answer += "\n💡 **For fee estimation**: Review these projects' scope, timeline, and billing records in SuiteFiles."
                
                return {
                    'answer': answer,
                    'sources': self._format_sources(documents[:5]),
                    'confidence': 'high' if len(projects) >= 3 else 'medium',
                    'documents_searched': len(documents),
                    'search_type': 'scope_similarity'
                }
            else:
                return {
                    'answer': f"I found documents related to '{topic}' but couldn't identify specific comparable projects. You might need to manually review project scopes.",
                    'sources': self._format_sources(documents[:3]),
                    'confidence': 'low',
                    'documents_searched': len(documents),
                    'search_type': 'scope_similarity_unclear'
                }
        else:
            return {
                'answer': f"I couldn't find projects with similar scope to '{topic}'. Try broadening your search terms or contact senior engineers for comparable project examples.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'scope_similarity_no_results'
            }
    
    async def _handle_technical_guidance(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle technical engineering guidance queries."""
        topic = intent.get('topic', '')
        logger.info("Handling technical guidance", topic=topic)
        
        # Search for technical guidance, best practices
        search_query = f"design guidance best practice methodology {topic}"
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            answer = await self._generate_answer_from_documents(
                f"What is the best practice or design guidance for {topic}?",
                documents
            )
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'search_type': 'technical_guidance'
            }
        else:
            return {
                'answer': f"I couldn't find specific technical guidance for '{topic}' in our documents. You might want to consult relevant standards or contact senior engineers.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'technical_guidance_no_results'
            }
    
    async def _handle_regulatory_precedent(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle regulatory precedent and consent queries."""
        topic = intent.get('topic', '')
        logger.info("Handling regulatory precedent", topic=topic)
        
        # Search for council approvals, consents, regulatory issues
        search_query = f"council consent approval regulatory precedent {topic}"
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            answer = await self._generate_answer_from_documents(
                f"What regulatory precedents, council approvals, or consent examples exist for {topic}?",
                documents
            )
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'search_type': 'regulatory_precedent'
            }
        else:
            return {
                'answer': f"I couldn't find regulatory precedents for '{topic}'. Check with the regulatory team or review past consent applications in SuiteFiles.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'regulatory_precedent_no_results'
            }
    
    async def _handle_scenario_technical(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle scenario-based technical queries with building type + conditions."""
        topic = intent.get('topic', '')
        building_type = intent.get('building_type', '')
        conditions = intent.get('conditions', [])
        location = intent.get('location', '')
        
        logger.info("Handling scenario technical query", 
                   topic=topic, building_type=building_type, conditions=conditions, location=location)
        
        # Build enhanced search query with scenario attributes
        search_terms = [topic]
        if building_type: search_terms.append(building_type)
        if conditions: search_terms.extend(conditions)
        if location: search_terms.append(location)
        
        search_query = ' '.join(search_terms)
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            projects = self._extract_projects_from_documents(documents)
            
            if projects:
                scenario_desc = f"{building_type} buildings" if building_type else "projects"
                if conditions:
                    scenario_desc += f" in {' and '.join(conditions)} conditions"
                if location:
                    scenario_desc += f" in {location}"
                
                answer = f"Here are examples of {scenario_desc} that DTCE has designed:\n\n"
                
                for i, project in enumerate(projects[:8], 1):
                    answer += f"{i}. **{project['name']}** - {project['summary']}\n"
                    answer += f"   📁 [View in SuiteFiles]({project['suitefiles_url']})\n\n"
                
                if len(projects) > 8:
                    answer += f"... and {len(projects) - 8} more similar projects found."
                
                return {
                    'answer': answer,
                    'sources': self._format_sources(documents[:5]),
                    'confidence': 'high' if len(projects) >= 3 else 'medium',
                    'documents_searched': len(documents),
                    'search_type': 'scenario_technical'
                }
            else:
                return {
                    'answer': f"I found documents related to your scenario but couldn't identify specific project examples. The search returned {len(documents)} relevant documents.",
                    'sources': self._format_sources(documents[:3]),
                    'confidence': 'medium',
                    'documents_searched': len(documents),
                    'search_type': 'scenario_technical_unclear'
                }
        else:
            return {
                'answer': f"I couldn't find specific examples of {building_type} projects with {', '.join(conditions) if conditions else 'those conditions'}. Try broadening your search criteria.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'scenario_technical_no_results'
            }
    
    async def _handle_lessons_learned(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle lessons learned and problem analysis queries."""
        topic = intent.get('topic', '')
        logger.info("Handling lessons learned query", topic=topic)
        
        # Search for issues, problems, lessons learned
        search_query = f"lessons learned issues problems failure construction {topic}"
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to analyze all documents for lessons learned, don't filter by keywords
            answer = await self._generate_answer_from_documents(
                f"What lessons have been learned or issues encountered with {topic}? Summarize any problems, failures, difficulties, or solutions from the project documents.",
                documents
            )
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high' if len(documents) >= 3 else 'medium',
                'documents_searched': len(documents),
                'search_type': 'lessons_learned'
            }
        else:
            return {
                'answer': f"I couldn't find documented lessons learned for '{topic}'. Check project folders for meeting minutes, construction issues, or post-project reviews.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'lessons_learned_no_results'
            }
    
    async def _handle_cost_time_insights(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle cost and timeline analysis queries."""
        topic = intent.get('topic', '')
        logger.info("Handling cost time insights query", topic=topic)
        
        # Search for timeline, cost, scope information
        search_query = f"timeline cost duration PS1 scope expansion fee variation {topic}"
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            answer = await self._generate_answer_from_documents(
                f"What are the typical costs, timelines, or scope considerations for {topic}?",
                documents
            )
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'search_type': 'cost_time_insights'
            }
        else:
            return {
                'answer': f"I couldn't find specific cost or timeline data for '{topic}'. Check project proposals, fee records, or contact project managers for historical data.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'cost_time_insights_no_results'
            }
    
    async def _handle_best_practices_templates(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle best practices and template requests."""
        topic = intent.get('topic', '')
        logger.info("Handling best practices templates query", topic=topic)
        
        # Search for best practices, standard approaches, reference examples
        search_query = f"best practice standard approach reference example template {topic}"
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            # Filter for template-like documents
            template_docs = [doc for doc in documents if any(keyword in doc.get('filename', '').lower() 
                           for keyword in ['template', 'reference', 'standard', 'example', '.xlsx', '.xls'])]
            
            answer = f"Here are the best practices and templates for {topic}:\n\n"
            
            if template_docs:
                for i, doc in enumerate(template_docs[:6], 1):
                    filename = doc.get('filename', 'Unknown')
                    answer += f"{i}. **{filename}**\n"
                    if doc.get('blob_url'):
                        safe_url = self._get_safe_suitefiles_url(doc['blob_url'])
                        answer += f"   📄 [Download]({safe_url})\n\n"
                
                # Add additional guidance from other documents
                if len(documents) > len(template_docs):
                    guidance = await self._generate_answer_from_documents(
                        f"What is the standard DTCE approach for {topic}?",
                        documents[:5]
                    )
                    answer += f"\n**Standard Approach:**\n{guidance}"
            else:
                answer = await self._generate_answer_from_documents(
                    f"What is the standard DTCE approach or best practice for {topic}?",
                    documents
                )
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'search_type': 'best_practices_templates'
            }
        else:
            return {
                'answer': f"I couldn't find documented best practices for '{topic}'. Check the Templates folder in SuiteFiles or consult with senior engineers.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'best_practices_templates_no_results'
            }
    
    async def _handle_materials_methods(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle materials and methods comparison queries."""
        topic = intent.get('topic', '')
        comparison_type = intent.get('comparison_type', '')
        logger.info("Handling materials methods comparison", topic=topic, comparison_type=comparison_type)
        
        # Search for comparative information
        search_query = f"compare comparison vs versus {topic}"
        documents = self._search_relevant_documents(search_query, project_filter)
        
        if documents:
            answer = await self._generate_answer_from_documents(
                f"Compare and contrast the different {comparison_type or 'approaches'} DTCE has used for {topic}. What are the pros and cons of each method?",
                documents
            )
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'search_type': 'materials_methods_comparison'
            }
        else:
            return {
                'answer': f"I couldn't find comparative information about {topic}. You might need to review multiple project examples manually or consult with experienced engineers.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'materials_methods_no_results'
            }
    
    async def _handle_internal_knowledge(self, intent: Dict[str, Any], project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle internal knowledge and expertise mapping queries."""
        topic = intent.get('topic', '')
        expertise_area = intent.get('expertise_area', '')
        logger.info("Handling internal knowledge query", topic=topic, expertise_area=expertise_area)
        
        # Search for documents to identify authorship and expertise
        documents = self._search_relevant_documents(topic, project_filter)
        
        if documents:
            # Extract authorship information where possible
            expertise_info = {}
            for doc in documents:
                # Try to extract project info and infer expertise
                project_id = self._extract_project_from_url(doc.get('blob_url', ''))
                filename = doc.get('filename', '')
                
                # This is a simplified approach - in a real system you'd have author metadata
                if project_id:
                    if project_id not in expertise_info:
                        expertise_info[project_id] = {
                            'project': project_id,
                            'documents': [],
                            'suitefiles_url': f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{project_id}"
                        }
                    expertise_info[project_id]['documents'].append(filename)
            
            if expertise_info:
                answer = f"Based on project documents, here's where DTCE has experience with {expertise_area or topic}:\n\n"
                
                for project_info in list(expertise_info.values())[:8]:
                    answer += f"**Project {project_info['project']}**:\n"
                    answer += f"  📁 [View in SuiteFiles]({project_info['suitefiles_url']})\n"
                    answer += f"  Documents: {', '.join(project_info['documents'][:3])}\n\n"
                
                answer += f"\n💡 **Recommendation**: Contact the project managers or check the team directory in SuiteFiles to identify specific engineers who worked on these projects."
                
                return {
                    'answer': answer,
                    'sources': self._format_sources(documents[:5]),
                    'confidence': 'medium',
                    'documents_searched': len(documents),
                    'search_type': 'internal_knowledge'
                }
            else:
                return {
                    'answer': f"I found documents related to {topic} but couldn't identify specific engineer expertise. Check the team directory or contact project managers directly.",
                    'sources': self._format_sources(documents[:3]),
                    'confidence': 'low',
                    'documents_searched': len(documents),
                    'search_type': 'internal_knowledge_unclear'
                }
        else:
            return {
                'answer': f"I couldn't find projects related to {expertise_area or topic}. Try checking the team directory in SuiteFiles or asking colleagues directly.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'search_type': 'internal_knowledge_no_results'
            }
    
    def _extract_projects_from_documents(self, documents: List[Dict]) -> List[Dict]:
        """Extract unique project information from search result documents."""
        projects = {}
        
        for doc in documents:
            # Extract project from URL path
            blob_url = doc.get('blob_url', '')
            project_id = self._extract_project_from_url(blob_url)
            
            if project_id and len(project_id) >= 6:  # Valid project IDs
                if project_id not in projects:
                    # Extract basic project info
                    projects[project_id] = {
                        'name': project_id,
                        'summary': self._generate_project_summary(project_id, doc),
                        'suitefiles_url': f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{project_id}",
                        'document_count': 1
                    }
                else:
                    projects[project_id]['document_count'] += 1
        
        # Convert to list and sort by relevance (document count)
        project_list = list(projects.values())
        project_list.sort(key=lambda x: x['document_count'], reverse=True)
        
        return project_list
    
    def _generate_project_summary(self, project_id: str, sample_doc: Dict) -> str:
        """Generate a brief summary for a project based on document info."""
        filename = sample_doc.get('filename', '')
        content = sample_doc.get('content', '')[:200]  # First 200 chars
        
        # Try to extract meaningful description from filename or content
        if 'hospital' in filename.lower() or 'hospital' in content.lower():
            return "Healthcare/Hospital project"
        elif 'school' in filename.lower() or 'education' in content.lower():
            return "Educational facility project"
        elif 'office' in filename.lower() or 'commercial' in content.lower():
            return "Commercial/Office building project"
        elif 'residential' in filename.lower() or 'apartment' in content.lower():
            return "Residential development project"
        elif 'bridge' in filename.lower() or 'bridge' in content.lower():
            return "Bridge infrastructure project"
        elif 'warehouse' in filename.lower() or 'industrial' in content.lower():
            return "Industrial/Warehouse project"
        else:
            return "Engineering project"

    async def analyze_project_scoping_request(self, scoping_text: str, rfp_content: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a project scoping request or RFP to find similar past projects,
        identify potential issues, and provide design philosophy recommendations.
        
        Args:
            scoping_text: The main scoping request text from client
            rfp_content: Optional additional RFP document content
            
        Returns:
            Dictionary with similar projects, recommendations, and potential issues
        """
        try:
            logger.info("Analyzing project scoping request", text_length=len(scoping_text))
            
            # Step 1: Extract key project characteristics from the scoping text
            project_characteristics = await self._extract_project_characteristics(scoping_text, rfp_content)
            
            # Step 2: Find similar past projects based on characteristics
            similar_projects = await self._find_similar_projects(project_characteristics)
            
            # Step 3: Analyze past issues and solutions from similar projects
            issues_analysis = await self._analyze_past_issues(similar_projects, project_characteristics)
            
            # Step 4: Generate design philosophy and recommendations
            design_philosophy = await self._generate_design_philosophy(project_characteristics, similar_projects, issues_analysis)
            
            # Step 5: Provide comprehensive analysis
            analysis_result = await self._generate_comprehensive_project_analysis(
                scoping_text, project_characteristics, similar_projects, issues_analysis, design_philosophy
            )
            
            return {
                'project_characteristics': project_characteristics,
                'similar_projects': similar_projects,
                'past_issues_analysis': issues_analysis,
                'design_philosophy': design_philosophy,
                'comprehensive_analysis': analysis_result,
                'confidence': 'high' if len(similar_projects) > 0 else 'medium',
                'similar_projects_found': len(similar_projects)
            }
            
        except Exception as e:
            logger.error("Project scoping analysis failed", error=str(e))
            return {
                'project_characteristics': {},
                'similar_projects': [],
                'past_issues_analysis': {},
                'design_philosophy': {},
                'comprehensive_analysis': f'I encountered an error while analyzing the project request: {str(e)}',
                'confidence': 'error',
                'similar_projects_found': 0
            }

    async def _generate_answer_from_documents(self, question: str, documents: List[Dict]) -> str:
        """Generate a comprehensive answer using the provided documents."""
        try:
            # Prepare context from documents with more content
            context_parts = []
            for doc in documents[:8]:  # Use top 8 documents for better context
                # Try extracted_text first (new schema), fallback to content (legacy)
                content = doc.get('extracted_text', '').strip() or doc.get('content', '').strip()
                filename = doc.get('filename', 'Unknown Document')
                project = doc.get('project_name', '') or self._extract_project_from_document(doc)
                
                if content:
                    # Use more content (1500 chars) for better context
                    context_part = f"**Document: {filename}**"
                    if project and project != 'Unknown':
                        context_part += f" (Project: {project})"
                    context_part += f"\nContent: {content[:1500]}..."
                    context_parts.append(context_part)
            
            if not context_parts:
                return f"I searched our database but couldn't find specific documents related to '{question}'. Try using different keywords or ask about a broader topic."
            
            context = "\n\n".join(context_parts)
            
            # Enhanced prompt specifically for document-based answers
            enhanced_question = f"""Based on the {len(context_parts)} documents found about '{question}', please provide a comprehensive answer. 

Extract specific information, examples, and insights from the documents. If the documents mention specific projects, issues, solutions, or recommendations, include those details. Even if the information is partial, extract what's useful and provide a complete answer.

Original question: {question}"""
            
            # Generate answer using the context with better error handling
            result = await self._generate_answer(enhanced_question, context)
            
            # Handle both string and dict responses
            if isinstance(result, dict):
                answer = result.get('answer', '').strip()
            else:
                answer = str(result).strip() if result else ''
            if not answer or len(answer) < 50:
                # If GPT response is too short, provide manual extraction
                return f"""Based on {len(context_parts)} documents found about '{question}':

{self._extract_key_points_from_context(context, question)}

The documents contain relevant information but may require further analysis. Consider reviewing the source documents directly for more detailed information."""
            
            return answer
            
        except Exception as e:
            logger.error("Failed to generate answer from documents", error=str(e), question=question, doc_count=len(documents))
            # Even if there's an error, try to provide something useful
            if documents:
                return f"I found {len(documents)} relevant documents about '{question}', but encountered a technical issue processing them. Please try rephrasing your question or contact support if the issue persists."
            else:
                return f"I couldn't find specific documents related to '{question}'. Try using different keywords or ask about a broader topic."

    def _extract_key_points_from_context(self, context: str, question: str) -> str:
        """Extract key points from context when GPT fails to generate a proper answer."""
        try:
            # Extract document names and key snippets
            key_points = []
            documents = context.split("**Document:")
            
            for i, doc_section in enumerate(documents[1:], 1):  # Skip first empty section
                lines = doc_section.split('\n')
                if lines:
                    doc_name = lines[0].replace('**', '').strip()
                    content = '\n'.join(lines[1:])
                    
                    # Extract first meaningful sentence or two
                    sentences = content.split('. ')
                    meaningful_content = '. '.join(sentences[:2])[:200]
                    
                    if meaningful_content.strip():
                        key_points.append(f"• **{doc_name}**: {meaningful_content}...")
            
            if key_points:
                return "\n".join(key_points[:6])  # Limit to 6 key points
            else:
                return "The documents contain technical information that may be relevant to your question."
                
        except Exception:
            return "Multiple documents were found with relevant information."

    def _search_relevant_documents(self, question: str, project_filter: Optional[str] = None) -> List[Dict]:
        """Search for documents relevant to the question."""
        try:
            # Auto-detect project from question if not provided
            if not project_filter:
                project_filter = self._extract_project_from_question(question)
                
            # If no project found but it's a date-specific question, try searching without filter first
            # then suggest being more specific
            is_date_question = self._is_date_only_question(question)
            
            # Enhanced intent detection for specific document types
            search_text = self._enhance_search_query_with_intent(question)
            
            # For project-specific queries, broaden the search terms
            if project_filter and ("project" in question.lower() or project_filter in question):
                # For project questions, search for common terms that might be in the files
                search_text = f"email OR communication OR document OR file OR DMT OR brief OR proceeding"
            
            # Convert date formats in the question to match filename patterns
            search_text = self._convert_date_formats(search_text)
            
            # Search without project filter initially since project_id field might be empty
            # Try semantic search first, with fallback to simple search
            try:
                results = self.search_client.search(
                    search_text=search_text,
                    top=50,  # Get more results for filtering
                    highlight_fields="file_name,project_title,extracted_text",  # Use correct field names
                    select=["id", "file_name", "extracted_text", "blob_url", "project_title",  # Use correct field names
                           "folder_path", "modified_date", "created_date", "file_size"],  # Use correct field names
                    query_type="semantic",  # Always use semantic search for better results
                    semantic_configuration_name="default"  # Use the semantic configuration we defined
                )
                search_type = "semantic"
            except Exception as semantic_error:
                logger.warning("Semantic search failed, falling back to simple search", error=str(semantic_error))
                # Fallback to simple search
                results = self.search_client.search(
                    search_text=search_text,
                    top=50,  # Get more results for filtering
                    highlight_fields="file_name,project_title,extracted_text",  # Use correct field names
                    select=["id", "file_name", "extracted_text", "blob_url", "project_title",  # Use correct field names
                           "folder_path", "modified_date", "created_date", "file_size"],  # Use correct field names
                    query_type="simple"  # Use simple search as fallback
                )
                search_type = "simple"
            
            logger.info("Document search completed", search_type=search_type, query=search_text)
            
            # Convert to list and filter by project if needed
            documents = []
            for result in results:
                doc_dict = dict(result)
                
                # Map field names from search result to expected format
                mapped_doc = {
                    'id': doc_dict.get('id'),
                    'filename': doc_dict.get('file_name', 'Unknown'),
                    'extracted_text': doc_dict.get('extracted_text', ''),
                    'content': doc_dict.get('extracted_text', ''),  # Map extracted_text to content for backwards compatibility
                    'blob_url': doc_dict.get('blob_url', ''),
                    'project_name': doc_dict.get('project_title', ''),
                    'folder': doc_dict.get('folder_path', ''),
                    'last_modified': doc_dict.get('modified_date', ''),
                    'created_date': doc_dict.get('created_date', ''),
                    'size': doc_dict.get('file_size', 0)
                }
                
                # If we have a project filter, check if the document belongs to that project
                if project_filter:
                    doc_project = self._extract_project_from_url(mapped_doc.get('blob_url', ''))
                    if doc_project != project_filter:
                        continue  # Skip documents not in the target project
                elif is_date_question:
                    # For date-only questions, include all matching documents but prioritize recent projects
                    pass  # Don't filter by project for date-only questions
                
                documents.append(mapped_doc)
                
                # Limit to top 10 after filtering
                if len(documents) >= 10:
                    break
            
            logger.info("Found relevant documents", count=len(documents), question=question, project_filter=project_filter)
            return documents
            
        except Exception as e:
            logger.error("Document search failed", error=str(e), question=question)
            return []
            
            logger.info("Found relevant documents", count=len(documents), question=question)
            return documents
            
        except Exception as e:
            logger.error("Document search failed", error=str(e), question=question)
            return []

    def _prepare_context(self, documents: List[Dict]) -> str:
        """Prepare context from relevant documents for GPT."""
        context_parts = []
        current_length = 0
        
        for doc in documents:
            # Extract relevant information using correct field names
            filename = doc.get('filename', 'Unknown')  # Use existing field name
            project = self._extract_project_from_url(doc.get('blob_url', '')) or doc.get('project_name', 'Unknown')  # Use existing field name
            # Use existing content field name
            content = doc.get('content', '')
            
            # Truncate content if too long
            if len(content) > 1000:
                content = content[:1000] + "..."
            
            doc_context = f"""
Document: {filename}
Project: {project}
Content: {content}
---
"""
            
            # Check if adding this document would exceed limit
            if current_length + len(doc_context) > self.max_context_length:
                break
                
            context_parts.append(doc_context)
            current_length += len(doc_context)
        
        return "\n".join(context_parts)

    def _extract_project_from_url(self, blob_url: str) -> Optional[str]:
        """Extract project ID from blob URL path like /Projects/219/219200/"""
        if not blob_url:
            return None
        
        try:
            # Look for Projects/xxx/xxxxxx pattern in URL
            import re
            match = re.search(r'/Projects/(\d+)/(\d+)/', blob_url)
            if match:
                # Return the more specific sub-project ID (219200)
                return match.group(2)
            
            # Fallback to simpler Projects/xxx pattern
            match = re.search(r'/Projects/(\d+)/', blob_url)
            if match:
                return match.group(1)
        except Exception:
            pass
        
        return None

    def _decode_document_id(self, document_id: str) -> Dict[str, str]:
        """Decode Base64 document ID to extract file path, filename, and project info."""
        result = {
            'full_path': '',
            'filename': '',
            'project_id': '',
            'folder_path': ''
        }
        
        if not document_id:
            return result
            
        try:
            import base64
            import urllib.parse
            import os
            
            # Try to decode as Base64
            decoded_bytes = base64.b64decode(document_id + '==')  # Add padding if needed
            decoded_url = decoded_bytes.decode('utf-8')
            
            # Extract the path part after the domain
            if 'dtce-documents/' in decoded_url:
                path_part = decoded_url.split('dtce-documents/')[-1]
                result['full_path'] = path_part
                
                # URL decode the path
                decoded_path = urllib.parse.unquote(path_part)
                result['full_path'] = decoded_path
                
                # Extract filename (last part of path, excluding .keep files)
                path_parts = decoded_path.split('/')
                if path_parts and path_parts[-1] and path_parts[-1] != '.keep':
                    result['filename'] = path_parts[-1]
                elif len(path_parts) > 1 and path_parts[-2]:
                    # If last part is .keep, use the folder name
                    result['filename'] = path_parts[-2]
                
                # Extract project ID from path (Projects/219/219359 pattern)
                if 'Projects/' in decoded_path:
                    project_part = decoded_path.split('Projects/')[-1]
                    project_parts = project_part.split('/')
                    if len(project_parts) >= 2:
                        result['project_id'] = project_parts[1]  # The specific project ID (e.g., 219359)
                    elif len(project_parts) >= 1:
                        result['project_id'] = project_parts[0]  # Fallback to first part
                
                # Extract folder path (everything except filename)
                if '/' in decoded_path:
                    result['folder_path'] = '/'.join(decoded_path.split('/')[:-1])
                    
        except Exception as e:
            # If Base64 decoding fails, try other extraction methods
            try:
                import re
                # Look for Projects_xxx_xxxxxx pattern in ID
                match = re.search(r'Projects_(\d+)_(\d+)_', document_id)
                if match:
                    result['project_id'] = match.group(2)  # Return the more specific project ID
                else:
                    # Fallback to Projects_xxx pattern
                    match = re.search(r'Projects_(\d+)_', document_id)
                    if match:
                        result['project_id'] = match.group(1)
            except:
                pass
        
        return result

    def _extract_document_info(self, document: Dict) -> Dict[str, str]:
        """Extract comprehensive document information including filename and project."""
        info = {
            'filename': 'Unknown',
            'project_id': '',
            'project_name': '',  # Add project_name back
            'folder_path': '',
            'full_path': ''
        }
        
        # Start with existing fields from search result
        if document.get('filename'):
            info['filename'] = document['filename']
        if document.get('project_name'):
            info['project_name'] = document['project_name']
            info['project_id'] = document['project_name']  # Keep both for backward compatibility
        
        # Try to get better info from decoded Base64 ID (this has the most accurate info)
        document_id = document.get('id', '')
        if document_id:
            decoded_info = self._decode_document_id(document_id)
            
            # Use decoded filename if we don't have one or it's better
            if decoded_info['filename'] and (not info['filename'] or info['filename'] == 'Unknown'):
                info['filename'] = decoded_info['filename']
            
            # Use decoded project info - this is usually more accurate than search fields
            if decoded_info['project_id']:
                info['project_id'] = decoded_info['project_id']
                if not info['project_name']:  # Only override if we don't have it from search
                    info['project_name'] = decoded_info['project_id']
            
            # Always use the path info from decoded ID
            info['folder_path'] = decoded_info['folder_path']
            info['full_path'] = decoded_info['full_path']
        
        # Fallback methods for project extraction if still missing
        if not info['project_id'] and not info['project_name']:
            # Try extracting from blob_url
            project_from_url = self._extract_project_from_url(document.get('blob_url', ''))
            if project_from_url:
                info['project_id'] = project_from_url
                info['project_name'] = project_from_url
            
            # Try extracting from content (look for project numbers)
            content = document.get('content', '')
            if content:
                try:
                    import re
                    # Look for patterns like "219324", "2BC221295", "221285" in content
                    project_patterns = [
                        r'\b(2[A-Z]{2}\d{6})\b',  # 2BC221295 format
                        r'\b(\d{6})\b',           # 6-digit numbers
                        r'\b(Project\s+\d+)\b'    # "Project 123" format
                    ]
                    
                    for pattern in project_patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            info['project_id'] = matches[0]
                            info['project_name'] = matches[0]  # Keep both consistent
                            break
                except:
                    pass
        
        return info

    def _extract_project_from_document(self, document: Dict) -> str:
        """Extract project ID from document using multiple methods."""
        # Use the comprehensive extraction method
        doc_info = self._extract_document_info(document)
        return doc_info['project_id'] or 'Unknown'

    def _generate_meaningful_filename(self, document: Dict) -> str:
        """Generate a meaningful filename from document content when filename is missing."""
        content = document.get('content', '')
        
        if not content:
            return 'Unknown Document'
        
        # Look for common document patterns
        content_lower = content.lower()
        
        # Check for specific document types
        if 'wind zones' in content_lower or 'wind load' in content_lower:
            return 'Wind Load Analysis'
        elif 'correspondence' in content_lower or 'from:' in content_lower:
            return 'Project Correspondence'
        elif 'building consent' in content_lower:
            return 'Building Consent Documentation'
        elif 'council' in content_lower and ('query' in content_lower or 'response' in content_lower):
            return 'Council Correspondence'
        elif 'engineering report' in content_lower or 'technical report' in content_lower:
            return 'Engineering Report'
        elif 'design guide' in content_lower:
            return 'Design Guide'
        elif 'timber building' in content_lower:
            return 'Timber Building Guide'
        elif 'consenting' in content_lower:
            return 'Consenting Documentation'
        elif 'ps1' in content_lower or 'ps3' in content_lower or 'producer statement' in content_lower:
            return 'Producer Statement'
        elif 'concept design' in content_lower:
            return 'Concept Design Report'
        
        # Look for subject lines in emails
        import re
        subject_match = re.search(r'subject:\s*([^\n\r]+)', content, re.IGNORECASE)
        if subject_match:
            subject = subject_match.group(1).strip()
            if len(subject) > 10 and len(subject) < 80:  # Reasonable subject length
                return f"Email: {subject}"
        
        # Look for document titles
        title_patterns = [
            r'^([A-Z][^\n\r]{10,60})\n',  # Title-like first lines
            r'FOR\s+([^\n\r]{10,60})\n',  # "FOR ..." patterns
            r'RE:\s*([^\n\r]{5,60})\n'    # "RE: ..." patterns
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, content[:200], re.MULTILINE)
            if match:
                title = match.group(1).strip()
                if title and not title.lower().startswith('page '):
                    return title[:50] + ('...' if len(title) > 50 else '')
        
        return 'Document Content'

    def _extract_project_from_question(self, question: str) -> Optional[str]:
        """Extract project number from question text."""
        if not question:
            return None
        
        try:
            import re
            # Look for 6-digit project numbers (like 219200)
            match = re.search(r'\b(\d{6})\b', question)
            if match:
                return match.group(1)
            
            # Look for project patterns like "project 219" 
            match = re.search(r'project\s+(\d{3,6})', question.lower())
            if match:
                return match.group(1)
            
            # Look for any 3+ digit numbers that could be projects
            match = re.search(r'\b(\d{3,6})\b', question)
            if match:
                return match.group(1)
        except Exception:
            pass
        
        return None

    def _convert_date_formats(self, text: str) -> str:
        """Convert natural language dates to the format used in filenames (YY MM DD)"""
        patterns = [
            (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', self._convert_full_date),
            (r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', self._convert_slash_date),
            (r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', self._convert_dash_date),
        ]
        
        converted_text = text
        for pattern, converter in patterns:
            converted_text = re.sub(pattern, converter, converted_text)
        
        return converted_text
    
    def _convert_full_date(self, match):
        """Convert 'January 7, 2019' to '19 01 07'"""
        month_name, day, year = match.groups()
        month_map = {
            'January': '01', 'February': '02', 'March': '03', 'April': '04',
            'May': '05', 'June': '06', 'July': '07', 'August': '08',
            'September': '09', 'October': '10', 'November': '11', 'December': '12'
        }
        month = month_map[month_name]
        year_short = year[-2:]  # Get last 2 digits
        day_padded = day.zfill(2)  # Pad with leading zero if needed
        return f"{year_short} {month} {day_padded}"
    
    def _convert_slash_date(self, match):
        """Convert '1/7/2019' to '19 01 07'"""
        month, day, year = match.groups()
        year_short = year[-2:]
        month_padded = month.zfill(2)
        day_padded = day.zfill(2)
        return f"{year_short} {month_padded} {day_padded}"
    
    def _convert_dash_date(self, match):
        """Convert '1-7-2019' to '19 01 07'"""
        month, day, year = match.groups()
        year_short = year[-2:]
        month_padded = month.zfill(2)
        day_padded = day.zfill(2)
        return f"{year_short} {month_padded} {day_padded}"

    def _is_date_only_question(self, question: str) -> bool:
        """Check if question is primarily about dates without project context."""
        if not question:
            return False
        
        try:
            import re
            question_lower = question.lower()
            
            # Check for date patterns without project numbers
            has_date = any([
                re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', question_lower),
                re.search(r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b', question_lower),
                re.search(r'\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b', question_lower)
            ])
            
            has_project = re.search(r'\b(project|219200|\d{6})\b', question_lower)
            
            return has_date and not has_project
            
        except Exception:
            return False

    async def _generate_answer(self, question: str, context: str) -> Dict[str, Any]:
        """Generate answer using GPT with document context."""
        try:
            import time
            start_time = time.time()
            
            # Prepare enhanced system prompt for comprehensive question answering
            system_prompt = """You are an advanced AI assistant for DTCE (engineering consultancy) that can answer ALL types of questions using available documentation and professional knowledge.

            YOUR CAPABILITIES:
            1. DOCUMENT-BASED ANSWERS: Answer questions using the provided document context
            2. BUSINESS PROCESS GUIDANCE: Provide advice on business processes, procedures, and workflows
            3. ENGINEERING EXPERTISE: Answer technical engineering questions
            4. ADMINISTRATIVE SUPPORT: Help with office procedures, software usage, and administrative tasks
            5. GENERAL PROFESSIONAL ADVICE: Provide reasonable professional guidance when documents don't contain the answer

            QUESTION TYPES YOU HANDLE:
            - Engineering: specifications, calculations, reports, drawings, project details
            - Business Processes: WorkflowMax, billing, time entry, invoicing, project management
            - Administrative: procedures, guidelines, company policies, software usage
            - Project Management: scheduling, communication, client relations
            - Financial: fee structures, billing procedures, cost estimation
            - General Professional: best practices, recommendations, troubleshooting

            CRITICAL RESTRICTIONS:
            - NEVER create, invent, or make up project numbers, job numbers, or file names
            - NEVER create or mention URLs unless they are explicitly provided in the context
            - ONLY reference specific documents, projects, or files that are actually mentioned in the context
            - If you don't have specific information, provide general guidance instead

            RESPONSE STRATEGY:
            1. PRIMARY: Always use document context when available - cite specific documents and extract useful information
            2. NEVER say documents don't contain relevant information if documents are provided
            3. If documents contain partial information, extract what's useful and supplement with professional guidance
            4. Always be helpful and provide actionable advice
            5. For business process questions (like WorkflowMax), provide step-by-step guidance
            6. For technical questions, extract what you can from documents and provide additional context

            EXAMPLE APPROACHES:
            - "Based on the documents provided..." (when using document context)
            - "From the project files, I can see..." (extracting specific information)
            - "The documents show... and additionally, here's the recommended approach..." (combination approach)
            """
            
            # Prepare enhanced user prompt
            user_prompt = f"""
            Question: {question}

            Available Document Context:
            {context if context.strip() else "No specific documents found for this query."}

            CRITICAL INSTRUCTIONS:
            - ONLY use information that is explicitly provided in the document context above
            - NEVER create, invent, or make up project numbers, job numbers, or file names
            - NEVER create or mention URLs unless they are explicitly provided in the context
            - If documents contain relevant information, use them as your primary source and cite specific details
            - If documents don't contain the answer, provide professional guidance and best practices
            - For business process questions (WorkflowMax, billing, etc.), provide step-by-step guidance
            - For technical questions, suggest where to find additional information if needed
            - Always be helpful and provide actionable advice
            - Be specific and detailed in your response

            Please provide a comprehensive answer addressing the question above.
            """
            
            # Call OpenAI/Azure OpenAI with enhanced parameters
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Slightly higher for more creative business guidance
                max_tokens=800   # Increased for more comprehensive answers
            )
            
            answer = response.choices[0].message.content
            processing_time = time.time() - start_time
            
            # Determine confidence based on response characteristics
            confidence = self._assess_confidence(answer, context)
            
            logger.info("Generated answer", 
                       question=question, 
                       answer_length=len(answer),
                       confidence=confidence,
                       processing_time=processing_time)
            
            return {
                'answer': answer,
                'confidence': confidence,
                'processing_time': processing_time
            }
            
        except Exception as e:
            logger.error("Answer generation failed", error=str(e), question=question)
            return {
                'answer': 'I encountered an error while generating the answer.',
                'confidence': 'error',
                'processing_time': 0
            }

    def _assess_confidence(self, answer: str, context: str) -> str:
        """Assess confidence level of the answer."""
        # Check for explicit disclaimers that indicate low confidence
        low_confidence_phrases = [
            "I cannot find", "not available", "not provided", "unclear from the documents",
            "insufficient information", "cannot determine"
        ]
        
        # Check if answer contains any low confidence indicators
        answer_lower = answer.lower()
        if any(phrase in answer_lower for phrase in low_confidence_phrases):
            return 'low'
        
        # Assess based on context and answer quality
        if len(context) > 2000 and len(answer) > 200:
            return 'high'
        elif len(context) > 500 and len(answer) > 100:
            return 'medium'
        elif len(context) > 0 and len(answer) > 50:
            return 'medium'  # Even with some context, give medium confidence
        else:
            return 'low'

    def _format_sources(self, documents: List[Dict]) -> List[Dict[str, Any]]:
        """Format document sources for API response."""
        sources = []
        for doc in documents:
            blob_url = doc.get('blob_url', '')
            # Convert blob URL to SuiteFiles URL for direct access
            suitefiles_url = self._get_safe_suitefiles_url(blob_url)
            
            source = {
                'filename': doc.get('filename', 'Unknown'),
                'url': suitefiles_url,  # Use converted SuiteFiles URL
                'project': self._extract_project_from_url(blob_url) or doc.get('project_name', 'Unknown'),
                'content_preview': doc.get('content', '')[:200] + "..." if doc.get('content', '') else "",
                'last_modified': doc.get('last_modified', ''),
                'folder': doc.get('folder', '')
            }
            sources.append(source)
        return sources

    async def get_document_summary(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a summary of available documents for a project or all projects."""
        try:
            # Search for all documents or project-specific documents
            search_filter = f"project_name eq '{project_id}'" if project_id else None
            
            results = self.search_client.search(
                search_text="*",
                top=100,
                filter=search_filter,
                select=["filename", "project_name", "folder", "content_type", "last_modified"]
            )
            
            # Analyze documents
            documents = list(results)
            doc_types = {}
            projects = set()
            
            for doc in documents:
                # Count document types
                content_type = doc.get('content_type', 'unknown')
                doc_types[content_type] = doc_types.get(content_type, 0) + 1
                
                # Collect projects using proper Base64 decoding
                doc_info = self._extract_document_info(doc)
                project = doc_info['project_name'] or doc_info['project_id']  # Smart: use project_name for display
                if project:
                    projects.add(project)
            
            # Create latest documents list with proper Base64 decoding
            latest_docs = []
            for doc in sorted(documents, key=lambda x: x.get('last_modified', ''), reverse=True)[:5]:
                doc_info = self._extract_document_info(doc)
                latest_docs.append({
                    'filename': doc_info['filename'] or 'Unknown',
                    'project': doc_info['project_name'] or doc_info['project_id'] or 'Unknown',  # Smart: prefer project_name
                    'last_modified': doc.get('last_modified', '')
                })
            
            return {
                'total_documents': len(documents),
                'document_types': doc_types,
                'projects': sorted(list(projects)),
                'latest_documents': latest_docs
            }
            
        except Exception as e:
            logger.error("Document summary failed", error=str(e))
            return {'error': str(e)}

    def _is_project_keyword_query(self, question: str) -> bool:
        """Check if the question is asking for past projects using specific engineering keywords."""
        if not question:
            return False
        
        question_lower = question.lower()
        
        # Engineering/structural keywords
        engineering_keywords = [
            # Precast & Concrete
            "precast", "pre-cast", "precast panel", "precast connection", 
            "unispans", "unispan", "precast element", "precast unit",
            "precast concrete", "prefab", "prefabricated", "concrete",
            "reinforced concrete", "cast in place", "cast-in-place",
            
            # Timber & Wood
            "timber", "wood", "wooden", "timber frame", "timber framed",
            "timber retaining", "timber structure", "glulam", "lvl",
            "plywood", "timber beam", "timber column", "timber wall",
            
            # Steel & Metal
            "steel", "steel frame", "steel structure", "metal", "aluminum",
            "steel beam", "steel column", "structural steel", "cold-formed",
            
            # Structural Elements
            "retaining wall", "foundation", "footing", "pile", "beam",
            "column", "slab", "wall", "roof", "truss", "portal frame",
            "cantilever", "span", "connection", "joint", "bracket",
            
            # Building Types
            "residential", "commercial", "industrial", "warehouse",
            "office", "retail", "apartment", "house", "building",
            "structure", "facility", "development"
        ]
        
        # Project/work-related terms
        project_patterns = [
            "project", "job", "work", "contract", "site", "construction",
            "past", "previous", "historical", "archive", "record",
            "scope", "experience", "portfolio", "case", "example",
            "reference", "similar", "done before", "worked on"
        ]
        
        # Intent/action terms (what user wants to do)
        intent_patterns = [
            "tell me", "show me", "find", "search", "list", "all",
            "what", "which", "where", "give me", "provide", "display",
            "help", "assist", "looking for", "need", "want", "advise"
        ]
        
        # Check for engineering keywords
        has_engineering_keywords = any(keyword in question_lower for keyword in engineering_keywords)
        
        # Check for project/work context
        has_project_context = any(pattern in question_lower for pattern in project_patterns)
        
        # Check for request/intent
        has_intent = any(pattern in question_lower for pattern in intent_patterns)
        
        # Also check for plural forms and question words
        has_multiple_indicator = any(word in question_lower for word in ["all", "any", "every", "what", "which"])
        
        # Return true if we have engineering keywords AND (project context OR clear intent to find multiple items)
        return has_engineering_keywords and (has_project_context or (has_intent and has_multiple_indicator))

    def _is_precast_project_query(self, question: str) -> bool:
        """Check if the question is specifically asking for precast panel projects (legacy method)."""
        if not question:
            return False
        
        question_lower = question.lower()
        
        # Precast-specific terms
        precast_patterns = [
            "precast", "pre-cast", "precast panel", "precast connection", 
            "unispans", "unispan", "precast element", "precast unit",
            "precast concrete", "prefab", "prefabricated"
        ]
        
        # Check if it has precast terms and is a project search
        has_precast = any(pattern in question_lower for pattern in precast_patterns)
        
        if has_precast:
            return self._is_project_keyword_query(question)
        
        return False
        
    async def _handle_keyword_project_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle keyword-based project queries with specialized search and SuiteFiles URLs."""
        try:
            logger.info("Processing keyword project query", question=question)
            
            # Check if this is a specific project number query (e.g., "project 225", "225", "Project 219359")
            specific_project = self._extract_specific_project_number(question)
            if specific_project:
                logger.info("Detected specific project number query", project_number=specific_project)
                return await self._handle_specific_project_query(specific_project, question)
            
            # Check if this is a scenario-based project query (building type + conditions + location)
            if self._is_scenario_based_project_query(question):
                return await self._handle_scenario_project_query(question, project_filter)
            
            # USE ENHANCED INTENT DETECTION for better search precision
            enhanced_search_query = self._enhance_search_query_with_intent(question)
            
            # Check if this is a specific document type request (like bridge drawings)
            question_lower = question.lower()
            specific_doc_requests = {
                'bridge': 'bridge drawings, calculations, or project documents',
                'building': 'building drawings, plans, or structural documents', 
                'road': 'road design drawings, alignment plans, or pavement documents',
                'retaining wall': 'retaining wall drawings, calculations, or structural details',
                'foundation': 'foundation drawings, pile designs, or geotechnical documents',
                'water': 'water system drawings, hydraulic calculations, or drainage plans',
                'culvert': 'culvert drawings, hydraulic designs, or structural details'
            }
            
            # Check if this is a specific document type request
            doc_type_found = None
            for doc_type, description in specific_doc_requests.items():
                if doc_type in question_lower:
                    doc_type_found = (doc_type, description)
                    break
            
            # If enhanced query is different from original, use enhanced search approach
            if enhanced_search_query != question:
                logger.info("Using enhanced intent-based search", 
                           original=question, enhanced=enhanced_search_query, doc_type=doc_type_found[0] if doc_type_found else None)
                
                # Use enhanced search query for more precise results
                enhanced_docs = self._search_documents_with_enhanced_query(enhanced_search_query)
                
                if not enhanced_docs and doc_type_found:
                    # No specific documents found - provide helpful response
                    doc_type, description = doc_type_found
                    return {
                        'answer': f"""I couldn't find any {description} in our current document database.

🔍 **What this means:**
- We may not have {doc_type} projects currently indexed in our system
- The documents might be stored in different folders or with different naming conventions
- Our document indexing may still be in progress

💡 **Suggestions:**
1. **Check project-specific folders** - Try searching for a specific project number if you know it
2. **Use broader terms** - Try searching for "structural drawings" or "engineering plans" instead
3. **Contact the team** - Our engineering team can help locate specific {doc_type} documents
4. **General guidance** - I can provide general engineering guidance about {doc_type} design and best practices

Would you like me to provide general engineering guidance about {doc_type} projects, or would you prefer to search for a specific project?""",
                        'sources': [],
                        'confidence': 'medium',
                        'documents_searched': 0,
                        'search_type': 'enhanced_intent_no_results'
                    }
                elif enhanced_docs:
                    # Found documents with enhanced search - format as project list
                    projects_found = self._group_documents_by_project(enhanced_docs)
                    return {
                        'answer': self._format_keyword_project_answer(projects_found, [enhanced_search_query]),
                        'sources': self._format_keyword_sources(projects_found, enhanced_docs),
                        'confidence': 'high' if len(projects_found) >= 3 else 'medium',
                        'documents_searched': len(enhanced_docs),
                        'search_type': 'enhanced_intent_project_search'
                    }
            
            # Fallback to original keyword extraction approach
            keywords = self._extract_keywords_from_question(question)
            
            # Search for keyword-related documents
            keyword_docs = self._search_keyword_documents(keywords)
            
            if not keyword_docs:
                return {
                    'answer': f'I could not find any projects related to {", ".join(keywords)} in our document index.',
                    'sources': [],
                    'confidence': 'medium',
                    'documents_searched': 0
                }
            
            # Extract unique projects from the documents
            projects_found = self._extract_keyword_projects(keyword_docs, keywords)
            
            if not projects_found:
                return {
                    'answer': f'I found documents related to {", ".join(keywords)} but could not identify specific project numbers.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': len(keyword_docs)
                }
            
            # Format the answer and sources
            answer = self._format_keyword_project_answer(projects_found, keywords)
            sources = self._format_keyword_sources(projects_found, keyword_docs)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',
                'documents_searched': len(keyword_docs)
            }
            
        except Exception as e:
            logger.error("Keyword project query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for keyword-related projects.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _is_scenario_based_project_query(self, question: str) -> bool:
        """Detect if this is a scenario-based project query (building type + conditions + location)."""
        question_lower = question.lower()
        
        # Look for combinations of building types, conditions, and technical systems
        building_indicators = ['buildings', 'building', 'houses', 'house', 'apartment', 'mid-rise', 'structures']
        condition_indicators = ['high wind', 'steep slope', 'coastal', 'seismic', 'wind zone', 'earthquake']
        location_indicators = ['wellington', 'auckland', 'christchurch', 'coastal', 'zone']
        system_indicators = ['foundation', 'shear wall', 'timber frame', 'connection', 'balcony', 'steel', 'concrete']
        
        has_building = any(term in question_lower for term in building_indicators)
        has_condition = any(term in question_lower for term in condition_indicators)
        has_location = any(term in question_lower for term in location_indicators)
        has_system = any(term in question_lower for term in system_indicators)
        
        # Scenario-based if it has at least 2 of these components
        components_count = sum([has_building, has_condition, has_location, has_system])
        
        return components_count >= 2
    
    async def _handle_scenario_project_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle complex scenario-based project queries."""
        try:
            logger.info("Processing scenario-based project query", question=question)
            
            # Extract scenario components
            scenario_components = self._extract_scenario_components(question)
            
            # Use scenario search logic
            search_terms = self._build_scenario_search_terms(question, scenario_components)
            relevant_docs = self._search_scenario_documents(search_terms, scenario_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific examples matching your criteria: {scenario_components.get('summary', question)}. Try searching for broader terms or check if there are similar projects with different conditions.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'scenario_project'
                }
            
            # Generate project-focused answer with SuiteFiles links
            answer = await self._generate_scenario_project_answer(question, relevant_docs, scenario_components)
            sources = self._format_scenario_sources(relevant_docs, scenario_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'scenario_project',
                'scenario_components': scenario_components
            }
            
        except Exception as e:
            logger.error("Scenario project query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for scenario-based project examples.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _generate_scenario_project_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a project-focused answer for scenario-based queries with SuiteFiles links."""
        if not documents:
            return "No matching project examples found for your scenario criteria."
        
        # Extract unique projects
        projects_found = {}
        for doc in documents:
            project_id = self._extract_project_from_document(doc)
            if project_id not in projects_found:
                projects_found[project_id] = {
                    'documents': [],
                    'scenario_score': 0
                }
            
            projects_found[project_id]['documents'].append(doc)
            # Use the highest scenario score for the project
            projects_found[project_id]['scenario_score'] = max(
                projects_found[project_id]['scenario_score'],
                doc.get('scenario_score', 0)
            )
        
        # Sort projects by scenario relevance
        sorted_projects = sorted(projects_found.items(), 
                               key=lambda x: x[1]['scenario_score'], 
                               reverse=True)
        
        # Build answer with project links
        answer_parts = []
        answer_parts.append(f"I found **{len(sorted_projects)} projects** matching your scenario criteria: {components['summary']}")
        answer_parts.append("")
        
        for project_id, project_data in sorted_projects[:5]:  # Top 5 projects
            doc_count = len(project_data['documents'])
            scenario_score = project_data['scenario_score']
            
            # Build SuiteFiles project link
            project_url = f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{project_id}"
            
            answer_parts.append(f"• **Project {project_id}** - {doc_count} documents (Match Score: {scenario_score:.1f})")
            answer_parts.append(f"  📁 [View Project Files]({project_url})")
            
            # Add brief description of what was found
            sample_doc = project_data['documents'][0]
            if sample_doc.get('content'):
                preview = sample_doc['content'][:100].replace('\n', ' ')
                answer_parts.append(f"  📝 Preview: {preview}...")
            
            answer_parts.append("")
        
        answer_parts.append("💡 **Tip:** Click the project links to access all related documents in SuiteFiles.")
        
        return "\n".join(answer_parts)

    def _extract_keywords_from_question(self, question: str) -> List[str]:
        """Extract relevant engineering keywords from the question."""
        if not question:
            return []
        
        question_lower = question.lower()
        found_keywords = []
        
        # Define keyword categories with their variations
        keyword_categories = {
            "precast": ["precast", "pre-cast", "precast panel", "precast connection", "unispans", "unispan", "prefab", "prefabricated", "precast concrete", "precast element", "precast beam", "precast slab"],
            "timber": ["timber", "wood", "wooden", "timber frame", "timber framed", "timber retaining", "glulam", "lvl"],
            "concrete": ["concrete", "reinforced concrete", "cast in place", "cast-in-place", "concrete building"],
            "steel": ["steel", "steel frame", "steel structure", "structural steel", "cold-formed"],
            "retaining wall": ["retaining wall", "retaining", "wall"],
            "building": ["building", "structure", "storey", "story", "residential", "commercial", "warehouse"]
        }
        
        # Find which categories match
        for category, terms in keyword_categories.items():
            if any(term in question_lower for term in terms):
                found_keywords.append(category)
        
        # Also extract explicit keywords mentioned in the question
        explicit_keywords = []
        for word in question.split():
            word_clean = word.strip('.,!?:;()[]"').lower()
            if word_clean in ["precast", "timber", "concrete", "steel", "retaining", "wall", "building", "unispans"]:
                explicit_keywords.append(word_clean)
        
        # Combine and deduplicate
        all_keywords = list(set(found_keywords + explicit_keywords))
        return all_keywords if all_keywords else ["structural", "engineering"]  # fallback

    def _extract_specific_project_number(self, question: str) -> Optional[str]:
        """Extract specific project number from queries like 'project 225', '225', 'Project 219359'."""
        import re
        
        question_lower = question.lower().strip()
        
        # Pattern 1: "project 225", "project225"
        match = re.search(r'project\s*(\d+)', question_lower)
        if match:
            return match.group(1)
        
        # Pattern 2: Just a number by itself "225" or "219359"
        if re.match(r'^\d+$', question.strip()):
            return question.strip()
        
        # Pattern 3: "225 project", "219359 project"
        match = re.search(r'(\d+)\s*project', question_lower)
        if match:
            return match.group(1)
        
        return None

    async def _handle_specific_project_query(self, project_number: str, original_question: str) -> Dict[str, Any]:
        """Handle queries for a specific project number."""
        try:
            logger.info("Searching for specific project", project_number=project_number)
            
            # Search for documents with this exact project number
            # Use multiple comprehensive search patterns to catch all variations
            search_patterns = [
                f'Projects/{project_number}',  # Folder path: Projects/225
                f'Projects/{project_number}/',  # Folder path with trailing slash
                f'/{project_number}/',  # Between slashes in path
                f'{project_number}*',  # Wildcard for sub-projects like 225006, 225066
                project_number,  # Just the number
            ]
            
            # For shorter project numbers (like "225"), also search for longer variations
            if len(project_number) <= 3:
                # Add patterns for common extensions like 225000, 225001, etc.
                for i in range(10):
                    extended_number = f"{project_number}00{i}"
                    search_patterns.append(f'Projects/{extended_number}')
                    search_patterns.append(f'/{extended_number}/')
            
            all_docs = []
            for pattern in search_patterns:
                try:
                    # Use wildcard search for better matching
                    results = self.search_client.search(
                        search_text=pattern,
                        top=100,  # Increased to get more results
                        select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                        query_type="simple",
                        search_mode="any"  # Match any of the terms
                    )
                    
                    for result in results:
                        doc_dict = dict(result)
                        blob_url = doc_dict.get('blob_url', '')
                        
                        # Check if this document actually belongs to the requested project
                        if self._document_belongs_to_project(blob_url, project_number):
                            all_docs.append(doc_dict)
                            
                except Exception as e:
                    logger.warning("Search pattern failed", pattern=pattern, error=str(e))
                    continue
            
            # Remove duplicates
            unique_docs = {}
            for doc in all_docs:
                doc_id = doc.get('id', '')
                if doc_id and doc_id not in unique_docs:
                    unique_docs[doc_id] = doc
            
            project_docs = list(unique_docs.values())
            
            if not project_docs:
                return {
                    'answer': f'I could not find any documents for Project {project_number}. Please verify the project number is correct.',
                    'sources': [],
                    'confidence': 'high',
                    'documents_searched': 0,
                    'search_type': 'specific_project'
                }
            
            # Format the specific project response
            answer = self._format_specific_project_answer(project_number, project_docs)
            sources = self._format_specific_project_sources(project_number, project_docs)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',
                'documents_searched': len(project_docs),
                'search_type': 'specific_project'
            }
            
        except Exception as e:
            logger.error("Specific project query failed", error=str(e), project_number=project_number)
            return {
                'answer': f'I encountered an error while searching for Project {project_number}.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'search_type': 'specific_project'
            }

    def _document_belongs_to_project(self, blob_url: str, project_number: str) -> bool:
        """Check if a document belongs to the specified project number."""
        if not blob_url or not project_number:
            return False
        
        blob_url_lower = blob_url.lower()
        project_lower = project_number.lower()
        
        # Check for direct project path patterns
        project_patterns = [
            f'/projects/{project_lower}/',
            f'/projects/{project_lower}/',
            f'projects/{project_lower}/',
            f'projects\\{project_lower}\\',  # Windows path separators
        ]
        
        # For shorter project numbers (like "225"), also check subproject patterns
        if len(project_number) <= 3:
            # "225" should match "225000", "225006", "225066", etc.
            for i in range(1000):  # Check up to 225999
                extended_number = f"{project_number}{i:03d}"
                project_patterns.extend([
                    f'/projects/{extended_number}/',
                    f'projects/{extended_number}/',
                    f'projects\\{extended_number}\\',
                ])
                
            # Also check for the pattern Projects/225/225xxx/
            project_patterns.extend([
                f'/projects/{project_lower}/{project_lower}',
                f'projects/{project_lower}/{project_lower}',
            ])
        
        # Check if any pattern matches
        for pattern in project_patterns:
            if pattern in blob_url_lower:
                return True
        
        # Fallback: Extract project using the existing method
        extracted_project = self._extract_project_from_url(blob_url)
        if not extracted_project:
            return False
        
        # Exact match
        if extracted_project == project_number:
            return True
        
        # For shorter project numbers, check if they appear as prefix
        if len(project_number) <= 3:
            return extracted_project.startswith(project_number)
        
        return False

    def _format_specific_project_answer(self, project_number: str, project_docs: List[Dict]) -> str:
        """Format the answer for a specific project query."""
        if len(project_docs) == 0:
            return f"No documents found for Project {project_number}."
        
        answer_parts = [
            f"🎯 **Project {project_number}**",
            "",
            f"I found **{len(project_docs)} documents** across multiple subfolders:",
            ""
        ]
        
        # Group documents by project subfolder AND document type
        folder_groups = {}
        for doc in project_docs:
            blob_url = doc.get('blob_url', '')
            filename = doc.get('filename', 'Unknown')
            
            # Extract subfolder from blob URL (e.g., Projects/225/225006/documents/)
            subfolder = self._extract_subfolder_from_url(blob_url, project_number)
            
            if subfolder not in folder_groups:
                folder_groups[subfolder] = {
                    "📄 Reports & Documents": [],
                    "📊 Spreadsheets & Calculations": [],
                    "📐 Drawings": [],
                    "🖼️ Images": [],
                    "📁 Other Files": []
                }
            
            # Determine document type
            if filename.lower().endswith(('.pdf', '.doc', '.docx')):
                doc_type = "📄 Reports & Documents"
            elif filename.lower().endswith(('.xls', '.xlsx', '.xlsm')):
                doc_type = "📊 Spreadsheets & Calculations"
            elif filename.lower().endswith(('.dwg', '.dxf')):
                doc_type = "📐 Drawings"
            elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                doc_type = "🖼️ Images"
            else:
                doc_type = "📁 Other Files"
            
            folder_groups[subfolder][doc_type].append(doc)
        
        # Display documents organized by subfolder
        for subfolder, doc_types in sorted(folder_groups.items()):
            total_docs_in_folder = sum(len(docs) for docs in doc_types.values())
            if total_docs_in_folder > 0:
                answer_parts.append(f"**📂 {subfolder}** ({total_docs_in_folder} files)")
                
                for doc_type, docs in doc_types.items():
                    if docs:  # Only show types that have documents
                        answer_parts.append(f"  {doc_type}")
                        
                        # Show first 5 files per type per folder, then summarize
                        for doc in docs[:5]:
                            filename = doc.get('filename', 'Unknown')
                            blob_url = doc.get('blob_url', '')
                            suite_files_url = self._get_safe_suitefiles_url(blob_url)
                            
                            if suite_files_url and suite_files_url != "Document link not available":
                                answer_parts.append(f"    • [{filename}]({suite_files_url})")
                            else:
                                answer_parts.append(f"    • {filename}")
                        
                        if len(docs) > 5:
                            answer_parts.append(f"    • ... and {len(docs) - 5} more {doc_type.split(' ')[1].lower()}")
                
                answer_parts.append("")  # Space between subfolders
        
        # Summary and tip
        answer_parts.extend([
            "💡 **Tips:**",
            "• Click any file link above to open it directly in SuiteFiles",
            "• This shows all documents found for your requested project",
            f"• Total: {len(project_docs)} documents across all subfolders"
        ])
        
        return "\n".join(answer_parts)

    def _extract_subfolder_from_url(self, blob_url: str, project_number: str) -> str:
        """Extract the subfolder name from a blob URL for a specific project."""
        if not blob_url:
            return "Unknown Folder"
        
        try:
            # Example URL: /Projects/225/225006/documents/file.pdf
            # We want to extract "225006" or "225006/documents"
            
            if f'/{project_number}/' in blob_url or f'\\{project_number}\\' in blob_url:
                # Find the part after the main project number
                parts = blob_url.replace('\\', '/').split('/')
                project_index = -1
                
                for i, part in enumerate(parts):
                    if part == project_number:
                        project_index = i
                        break
                
                if project_index >= 0 and project_index + 1 < len(parts):
                    # Get the subfolder (next part after project number)
                    subfolder = parts[project_index + 1]
                    if subfolder and subfolder != project_number:
                        return f"Project {subfolder}"
                    
            # Fallback: try to extract any project-like number from the path
            import re
            match = re.search(rf'/({project_number}\d+)/', blob_url)
            if match:
                return f"Project {match.group(1)}"
                
            return f"Project {project_number} (Main Folder)"
            
        except Exception:
            return f"Project {project_number} (Unknown Subfolder)"

    def _format_specific_project_sources(self, project_number: str, project_docs: List[Dict]) -> List[Dict[str, Any]]:
        """Format sources for a specific project query."""
        sources = []
        
        for doc in project_docs[:20]:  # Limit sources
            blob_url = doc.get('blob_url', '')
            suite_files_url = self._get_safe_suitefiles_url(blob_url)
            
            source = {
                'title': doc.get('filename', 'Unknown'),
                'content': (doc.get('content', '') or '')[:200] + "..." if doc.get('content') else "",
                'url': suite_files_url,
                'project': project_number,
                'relevance_score': 1.0  # High relevance for specific project match
            }
            sources.append(source)
        
        return sources

    def _convert_to_suitefiles_url(self, blob_url: str, link_type: str = "file") -> Optional[str]:
        """Convert Azure blob URL to SuiteFiles URL for file or folder navigation.
        
        Args:
            blob_url: The Azure blob storage URL
            link_type: Either "file" or "folder" to determine link type
        """
        if not blob_url:
            return None
        
        try:
            from ..config.settings import get_settings
            settings = get_settings()
            sharepoint_base_url = settings.SHAREPOINT_SITE_URL
            
            # Extract the file path from blob URL
            # Example blob URL: https://dtceaistorage.blob.core.windows.net/dtce-documents/Engineering/04_Design(Structural)/05_Timber/11%20Proprietary%20Products/Lumberworx/Lumberworx-Laminated-Veneer-Lumber-Glulam-Beams2013.pdf
            # For file: https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/Projects/219/219392/06%20Calculations/...
            # For folder: https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/219/219392/06%20Calculations/...
            
            # Extract everything after "/dtce-documents/"
            if '/dtce-documents/' in blob_url:
                path_part = blob_url.split('/dtce-documents/')[-1]
                
                # URL decode first (in case it's already encoded)
                import urllib.parse
                decoded_path = urllib.parse.unquote(path_part)
                
                # Check if this is a file (has extension) or folder
                filename = decoded_path.split('/')[-1]
                is_file = '.' in filename and len(filename.split('.')[-1]) <= 5  # Common file extensions
                
                if link_type == "file" and is_file:
                    # This is a file - create direct file link
                    encoded_path = urllib.parse.quote(decoded_path, safe='/')
                    # Build SuiteFiles URL - direct path for files
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/{encoded_path}"
                else:
                    # This is a folder or we want folder navigation
                    if is_file:
                        # Extract folder path from file path
                        folder_path = '/'.join(decoded_path.split('/')[:-1])
                        encoded_path = urllib.parse.quote(folder_path, safe='/')
                    else:
                        # This is already a folder path
                        encoded_path = urllib.parse.quote(decoded_path, safe='/')
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/folder/{encoded_path}"
                
                return suite_files_url
                
            # Fallback for old logic (Projects specific)
            elif '/Projects/' in blob_url:
                path_part = blob_url.split('/Projects/')[-1]
                import urllib.parse
                decoded_path = urllib.parse.unquote(path_part)
                
                # Check if this is a file or folder for Projects
                filename = decoded_path.split('/')[-1]
                is_file = '.' in filename and len(filename.split('.')[-1]) <= 5
                
                if link_type == "file" and is_file:
                    # Direct file access
                    encoded_path = urllib.parse.quote(decoded_path, safe='/')
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/Projects/{encoded_path}"
                else:
                    # Folder navigation
                    if is_file:
                        folder_path = '/'.join(decoded_path.split('/')[:-1])
                        encoded_path = urllib.parse.quote(folder_path, safe='/')
                    else:
                        encoded_path = urllib.parse.quote(decoded_path, safe='/')
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/folder/Projects/{encoded_path}"
                
                return suite_files_url
        except Exception as e:
            logger.warning("Failed to convert to SuiteFiles URL", blob_url=blob_url, error=str(e))
        
        return None

    def _get_safe_suitefiles_url(self, blob_url: str, link_type: str = "file") -> str:
        """
        Safely convert blob URL to SuiteFiles URL, ensuring we never return blob URLs.
        Returns SuiteFiles URL or fallback message, never blob URLs.
        
        Args:
            blob_url: The Azure blob storage URL
            link_type: Either "file" or "folder" to determine link type
        """
        if not blob_url:
            return "Document link not available"
        
        try:
            suitefiles_url = self._convert_to_suitefiles_url(blob_url, link_type)
            if suitefiles_url and not suitefiles_url.startswith('https://dtceaistorage.blob.core.windows.net'):
                return suitefiles_url
        except Exception as e:
            logger.warning("Failed to convert blob URL to SuiteFiles", blob_url=blob_url, error=str(e))
        
        # Never return blob URLs - return generic message instead
        return "Access document through SuiteFiles"

    def _search_keyword_documents(self, keywords: List[str]) -> List[Dict]:
        """Search for documents related to the specified keywords using semantic search with fallback."""
        try:
            # Create a comprehensive search query from keywords
            search_text = " ".join(keywords) + " engineering structural design construction"
            
            # Try semantic search first
            try:
                results = self.search_client.search(
                    search_text=search_text,
                    top=500,  # Get many more results to find all projects
                    select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                    query_type="semantic",  # Semantic search will find similar concepts
                    semantic_configuration_name="default"  # Use the semantic configuration we defined
                )
                search_type = "semantic"
            except Exception as semantic_error:
                logger.warning("Semantic search failed, falling back to regular search", error=str(semantic_error))
                # Fallback to regular search
                results = self.search_client.search(
                    search_text=search_text,
                    top=500,  # Get many more results to find all projects
                    select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                    query_type="simple"  # Use simple search as fallback
                )
                search_type = "simple"
            
            documents = []
            for result in results:
                doc_dict = dict(result)
                
                # More flexible content matching
                content = (doc_dict.get('content') or '').lower()
                filename = (doc_dict.get('filename') or '').lower()
                
                # Check for keyword-related terms in content or filename
                keyword_terms = keywords + [
                    'engineering', 'structural', 'design', 'construction', 'building',
                    'concrete', 'steel', 'timber', 'precast', 'retaining', 'wall'
                ]
                
                # Include if search found it OR if it contains obvious keyword terms
                if (result.get('@search.score', 0) > 0.1 or  # Lower threshold for match
                    any(term in content or term in filename for term in keyword_terms)):
                    documents.append(doc_dict)
            
            logger.info("Found keyword documents", search_type=search_type, keywords=keywords, count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Keyword search failed completely", error=str(e), keywords=keywords)
            return []

    def _group_documents_by_project(self, documents: List[Dict]) -> Dict[str, Dict]:
        """Group documents by project number for enhanced search results."""
        projects = {}
        
        logger.info(f"Grouping {len(documents)} documents by project")
        
        for doc in documents:
            blob_url = doc.get('blob_url', '')
            project_id = self._extract_project_from_url(blob_url)
            
            if project_id and len(project_id) >= 6:  # Valid project numbers
                if project_id not in projects:
                    projects[project_id] = {
                        'project_id': project_id,
                        'suitefiles_url': f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{project_id}",
                        'document_count': 0,
                        'sample_documents': [],
                        'keywords_found': []
                    }
                
                projects[project_id]['document_count'] += 1
                if len(projects[project_id]['sample_documents']) < 3:
                    projects[project_id]['sample_documents'].append(doc.get('filename', 'Unknown'))
        
        logger.info(f"Grouped documents into {len(projects)} projects")
        return projects

    def _extract_keyword_projects(self, keyword_docs: List[Dict], keywords: List[str]) -> Dict[str, Dict]:
        """Extract unique project numbers from keyword-related documents."""
        projects = {}
        
        logger.info(f"Extracting projects from {len(keyword_docs)} documents for keywords: {keywords}")
        
        for doc in keyword_docs:
            blob_url = doc.get('blob_url', '')
            project_id = self._extract_project_from_url(blob_url)
            
            if project_id and len(project_id) >= 6:  # Valid project numbers
                if project_id not in projects:
                    projects[project_id] = {
                        'project_id': project_id,
                        'suitefiles_url': f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{project_id}",
                        'document_count': 0,
                        'sample_documents': [],
                        'keywords_found': []
                    }
                
                projects[project_id]['document_count'] += 1
                if len(projects[project_id]['sample_documents']) < 3:
                    projects[project_id]['sample_documents'].append(doc.get('filename', 'Unknown'))
                
                # Track which keywords were found in this project
                content = (doc.get('content') or '').lower()
                # Use proper Base64 decoding for filename
                doc_info = self._extract_document_info(doc)
                filename = doc_info['filename'].lower() if doc_info['filename'] else ''
                for keyword in keywords:
                    if keyword in content or keyword in filename:
                        if keyword not in projects[project_id]['keywords_found']:
                            projects[project_id]['keywords_found'].append(keyword)
        
        logger.info(f"Found {len(projects)} unique projects: {list(projects.keys())}")
        return projects

    def _format_keyword_project_answer(self, projects_found: Dict[str, Dict], keywords: List[str]) -> str:
        """Format the answer for keyword-based project queries."""
        if not projects_found:
            return f"I couldn't find any projects related to {', '.join(keywords)} in our documents."
        
        project_count = len(projects_found)
        keywords_text = ', '.join(keywords).title()
        total_documents = sum(project_info['document_count'] for project_info in projects_found.values())
        
        # Always show detailed list format to display all projects
        if project_count == 1:
            answer = f"I found **{total_documents} documents** related to {keywords_text} in **1 project**:\n\n"
        else:
            answer = f"I found **{project_count} projects** with **{total_documents} total documents** related to {keywords_text}:\n\n"
        
        project_list = []
        for project_id, project_info in sorted(projects_found.items()):
            doc_count = project_info['document_count']
            suitefiles_url = project_info['suitefiles_url']
            keywords_found = project_info['keywords_found']
            sample_files = project_info.get('sample_documents', [])
            
            keywords_display = f" ({', '.join(keywords_found)})" if keywords_found else ""
            project_entry = f"• **Project {project_id}** - {doc_count} documents{keywords_display}\n  📁 [View Files]({suitefiles_url})"
            
            # Show sample files if available
            if sample_files:
                project_entry += f"\n  📄 Sample files: {', '.join(sample_files[:3])}"
                if doc_count > len(sample_files):
                    project_entry += f" (and {doc_count - len(sample_files)} more)"
            
            project_list.append(project_entry)
        
        answer += "\n\n".join(project_list)
        answer += "\n\nClick any link above to access the project folders in SuiteFiles."
        
        return answer

    def _format_keyword_sources(self, projects_found: Dict[str, Dict], keyword_docs: List[Dict]) -> List[Dict]:
        """Format sources for keyword project queries with SuiteFiles URLs."""
        sources = []
        
        for project_id, project_info in sorted(projects_found.items()):
            sample_files = project_info['sample_documents'][:3]
            keywords_found = project_info['keywords_found']
            
            if sample_files:
                sample_text = f"Including files: {', '.join(sample_files)}"
            else:
                sample_text = "Multiple related documents found"
            
            if keywords_found:
                sample_text += f" | Keywords: {', '.join(keywords_found)}"
                
            sources.append({
                'filename': f"Project {project_id}",
                'project_id': project_id,
                'relevance_score': 1.0,
                'blob_url': project_info['suitefiles_url'],
                'excerpt': sample_text
            })
        
        return sources

    async def _handle_precast_project_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle precast panel project queries with specialized search and SuiteFiles URLs."""
        try:
            logger.info("Processing precast project query", question=question)
            
            # Search for precast-related documents
            precast_docs = await self._search_precast_documents()
            
            if not precast_docs:
                return {
                    'answer': 'I could not find any precast panel projects in our document index.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0
                }
            
            # Extract unique projects and generate SuiteFiles URLs
            projects_found = self._extract_precast_projects(precast_docs)
            
            # Format response with project list and SuiteFiles URLs
            answer = self._format_precast_project_answer(projects_found)
            
            # Format sources with SuiteFiles URLs
            sources = self._format_precast_sources(projects_found, precast_docs)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',
                'documents_searched': len(precast_docs),
                'processing_time': 0
            }
            
        except Exception as e:
            logger.error("Precast project query failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while searching for precast projects: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _search_precast_documents(self) -> List[Dict]:
        """Search for documents related to precast panels using semantic search with fallback."""
        try:
            # Use natural language query for semantic search
            search_text = "precast panels precast concrete connections unispans prefabricated elements construction"
            
            # Try semantic search first
            try:
                results = self.search_client.search(
                    search_text=search_text,
                    top=100,  # Get many results to find all projects
                    select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                    query_type="semantic",  # Semantic search will find similar concepts
                    semantic_configuration_name="default"  # Use the semantic configuration we defined
                )
                search_type = "semantic"
            except Exception as semantic_error:
                logger.warning("Precast semantic search failed, falling back to simple search", error=str(semantic_error))
                # Fallback to simple search
                results = self.search_client.search(
                    search_text=search_text,
                    top=100,  # Get many results to find all projects
                    select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                    query_type="simple"  # Use simple search as fallback
                )
                search_type = "simple"
            
            documents = []
            for result in results:
                doc_dict = dict(result)
                
                # More flexible content matching with semantic search
                content = (doc_dict.get('content') or '').lower()
                filename = (doc_dict.get('filename') or '').lower()
                
                # With semantic search, we can be more lenient in filtering
                # Check for precast-related terms in content or filename
                precast_terms = [
                    'precast', 'pre-cast', 'unispan', 'prefab', 'prefabricated',
                    'tilt-up', 'lift-up', 'panel', 'connection'
                ]
                
                # Include if semantic search found it OR if it contains obvious precast terms
                # Lower the threshold for semantic search since Azure might score differently
                if (result.get('@search.score', 0) > 0.1 or  # Lower threshold for semantic match
                    any(term in content or term in filename for term in precast_terms)):
                    documents.append(doc_dict)
            
            logger.info("Found precast documents via semantic search", count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Precast semantic search failed", error=str(e))
            return []

    def _extract_precast_projects(self, precast_docs: List[Dict]) -> Dict[str, Dict]:
        """Extract unique project numbers from precast documents."""
        projects = {}
        
        for doc in precast_docs:
            blob_url = doc.get('blob_url', '')
            project_id = self._extract_project_from_url(blob_url)
            
            if project_id and len(project_id) >= 6:  # Valid project numbers
                if project_id not in projects:
                    projects[project_id] = {
                        'project_id': project_id,
                        'suitefiles_url': f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{project_id}",
                        'document_count': 0,
                        'sample_documents': []
                    }
                
                projects[project_id]['document_count'] += 1
                if len(projects[project_id]['sample_documents']) < 3:
                    projects[project_id]['sample_documents'].append(doc.get('filename', 'Unknown'))
        
        return projects

    def _format_precast_project_answer(self, projects_found: Dict[str, Dict]) -> str:
        """Format the answer for precast project queries."""
        if not projects_found:
            return "I couldn't find any projects with precast panel work in our documents."
        
        project_count = len(projects_found)
        total_documents = sum(project_info['document_count'] for project_info in projects_found.values())
        
        if project_count == 1 and total_documents <= 3:
            # Single project with few documents - conversational
            project_id, project_info = list(projects_found.items())[0]
            doc_count = project_info['document_count']
            suitefiles_url = project_info['suitefiles_url']
            
            answer = f"I found **Project {project_id}** which has {doc_count} documents related to precast work.\n\n"
            answer += f"📁 **View Project Files:** [Open in SuiteFiles]({suitefiles_url})\n\n"
            answer += "This will take you directly to the project folder where you can access all the precast-related documents."
        else:
            # Multiple projects OR single project with many documents - show detailed list
            if project_count == 1:
                answer = f"I found **{total_documents} precast-related documents** in **1 project**:\n\n"
            else:
                answer = f"I found **{project_count} projects** with **{total_documents} total documents** related to precast work:\n\n"
            
            project_list = []
            for project_id, project_info in sorted(projects_found.items()):
                doc_count = project_info['document_count']
                suitefiles_url = project_info['suitefiles_url']
                sample_files = project_info.get('sample_documents', [])
                
                project_entry = f"• **Project {project_id}** - {doc_count} precast documents\n  📁 [View Files]({suitefiles_url})"
                
                # Show sample files if available
                if sample_files and doc_count > 3:
                    project_entry += f"\n  📄 Sample files: {', '.join(sample_files[:3])}"
                    if len(sample_files) > 3:
                        project_entry += f" (and {doc_count - 3} more)"
                
                project_list.append(project_entry)
            
            answer += "\n\n".join(project_list)
            answer += "\n\nClick any link above to access the project folders in SuiteFiles."
        
        return answer

    def _format_precast_sources(self, projects_found: Dict[str, Dict], precast_docs: List[Dict]) -> List[Dict]:
        """Format sources for precast project queries with SuiteFiles URLs."""
        sources = []
        
        for project_id, project_info in sorted(projects_found.items()):
            sample_files = project_info['sample_documents'][:3]
            if sample_files:
                sample_text = f"Including files: {', '.join(sample_files)}"
            else:
                sample_text = "Multiple precast-related documents found"
                
            sources.append({
                'filename': f"Project {project_id}",
                'project_id': project_id,
                'relevance_score': 1.0,
                'blob_url': project_info['suitefiles_url'],
                'excerpt': sample_text
            })
        
        return sources[:10]  # Limit to top 10 projects

    def _is_nz_standards_query(self, question: str) -> bool:
        """Check if the question is asking about NZ Standards, codes, or clauses."""
        if not question:
            return False
        
        question_lower = question.lower()
        
        # NZ Standards and code terms
        standards_terms = [
            "nzs", "nz standard", "new zealand standard", "code", "clause",
            "nzs 3101", "nzs 3404", "nzs 1170", "nzs 3603", "structural code",
            "standard", "requirement", "specification"
        ]
        
        # Technical engineering terms often found in standards queries
        technical_terms = [
            "cover", "clear cover", "minimum cover", "concrete cover",
            "strength reduction", "reduction factor", "phi factor",
            "detailing", "detailing requirement", "reinforcement",
            "beam", "column", "slab", "foundation", "seismic",
            "composite", "diaphragm", "design", "structural design"
        ]
        
        # Question patterns that indicate standards queries
        standards_patterns = [
            "as per", "according to", "per code", "per standard",
            "what clause", "which clause", "tell me", "requirements",
            "minimum", "maximum", "shall", "must", "should"
        ]
        
        # Check for standards/code terms
        has_standards_terms = any(term in question_lower for term in standards_terms)
        
        # Check for technical terms
        has_technical_terms = any(term in question_lower for term in technical_terms)
        
        # Check for standards query patterns
        has_standards_patterns = any(pattern in question_lower for pattern in standards_patterns)
        
        # Return true if we have standards terms OR (technical terms AND standards patterns)
        return has_standards_terms or (has_technical_terms and has_standards_patterns)

    async def _handle_nz_standards_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle NZ Standards and code queries with specialized search for technical requirements."""
        try:
            logger.info("Processing NZ Standards query", question=question)
            
            # Search for standards-related documents
            standards_docs = await self._search_nz_standards_documents(question)
            
            if not standards_docs:
                return {
                    'answer': 'I could not find relevant NZ Standards or code documents to answer your technical query. Please ensure the standards documents are available in the system.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0
                }
            
            # Prepare enhanced context for standards queries
            context = self._prepare_standards_context(standards_docs, question)
            
            # Generate answer with focus on technical accuracy
            answer_response = await self._generate_standards_answer(question, context)
            
            # Format response with technical sources
            return {
                'answer': answer_response['answer'],
                'sources': [
                    {
                        'filename': doc.get('filename', 'NZ Standards Document'),
                        'project_id': 'NZ Standards',
                        'relevance_score': doc['@search.score'],
                        'blob_url': doc.get('blob_url', ''),
                        'excerpt': self._extract_relevant_clause(doc, question)
                    }
                    for doc in standards_docs[:5]  # Top 5 most relevant standards documents
                ],
                'confidence': answer_response['confidence'],
                'documents_searched': len(standards_docs),
                'processing_time': answer_response.get('processing_time', 0)
            }
            
        except Exception as e:
            logger.error("NZ Standards query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching NZ Standards documents.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _search_nz_standards_documents(self, question: str) -> List[Dict]:
        """Search for NZ Standards and code documents using semantic search."""
        try:
            # Create a focused search query for standards documents
            search_text = f"{question} NZS standard code clause requirement specification"
            
            results = self.search_client.search(
                search_text=search_text,
                top=50,  # Get more results for comprehensive standards coverage
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                query_type="semantic",  # Use semantic search for better technical matching
                semantic_configuration_name="default"
            )
            
            documents = []
            for result in results:
                doc_dict = dict(result)
                
                # Check if document contains standards-related content
                content = (doc_dict.get('content') or '').lower()
                filename = (doc_dict.get('filename') or '').lower()
                
                # Look for NZ Standards indicators
                standards_indicators = [
                    'nzs', 'standard', 'code', 'clause', 'shall', 'must',
                    'requirement', 'specification', 'concrete cover', 'strength reduction',
                    'detailing', 'reinforcement', 'structural design'
                ]
                
                # Include if it's likely a standards document
                if (result.get('@search.score', 0) > 0.1 or  # Good semantic match
                    any(indicator in content or indicator in filename for indicator in standards_indicators)):
                    documents.append(doc_dict)
            
            logger.info("Found NZ Standards documents", count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("NZ Standards search failed", error=str(e))
            return []

    def _prepare_standards_context(self, standards_docs: List[Dict], question: str) -> str:
        """Prepare context specifically for NZ Standards queries with relevant clauses."""
        context_parts = []
        current_length = 0
        
        for doc in standards_docs:
            content = doc.get('content', '')
            filename = doc.get('filename', 'Standards Document')
            
            # Extract relevant sections that might contain clauses or requirements
            relevant_content = self._extract_relevant_standards_content(content, question)
            
            if relevant_content:
                doc_context = f"""
=== {filename} ===
{relevant_content}
---
"""
                
                # Check if adding this document would exceed limit
                if current_length + len(doc_context) > self.max_context_length:
                    break
                    
                context_parts.append(doc_context)
                current_length += len(doc_context)
        
        return "\n".join(context_parts)

    def _extract_relevant_standards_content(self, content: str, question: str) -> str:
        """Extract the most relevant parts of standards documents for the question."""
        if not content:
            return ""
        
        question_lower = question.lower()
        content_lower = content.lower()
        
        # Keywords to look for in the question
        key_terms = []
        if 'cover' in question_lower:
            key_terms.extend(['cover', 'covering', 'concrete cover', 'clear cover'])
        if 'strength reduction' in question_lower or 'reduction factor' in question_lower:
            key_terms.extend(['strength reduction', 'reduction factor', 'phi', 'φ'])
        if 'detailing' in question_lower:
            key_terms.extend(['detailing', 'detail', 'reinforcement detailing'])
        if 'beam' in question_lower:
            key_terms.extend(['beam', 'flexural', 'bending'])
        if 'seismic' in question_lower:
            key_terms.extend(['seismic', 'earthquake', 'ductility'])
        if 'composite' in question_lower:
            key_terms.extend(['composite', 'slab', 'diaphragm'])
        
        # If no specific terms, look for general clause patterns
        if not key_terms:
            key_terms = ['clause', 'shall', 'must', 'requirement', 'minimum', 'maximum']
        
        # Find sentences containing key terms
        sentences = content.split('.')
        relevant_sentences = []
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(term in sentence_lower for term in key_terms):
                # Include some context around the relevant sentence
                relevant_sentences.append(sentence.strip())
        
        # Limit to most relevant content
        if relevant_sentences:
            return '. '.join(relevant_sentences[:10]) + '.'  # Max 10 sentences
        else:
            # Fallback to first part of content
            return content[:1500] + "..." if len(content) > 1500 else content

    def _extract_relevant_clause(self, doc: Dict, question: str) -> str:
        """Extract a relevant clause or excerpt from the document for display."""
        content = doc.get('content', '')
        if not content:
            return "NZ Standards document content"
        
        # Look for clause numbers or specific requirements
        relevant_content = self._extract_relevant_standards_content(content, question)
        
        if relevant_content:
            # Limit excerpt length for display
            excerpt = relevant_content[:200] + "..." if len(relevant_content) > 200 else relevant_content
            return excerpt
        else:
            return "NZ Standards technical requirements"

    async def _generate_standards_answer(self, question: str, context: str) -> Dict[str, Any]:
        """Generate answer specifically for NZ Standards queries with technical focus."""
        try:
            import time
            start_time = time.time()
            
            # Enhanced system prompt for NZ Standards queries
            system_prompt = """You are a technical AI assistant specializing in New Zealand Structural Engineering Standards and Codes. You have expert knowledge of NZS codes including NZS 3101 (Concrete), NZS 3404 (Steel), NZS 1170 (Loading), and other structural standards.

            TECHNICAL EXPERTISE AREAS:
            - NZS 3101: Concrete Structures Standard (cover requirements, strength reduction factors, detailing)
            - NZS 3404: Steel Structures Standard (connections, member design, seismic provisions)  
            - NZS 1170: Structural Design Actions (loading, seismic, wind)
            - NZS 3603: Timber Structures Standard
            - Building Code compliance and structural requirements

            RESPONSE REQUIREMENTS:
            1. ACCURACY: Provide precise, technically accurate information from NZ Standards
            2. CITE CLAUSES: Always reference specific clause numbers when available (e.g., "Clause 5.3.2 of NZS 3101")
            3. TECHNICAL DETAIL: Include specific values, formulas, and requirements
            4. CODE COMPLIANCE: Focus on compliance requirements and mandatory provisions
            5. PRACTICAL APPLICATION: Explain how the requirements apply in practice

            ANSWER FORMAT:
            - Lead with the specific requirement or answer
            - Cite the relevant NZS code and clause number
            - Provide technical details (values, formulas, conditions)
            - Explain any important exceptions or special cases
            - Be precise and avoid generalizations

            EXAMPLE RESPONSES:
            - "According to Clause 9.3.1 of NZS 3101:2006, the minimum cover to reinforcement shall be..."
            - "NZS 3101 specifies strength reduction factors (φ) in Table 7.1: φ = 0.85 for flexure, φ = 0.75 for shear..."
            - "For composite slabs acting as diaphragms, refer to NZS 3404 Part 1, specifically Clause 12.8.2..."
            """
            
            # Technical user prompt for standards queries
            user_prompt = f"""
            TECHNICAL STANDARDS QUERY: {question}

            AVAILABLE NZ STANDARDS DOCUMENTATION:
            {context if context.strip() else "Limited standards documentation available."}

            INSTRUCTIONS:
            - Extract specific requirements, clause numbers, and technical values from the provided standards documentation
            - If specific clause numbers are found, cite them precisely
            - Include exact values, formulas, and technical requirements
            - If the information is not in the provided documentation, clearly state this limitation
            - Focus on compliance requirements and mandatory provisions
            - Be technically precise and avoid approximations

            Provide a comprehensive, technically accurate answer based on the NZ Standards documentation provided.
            """
            
            # Call OpenAI with technical parameters
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Very low temperature for technical accuracy
                max_tokens=1000   # Longer responses for detailed technical information
            )
            
            answer = response.choices[0].message.content
            processing_time = time.time() - start_time
            
            # Assess confidence for technical content
            confidence = self._assess_standards_confidence(answer, context)
            
            logger.info("Generated NZ Standards answer", 
                       question=question, 
                       answer_length=len(answer),
                       confidence=confidence,
                       processing_time=processing_time)
            
            return {
                'answer': answer,
                'confidence': confidence,
                'processing_time': processing_time
            }
            
        except Exception as e:
            logger.error("Standards answer generation failed", error=str(e), question=question)
            return {
                'answer': 'I encountered an error while processing the NZ Standards query.',
                'confidence': 'error',
                'processing_time': 0
            }

    def _assess_standards_confidence(self, answer: str, context: str) -> str:
        """Assess confidence level specifically for NZ Standards answers."""
        # Check for technical indicators of good standards content
        technical_indicators = [
            'clause', 'nzs', 'standard', 'shall', 'minimum', 'maximum',
            'requirement', 'specification', 'table', 'figure'
        ]
        
        answer_lower = answer.lower()
        has_technical_content = sum(1 for indicator in technical_indicators if indicator in answer_lower)
        
        # High confidence if answer contains multiple technical indicators and good context
        if has_technical_content >= 3 and len(context) > 1000:
            return 'high'
        elif has_technical_content >= 2 and len(context) > 500:
            return 'medium'
        elif len(context) > 0:
            return 'medium'
        else:
            return 'low'

    def _is_web_search_query(self, question: str) -> bool:
        """Check if the question is asking for online/external resources."""
        if not question:
            return False
        
        question_lower = question.lower()
        
        # Only trigger web search for very explicit requests for external resources
        # This prevents false positives that should use internal documents
        explicit_external_requests = [
            "external resources", "online resources", "web resources",
            "public discussions", "forum discussions", "online forums",
            "external references", "outside resources", "internet sources",
            "online discussions", "web discussions", "online threads",
            "external websites", "public websites", "community discussions",
            "provide links", "share links", "find links", "online links"
        ]
        
        # Very specific patterns that clearly indicate external resource requests
        specific_patterns = [
            "look for.*online", "search.*online", "find.*online",
            "reddit.*discussion", "forum.*post", "online.*thread",
            "external.*discussion", "public.*forum", "web.*forum"
        ]
        
        # Check for explicit external requests
        has_explicit_request = any(request in question_lower for request in explicit_external_requests)
        
        # Check for specific patterns using regex
        import re
        has_specific_pattern = any(re.search(pattern, question_lower) for pattern in specific_patterns)
        
        # Only return true for very explicit external resource requests
        # This prevents triggering on general engineering questions
        return has_explicit_request or has_specific_pattern

    async def _handle_web_search_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries requiring web search for external resources."""
        try:
            logger.info("Processing external resources query", question=question)
            
            # Use GPT to provide a comprehensive answer with real external resources
            answer = await self._format_curated_external_resources(question)
            sources = await self._format_curated_sources(question, answer)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',  # GPT provides good external answers
                'documents_searched': 0,
                'search_type': 'gpt_external_resources'
            }
            
        except Exception as e:
            logger.error("External resources query failed", error=str(e))
            return {
                'answer': 'I encountered an error while gathering external resources. You might want to try searching engineering forums like Reddit r/StructuralEngineering, Engineering StackExchange, or SESOC resources directly.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _format_curated_external_resources(self, question: str) -> str:
        """Use GPT to provide a comprehensive answer with real external resources."""
        try:
            # Create a prompt for GPT to answer the question with real external resources
            external_resources_prompt = f"""You are a knowledgeable structural engineering assistant. The user has asked a question that requires external resources or general engineering knowledge not available in DTCE's internal documents.

Question: {question}

Please provide:
1. A direct, helpful answer to their question
2. Specific external resources with real working URLs where they can find more information
3. Focus on authoritative sources like:
   - Official software documentation and support
   - Professional engineering organizations (SESOC, NZSEE, SCNZ, etc. for NZ context)
   - Industry standards organizations (AISC, ACI, etc.)
   - Academic institutions and research papers
   - Active engineering forums and communities

Format your response with clear sections and include actual clickable URLs in markdown format [text](url).
Be specific and practical - provide resources that directly address their question."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior structural engineering consultant with extensive knowledge of industry resources, standards, and best practices. Provide helpful, accurate information with real external links."},
                    {"role": "user", "content": external_resources_prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            gpt_answer = response.choices[0].message.content.strip()
            
            # Add a note about DTCE's internal resources
            footer = "\n\n� **Note:** This answer draws from general engineering knowledge and external resources. For DTCE-specific project information, methodologies, and templates, please search our internal document library."
            
            return gpt_answer + footer
            
        except Exception as e:
            logger.error("GPT external resources generation failed", error=str(e))
            # Fallback to a brief static response
            return f"I couldn't generate a comprehensive answer for your question about external resources. You might want to try searching professional engineering resources like SESOC (https://sesoc.org.nz), engineering forums like Reddit r/StructuralEngineering, or the relevant software documentation directly."

    async def _format_curated_sources(self, question: str = "", gpt_answer: str = "") -> List[Dict]:
        """Format curated external resources as sources based on query context and GPT response."""
        question_lower = question.lower()
        sources = []
        
        # Try to extract URLs from GPT response if available
        if gpt_answer:
            import re
            url_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            urls_from_gpt = re.findall(url_pattern, gpt_answer)
            
            for title, url in urls_from_gpt[:5]:  # Limit to first 5 URLs from GPT
                sources.append({
                    'filename': title,
                    'project_id': 'External Resource',
                    'relevance_score': 0.95,
                    'blob_url': url,
                    'excerpt': f"Resource mentioned in AI response: {title}"
                })
        
        # Core structural engineering resources (if we don't have enough from GPT)
        if len(sources) < 3:
            sources.extend([
                {
                    'filename': 'Reddit r/StructuralEngineering',
                    'project_id': 'External Forum',
                    'relevance_score': 0.9,
                    'blob_url': 'https://reddit.com/r/StructuralEngineering',
                    'excerpt': 'Active community with daily discussions, project reviews, and Q&A sessions'
                },
                {
                    'filename': 'Engineering StackExchange',
                    'project_id': 'External Q&A',
                    'relevance_score': 0.9,
                    'blob_url': 'https://engineering.stackexchange.com',
                    'excerpt': 'Professional Q&A platform with expert-validated answers'
                }
            ])
        
        # Add contextual sources based on question content (only if needed)
        if len(sources) < 5:
            # New Zealand specific resources
            if any(term in question_lower for term in ['nz', 'new zealand', 'nzs', 'building code', 'sesoc', 'council']):
                sources.append({
                    'filename': 'SESOC - New Zealand',
                    'project_id': 'External Organization',
                    'relevance_score': 0.8,
                    'blob_url': 'https://sesoc.org.nz',
                    'excerpt': 'Structural Engineering Society of New Zealand'
                })
                sources.append({
                    'filename': 'MBIE Building Performance',
                    'project_id': 'External Government',
                    'relevance_score': 0.8,
                    'blob_url': 'https://www.building.govt.nz',
                    'excerpt': 'New Zealand Building Code and compliance information'
                })
            
            # Software-specific resources
            if any(term in question_lower for term in ['etabs', 'sap2000', 'csi']):
                sources.append({
                    'filename': 'CSI Knowledge Base',
                    'project_id': 'External Software',
                    'relevance_score': 0.85,
                    'blob_url': 'https://wiki.csiamerica.com',
                    'excerpt': 'Official documentation and tutorials for ETABS, SAP2000, and other CSI software'
                })
            
            if any(term in question_lower for term in ['spacegass', 'space gass']):
                sources.append({
                    'filename': 'Spacegass Support',
                    'project_id': 'External Software',
                    'relevance_score': 0.85,
                    'blob_url': 'https://www.spacegass.com/support',
                    'excerpt': 'Official Spacegass documentation and support resources'
                })
        
        # Remove duplicates and limit to 6 sources
        seen_urls = set()
        unique_sources = []
        for source in sources:
            if source['blob_url'] not in seen_urls:
                seen_urls.add(source['blob_url'])
                unique_sources.append(source)
                if len(unique_sources) >= 6:
                    break
        
        return unique_sources

    async def _handle_contractor_search_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries asking about builders, contractors, or construction companies."""
        try:
            logger.info("Processing contractor search query", question=question)
            
            # Search for documents mentioning contractors, builders, or construction companies
            contractor_search_terms = [
                "contractor", "builder", "construction company", "built by", 
                "constructed by", "main contractor", "subcontractor",
                "building company", "construction team", "project manager"
            ]
            
            # Create search query focusing on contractor information
            search_query = f"{question} contractor builder construction company"
            
            # Search documents
            results = self.search_client.search(
                search_text=search_query,
                top=50,
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                query_type="semantic",
                semantic_configuration_name="default"
            )
            
            contractor_docs = []
            contractor_info = {}
            
            for result in results:
                doc_dict = dict(result)
                content = (doc_dict.get('content') or '').lower()
                
                # Look for contractor mentions in the content
                if any(term in content for term in contractor_search_terms):
                    contractor_docs.append(doc_dict)
                    
                    # Extract contractor names and contact info using regex
                    # Use the _extract_document_info method to get proper project information
                    doc_info = self._extract_document_info(doc_dict)
                    project_id = doc_info['project_id'] or doc_info['project_name'] or 'Unknown Project'
                    
                    contractors = self._extract_contractor_info(doc_dict.get('content', ''))
                    
                    if contractors and project_id not in contractor_info:
                        contractor_info[project_id] = contractors
            
            if not contractor_docs:
                return {
                    'answer': 'I could not find specific contractor or builder information in our project documents. You might want to check project correspondence or construction documentation directly.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0
                }
            
            # Format the answer
            answer = self._format_contractor_answer(contractor_info, question)
            sources = self._format_contractor_sources(contractor_docs)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'medium',
                'documents_searched': len(contractor_docs)
            }
            
        except Exception as e:
            logger.error("Contractor search query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for contractor information.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _extract_contractor_info(self, content: str) -> List[Dict[str, str]]:
        """Extract contractor names and contact information from document content."""
        if not content or len(content) < 50:
            return []
        
        contractors = []
        found_names = set()
        
        # Clean content
        content = content.replace('\n', ' ').replace('\r', ' ')
        content = ' '.join(content.split())  # Normalize whitespace
        
        # Very specific patterns - must end with company identifiers
        company_patterns = [
            r'\b([A-Z][a-zA-Z]{3,15}\s+Construction\s+(?:Ltd|Limited))\b',
            r'\b([A-Z][a-zA-Z]{3,15}\s+Building\s+(?:Ltd|Limited))\b',
            r'\b([A-Z][a-zA-Z]{3,15}\s+Contractors\s+(?:Ltd|Limited))\b',
            r'\b([A-Z][a-zA-Z]{3,15}\s+Engineering\s+(?:Ltd|Limited))\b',
            # Specific known good patterns
            r'\b(Griffiths\s+Construction)\b',
            r'\b(Strongman\s+Building)\b',
        ]
        
        # DTCE emails to exclude (our own company)
        dtce_domains = ['dtce.co.nz', 'donthomson.co.nz']
        
        # Look for well-formed company names
        for pattern in company_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for company_name in matches:
                company_name = company_name.strip()
                
                # Skip if too short, too long, or already found
                if (len(company_name) < 8 or 
                    len(company_name) > 35 or 
                    company_name in found_names):
                    continue
                
                # Skip obvious bad matches
                bad_words = [
                    'building consent', 'building code', 'construction site', 
                    'construction work', 'consulting engineers', 'main building',
                    'scott building', 'wall building', 'and construction',
                    'which contractor', 'the contractor', 'a contractor'
                ]
                if any(bad.lower() in company_name.lower() for bad in bad_words):
                    continue
                    
                # Skip if it contains DTCE (our own company)
                if 'dtce' in company_name.lower() or 'consulting engineers limited' in company_name.lower():
                    continue
                    
                found_names.add(company_name)
                
                # Look for contact info near this company
                company_pos = content.lower().find(company_name.lower())
                if company_pos >= 0:
                    context_start = max(0, company_pos - 100)
                    context_end = min(len(content), company_pos + len(company_name) + 100)
                    context = content[context_start:context_end]
                    
                    # Find emails and phones in context
                    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,4}\b', context)
                    phones = re.findall(r'(?:\+64[\s\-]?|0)[2-9][\s\-]?\d{3}[\s\-]?\d{4}', context)
                    
                    # Filter out DTCE emails
                    clean_emails = []
                    for email in emails:
                        email_lower = email.lower()
                        if not any(domain in email_lower for domain in dtce_domains):
                            clean_emails.append(email)
                    
                    # Only add if we have external contact info
                    if clean_emails or phones:
                        contractors.append({
                            'name': company_name,
                            'emails': clean_emails[:1],  # Max 1 email
                            'phones': list(set(phones))[:1]   # Max 1 phone
                        })
        
        return contractors[:2]  # Max 2 contractors to keep response very clean

    def _format_contractor_answer(self, contractor_info: Dict[str, List[Dict]], question: str) -> str:
        """Format contractor information into a clean, readable answer."""
        if not contractor_info:
            return "I couldn't find specific contractor information in our project documents. You may want to check with the project managers for recent contractor recommendations."
        
        # Filter out projects with no valid contractors
        valid_projects = {}
        for project_id, contractors in contractor_info.items():
            valid_contractors = [c for c in contractors if c.get('name') and len(c['name']) > 5]
            if valid_contractors:
                valid_projects[project_id] = valid_contractors
        
        if not valid_projects:
            return "I couldn't find clear contractor contact information in our documents. For steel structure retrofits on heritage buildings, I recommend contacting local steel fabrication companies with heritage building experience."
        
        answer = "Based on our project documents, here are contractors we've worked with:\n\n"
        
        contractor_count = 0
        for project_id, contractors in valid_projects.items():
            # Clean up project display - skip if problematic
            if (not project_id or 
                project_id == 'None' or 
                project_id == 'Unknown' or
                'unknown' in project_id.lower() or
                len(project_id) < 3):
                continue
                
            # Format project name properly
            if project_id.isdigit():
                project_display = f"Project {project_id}"
            else:
                # Clean up project ID
                project_clean = project_id.replace('Project ', '').strip()
                if len(project_clean) > 20:  # Too long, probably corrupted
                    continue
                project_display = f"Project {project_clean}"
            
            answer += f"🏗️ **{project_display}**\n"
            
            for contractor in contractors:
                contractor_count += 1
                contractor_name = contractor['name'].strip()
                    
                answer += f"• **{contractor_name}**\n"
                
                # Add contact info if available
                if contractor.get('emails'):
                    clean_emails = [email for email in contractor['emails'] if '@' in email and '.' in email]
                    if clean_emails:
                        answer += f"  📧 {', '.join(clean_emails[:1])}\n"  # Max 1 email
                
                if contractor.get('phones'):
                    clean_phones = [phone for phone in contractor['phones'] if len(phone.replace(' ', '').replace('-', '')) >= 8]
                    if clean_phones:
                        answer += f"  📞 {', '.join(clean_phones[:1])}\n"  # Max 1 phone
                
                answer += "\n"
        
        # Add context-specific recommendations only if we found contractors
        if contractor_count > 0:
            answer += "💡 **For your steel structure retrofit:**\n"
            answer += "• Look for contractors with steel construction experience\n"
            answer += "• Choose companies familiar with heritage building work\n"
            answer += "• Verify they have experience with structural modifications\n\n"
            answer += "⚠️ **Note:** Please verify current contact details and availability."
        else:
            answer = "I couldn't find clear contractor contact information in our documents. For steel structure retrofits on heritage buildings, I recommend:\n\n"
            answer += "• Contacting local steel fabrication companies\n"
            answer += "• Looking for contractors with heritage building experience\n"
            answer += "• Checking with building consent authorities for recommended contractors\n"
            answer += "• Getting multiple quotes from different specialists\n\n"
            answer += "You may want to check with your project manager for specific contractor recommendations."
        
        return answer

    def _format_contractor_sources(self, contractor_docs: List[Dict]) -> List[Dict]:
        """Format contractor documents as sources."""
        sources = []
        
        for doc in contractor_docs[:5]:  # Limit to top 5 sources
            sources.append({
                'filename': doc.get('filename', 'Unknown Document'),
                'project_id': doc.get('project_name', 'Unknown Project'),
                'relevance_score': doc.get('@search.score', 0.8),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': (doc.get('content', '')[:200] + '...') if doc.get('content') else ''
            })
        
        return sources

    async def _handle_scenario_technical_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle scenario-based technical queries that combine building type, conditions, and location."""
        try:
            logger.info("Processing scenario-based technical query", question=question)
            
            # Extract scenario components from the question
            scenario_components = self._extract_scenario_components(question)
            
            # Build enhanced search terms for scenario matching
            search_terms = self._build_scenario_search_terms(question, scenario_components)
            
            # Search with scenario-optimized terms
            relevant_docs = self._search_scenario_documents(search_terms, scenario_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific examples matching your criteria: {scenario_components.get('summary', question)}. Try searching for broader terms or check if there are similar projects with different conditions.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'scenario_technical'
                }
            
            # Generate scenario-specific answer
            answer = await self._generate_scenario_answer(question, relevant_docs, scenario_components)
            
            # Format sources with project context
            sources = self._format_scenario_sources(relevant_docs, scenario_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'scenario_technical',
                'scenario_components': scenario_components
            }
            
        except Exception as e:
            logger.error("Scenario technical query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for scenario-based examples. Please try rephrasing your query or search for individual components.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _extract_scenario_components(self, question: str) -> Dict[str, Any]:
        """Extract building type, conditions, location, and system components from scenario query."""
        question_lower = question.lower()
        
        components = {
            'building_types': [],
            'structural_systems': [],
            'environmental_conditions': [],
            'locations': [],
            'specific_elements': [],
            'summary': ''
        }
        
        # Building types
        building_types = {
            'mid-rise': ['mid-rise', 'medium rise', 'multi-story', 'multi-storey'],
            'timber frame': ['timber frame', 'wood frame', 'timber construction'],
            'apartment': ['apartment', 'residential complex', 'unit'],
            'house': ['house', 'dwelling', 'home', 'residence'],
            'commercial': ['commercial', 'office', 'retail']
        }
        
        # Structural systems
        structural_systems = {
            'concrete shear walls': ['concrete shear wall', 'shear wall', 'concrete wall'],
            'foundation': ['foundation', 'footing', 'pile', 'basement'],
            'timber frame': ['timber frame', 'wood frame', 'CLT', 'LVL'],
            'steel frame': ['steel frame', 'steel structure', 'structural steel'],
            'connections': ['connection', 'joint', 'fastener', 'bracket']
        }
        
        # Environmental conditions
        environmental_conditions = {
            'high wind': ['high wind', 'wind zone', 'cyclone', 'hurricane', 'wind load'],
            'seismic': ['seismic', 'earthquake', 'seismic strengthening', 'seismic zone'],
            'coastal': ['coastal', 'marine', 'salt exposure', 'corrosion'],
            'steep slope': ['steep slope', 'sloping site', 'hillside', 'gradient']
        }
        
        # Locations
        locations = {
            'wellington': ['wellington', 'wgtn'],
            'auckland': ['auckland', 'akl'],
            'christchurch': ['christchurch', 'chch'],
            'queenstown': ['queenstown'],
            'coastal': ['coastal', 'beachfront', 'waterfront']
        }
        
        # Specific elements
        specific_elements = {
            'balcony': ['balcony', 'deck', 'terrace'],
            'connections': ['connection detail', 'connection', 'joint detail'],
            'foundation system': ['foundation system', 'foundation type'],
            'reinforcement': ['reinforcement', 'strengthening', 'retrofit']
        }
        
        # Extract components
        for category, terms_dict in [
            ('building_types', building_types),
            ('structural_systems', structural_systems), 
            ('environmental_conditions', environmental_conditions),
            ('locations', locations),
            ('specific_elements', specific_elements)
        ]:
            for key, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(key)
        
        # Create summary
        summary_parts = []
        if components['building_types']:
            summary_parts.append(f"Building: {', '.join(components['building_types'])}")
        if components['structural_systems']:
            summary_parts.append(f"Structure: {', '.join(components['structural_systems'])}")
        if components['environmental_conditions']:
            summary_parts.append(f"Conditions: {', '.join(components['environmental_conditions'])}")
        if components['locations']:
            summary_parts.append(f"Location: {', '.join(components['locations'])}")
        if components['specific_elements']:
            summary_parts.append(f"Elements: {', '.join(components['specific_elements'])}")
            
        components['summary'] = " | ".join(summary_parts) if summary_parts else question
        
        return components

    def _build_scenario_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build optimized search terms for scenario matching."""
        search_terms = []
        
        # Add original question terms
        search_terms.append(question)
        
        # Add component-specific terms
        for category in ['building_types', 'structural_systems', 'environmental_conditions', 'locations', 'specific_elements']:
            search_terms.extend(components.get(category, []))
        
        # Add technical document keywords that might contain these scenarios
        technical_keywords = [
            'structural calculation', 'design report', 'engineering analysis',
            'project summary', 'design brief', 'structural drawing',
            'specification', 'technical report', 'assessment'
        ]
        search_terms.extend(technical_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:15])  # Limit to prevent too long query

    def _search_scenario_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents matching scenario criteria."""
        try:
            # Search with broader terms first
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                search_mode="any"
            )
            
            relevant_docs = []
            seen_projects = set()
            
            for result in results:
                # Score documents based on how many scenario components they match
                score = self._calculate_scenario_relevance(result, components)
                
                if score > 0.3:  # Minimum relevance threshold
                    # Avoid duplicate projects unless they're highly relevant
                    project_id = result.get('project_name', 'unknown')
                    if project_id not in seen_projects or score > 0.8:
                        result['scenario_score'] = score
                        relevant_docs.append(result)
                        seen_projects.add(project_id)
            
            # Sort by scenario relevance score
            relevant_docs.sort(key=lambda x: x.get('scenario_score', 0), reverse=True)
            
            logger.info("Scenario document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:10]  # Top 10 most relevant
            
        except Exception as e:
            logger.error("Scenario document search failed", error=str(e))
            return []

    def _calculate_scenario_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches the scenario components."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '')
        ).lower()
        
        score = 0.0
        total_components = 0
        
        # Check each component category
        for category in ['building_types', 'structural_systems', 'environmental_conditions', 'locations', 'specific_elements']:
            components_list = components.get(category, [])
            if components_list:
                total_components += len(components_list)
                for component in components_list:
                    if component.lower() in content:
                        # Weight different categories
                        if category == 'structural_systems':
                            score += 0.3  # Structural systems are most important
                        elif category == 'environmental_conditions':
                            score += 0.25
                        elif category == 'building_types':
                            score += 0.2
                        elif category == 'locations':
                            score += 0.15
                        else:
                            score += 0.1
        
        # Normalize score
        if total_components > 0:
            score = score / total_components
        
        # Bonus for documents that match multiple categories
        matched_categories = sum(1 for category in ['building_types', 'structural_systems', 'environmental_conditions', 'locations'] 
                               if any(comp.lower() in content for comp in components.get(category, [])))
        
        if matched_categories >= 2:
            score += 0.2
        if matched_categories >= 3:
            score += 0.3
            
        return min(score, 1.0)  # Cap at 1.0

    async def _generate_scenario_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for scenario-based queries."""
        if not documents:
            return "No matching examples found for your scenario criteria."
        
        # Create context from top documents
        context_parts = []
        for i, doc in enumerate(documents[:5]):
            project = doc.get('project_name', 'Unknown Project')
            filename = doc.get('filename', 'Unknown Document')
            content_excerpt = doc.get('content', '')[:500]
            
            context_parts.append(f"Document {i+1}: {filename} (Project: {project})\n{content_excerpt}...")
        
        context = "\n\n".join(context_parts)
        
        # Generate AI response with scenario context
        scenario_prompt = f"""Based on the following engineering documents from DTCE projects, provide a comprehensive answer for this scenario-based query:

Question: {question}

Scenario Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Examples Found**: List specific projects that match the scenario criteria
2. **Technical Details**: Key structural systems, connection details, or design approaches used
3. **Location-Specific Considerations**: Any location-specific factors (wind, seismic, coastal, etc.)
4. **Design Solutions**: Specific solutions, products, or methodologies employed
5. **References**: Which projects/documents contain the most relevant information

Format your response with clear headings and bullet points. Focus on practical engineering information that can be applied to similar scenarios."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior structural engineer analyzing DTCE project documents to provide scenario-based technical guidance."},
                    {"role": "user", "content": scenario_prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Scenario answer generation failed", error=str(e))
            return f"Found {len(documents)} relevant examples matching your scenario criteria. Please review the source documents for detailed technical information."

    def _format_scenario_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format scenario-based document sources with enhanced context."""
        sources = []
        
        for doc in documents[:5]:
            scenario_score = doc.get('scenario_score', 0)
            filename = doc.get('filename', 'Unknown Document')
            
            # Handle case where filename is literally 'None' or missing
            if not filename or filename == 'None':
                # Try to create a meaningful filename from content
                filename = self._generate_meaningful_filename(doc)
            
            sources.append({
                'filename': filename,
                'project_id': self._extract_project_from_document(doc), 
                'relevance_score': doc.get('@search.score', scenario_score),
                'scenario_score': round(scenario_score, 2),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': (doc.get('content', '')[:200] + '...') if doc.get('content') else '',
                'matching_components': components['summary']
            })
        
        return sources

    async def _handle_regulatory_precedent_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about regulatory challenges, council interactions, alternative solutions, and consent precedents."""
        try:
            logger.info("Processing regulatory precedent query", question=question)
            
            # Extract regulatory components from the question
            regulatory_components = self._extract_regulatory_components(question)
            
            # Build search terms focused on regulatory documents
            search_terms = self._build_regulatory_search_terms(question, regulatory_components)
            
            # Search for regulatory/consent-related documents
            relevant_docs = await self._search_regulatory_documents(search_terms, regulatory_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific examples of regulatory precedents for: {regulatory_components.get('summary', question)}. Try searching for broader terms or check council correspondence files.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'regulatory_precedent'
                }
            
            # Generate regulatory-focused answer
            answer = await self._generate_regulatory_answer(question, relevant_docs, regulatory_components)
            sources = self._format_regulatory_sources(relevant_docs, regulatory_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'regulatory_precedent',
                'regulatory_components': regulatory_components
            }
            
        except Exception as e:
            logger.error("Regulatory precedent query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for regulatory precedents. Please try searching for specific project names or council correspondence.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _handle_cost_time_insights_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about project timelines, costs, durations, and scope changes."""
        try:
            logger.info("Processing cost/time insights query", question=question)
            
            # Extract cost/time components from the question
            cost_time_components = self._extract_cost_time_components(question)
            
            # Build search terms focused on project timeline and cost documents
            search_terms = self._build_cost_time_search_terms(question, cost_time_components)
            
            # Search for cost/time-related documents
            relevant_docs = await self._search_cost_time_documents(search_terms, cost_time_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific cost or timeline information for: {cost_time_components.get('summary', question)}. Try searching for project reports, fee proposals, or correspondence files.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'cost_time_insights',
                    'cost_time_components': cost_time_components
                }
            
            # Generate AI answer focused on cost/time insights
            answer = await self._generate_cost_time_answer(question, relevant_docs, cost_time_components)
            sources = self._format_cost_time_sources(relevant_docs, cost_time_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'cost_time_insights',
                'cost_time_components': cost_time_components
            }
            
        except Exception as e:
            logger.error("Cost/time insights query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for cost and timeline information. Please try searching for specific project types or timeframe ranges.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _extract_cost_time_components(self, question: str) -> Dict[str, Any]:
        """Extract cost, timeline, and project duration components from the query."""
        question_lower = question.lower()
        
        components = {
            'timeline_types': [],
            'cost_types': [],
            'project_types': [],
            'scope_aspects': [],
            'duration_indicators': []
        }
        
        # Timeline and milestone types
        timeline_types = {
            'concept_to_ps1': ['concept to ps1', 'concept design to ps1', 'initial to ps1'],
            'ps1_to_completion': ['ps1 to completion', 'ps1 to finished', 'ps1 to end'],
            'design_phase': ['design phase', 'design duration', 'design time'],
            'consent_process': ['consent time', 'consent duration', 'building consent', 'approval time'],
            'total_project': ['total duration', 'project length', 'start to finish', 'overall timeline'],
            'milestone_phases': ['phases', 'milestones', 'stages']
        }
        
        # Cost categories
        cost_types = {
            'structural_design': ['structural design cost', 'engineering fee', 'structural fee'],
            'total_project_cost': ['total cost', 'project cost', 'overall cost'],
            'design_fees': ['design fee', 'consultant fee', 'professional fee'],
            'scope_expansion': ['scope increase', 'additional work', 'extra cost', 'cost overrun'],
            'cost_range': ['cost range', 'typical cost', 'cost estimate', 'budget range']
        }
        
        # Project types and categories
        project_types = {
            'commercial_alterations': ['commercial alteration', 'commercial renovation', 'office alteration'],
            'residential': ['residential', 'house', 'home', 'dwelling'],
            'multi_unit': ['multi-unit', 'apartment', 'townhouse', 'duplex'],
            'industrial': ['industrial', 'warehouse', 'factory'],
            'heritage': ['heritage', 'historic', 'character building'],
            'new_build': ['new build', 'new construction', 'new development'],
            'small_projects': ['small', 'minor', 'simple'],
            'large_projects': ['large', 'major', 'complex']
        }
        
        # Scope change indicators
        scope_aspects = {
            'scope_expansion': ['scope expanded', 'scope increased', 'additional work', 'scope change', 'expanded significantly', 'scope grew', 'scope expansion', 'extra scope'],
            'scope_reduction': ['scope reduced', 'scope decreased', 'scope cut'],
            'design_changes': ['design change', 'design revision', 'redesign'],
            'structural_additions': ['structural addition', 'extra structural', 'additional structural']
        }
        
        # Duration and time indicators
        duration_indicators = {
            'typical_duration': ['typical', 'usually', 'normally', 'average'],
            'fast_track': ['fast', 'quick', 'urgent', 'expedited'],
            'extended_timeline': ['long', 'extended', 'delayed', 'slow'],
            'specific_timeframes': ['weeks', 'months', 'days', 'years']
        }
        
        # Extract components
        for category, terms_dict in [
            ('timeline_types', timeline_types),
            ('cost_types', cost_types),
            ('project_types', project_types),
            ('scope_aspects', scope_aspects),
            ('duration_indicators', duration_indicators)
        ]:
            for key, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(key)
        
        # Create summary
        summary_parts = []
        if components['timeline_types']:
            summary_parts.append(f"Timeline: {', '.join(components['timeline_types'])}")
        if components['cost_types']:
            summary_parts.append(f"Cost: {', '.join(components['cost_types'])}")
        if components['project_types']:
            summary_parts.append(f"Projects: {', '.join(components['project_types'])}")
        if components['scope_aspects']:
            summary_parts.append(f"Scope: {', '.join(components['scope_aspects'])}")
        if components['duration_indicators']:
            summary_parts.append(f"Duration: {', '.join(components['duration_indicators'])}")
            
        components['summary'] = " | ".join(summary_parts) if summary_parts else question
        
        return components

    def _build_cost_time_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms optimized for finding cost and timeline documents."""
        search_terms = []
        
        # Add original question
        search_terms.append(question)
        
        # Add cost/time-specific terms
        cost_time_keywords = [
            # Timeline terms
            'timeline', 'duration', 'time', 'schedule', 'milestone', 'phase',
            'concept design', 'ps1', 'ps3', 'completion', 'start', 'finish',
            
            # Cost terms
            'cost', 'fee', 'budget', 'price', 'estimate', 'proposal', 'quote',
            'structural design fee', 'engineering cost', 'professional fee',
            
            # Project phases
            'concept', 'developed design', 'detailed design', 'consent',
            'construction', 'completion', 'sign-off',
            
            # Scope terms
            'scope', 'additional work', 'variation', 'change', 'expansion',
            'extra', 'revised scope', 'scope increase',
            
            # Document types
            'fee proposal', 'report', 'correspondence', 'memo', 'email',
            'project brief', 'scope document'
        ]
        
        # Add component-specific terms
        for category in ['timeline_types', 'cost_types', 'project_types', 'scope_aspects', 'duration_indicators']:
            search_terms.extend(components.get(category, []))
        
        # Add cost/time keywords
        search_terms.extend(cost_time_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:25])  # Limit to prevent too long query

    def _build_best_practices_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms for best practices and templates queries."""
        search_terms = []
        
        # Extract key terms from question
        question_lower = question.lower()
        search_terms.extend([word for word in question_lower.split() if len(word) > 3])
        
        # Add component-specific terms
        for category in ['practice_types', 'template_types', 'methodology_types', 'scope_areas', 'deliverable_types']:
            search_terms.extend(components.get(category, []))
        
        # Add best practices keywords
        best_practices_keywords = [
            'standard approach', 'methodology', 'template', 'procedure', 'guideline',
            'best practice', 'calculation sheet', 'design process', 'quality assurance',
            'specification', 'checklist', 'protocol', 'format', 'process'
        ]
        search_terms.extend(best_practices_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:25])  # Limit to prevent too long query

    def _build_materials_methods_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms for materials and methods queries."""
        search_terms = []
        
        # Extract key terms from question
        question_lower = question.lower()
        search_terms.extend([word for word in question_lower.split() if len(word) > 3])
        
        # Add component-specific terms
        for category in ['material_types', 'structural_systems', 'comparison_aspects', 'building_elements', 'project_contexts', 'decision_factors']:
            search_terms.extend(components.get(category, []))
        
        # Add materials/methods keywords
        materials_methods_keywords = [
            'material selection', 'concrete', 'steel', 'timber', 'comparison', 'alternative',
            'chosen', 'selected', 'rationale', 'decision', 'performance', 'construction',
            'versus', 'vs', 'compared', 'why', 'because', 'reason'
        ]
        search_terms.extend(materials_methods_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:25])  # Limit to prevent too long query

    def _build_internal_knowledge_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms for internal knowledge and expertise queries."""
        # For specific technical terms, use them directly
        specific_terms = self._extract_specific_technical_terms(question)
        if specific_terms:
            # Use specific technical terms with AND logic for precision
            main_search = " AND ".join(f'"{term}"' for term in specific_terms)
            
            # Add engineer-related terms with OR logic
            engineer_terms = []
            for role in components.get('engineer_roles', []):
                engineer_terms.append(f'"{role}"')
            
            if engineer_terms:
                return f"({main_search}) AND ({' OR '.join(engineer_terms)})"
            else:
                return main_search
        
        # Fallback to original approach for general queries
        search_terms = []
        
        # Extract key terms from question
        question_lower = question.lower()
        search_terms.extend([word for word in question_lower.split() if len(word) > 3])
        
        # Add component-specific terms
        for category in ['expertise_areas', 'engineer_roles', 'project_types', 'technical_skills', 'experience_levels', 'knowledge_types']:
            search_terms.extend(components.get(category, []))
        
        # Add internal knowledge keywords
        internal_knowledge_keywords = [
            'engineer', 'expertise', 'experience', 'specialist', 'team', 'staff',
            'designed by', 'checked by', 'responsible', 'involved', 'worked on',
            'skills', 'knowledge', 'capability', 'qualified', 'competent'
        ]
        search_terms.extend(internal_knowledge_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:25])  # Limit to prevent too long query

    async def _search_cost_time_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing cost and timeline information."""
        try:
            # Search with cost/time focus
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                search_mode="any"
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                # Score documents based on cost/time relevance
                score = self._calculate_cost_time_relevance(result, components)
                
                if score > 0.2:  # Threshold for cost/time relevance
                    # Avoid duplicate documents
                    doc_id = result.get('id', result.get('filename', ''))
                    if doc_id not in seen_docs:
                        result['cost_time_score'] = score
                        relevant_docs.append(result)
                        seen_docs.add(doc_id)
            
            # Sort by cost/time relevance score
            relevant_docs.sort(key=lambda x: x.get('cost_time_score', 0), reverse=True)
            
            logger.info("Cost/time document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Cost/time document search failed", error=str(e))
            return []

    async def _search_best_practices_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing best practices and templates."""
        try:
            # Search with best practices focus
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                filter=None
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                if result.get('id'):
                    doc_id = result['id']
                    if doc_id not in seen_docs:
                        # Calculate best practices relevance
                        score = self._calculate_best_practices_relevance(result, components)
                        if score >= 0.2:  # Threshold for best practices relevance
                            result['best_practices_score'] = score
                            relevant_docs.append(result)
                            seen_docs.add(doc_id)
            
            # Sort by best practices relevance score
            relevant_docs.sort(key=lambda x: x.get('best_practices_score', 0), reverse=True)
            
            logger.info("Best practices document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Best practices document search failed", error=str(e))
            return []

    async def _search_materials_methods_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing materials and methods information."""
        try:
            # Search with materials/methods focus
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                filter=None
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                if result.get('id'):
                    doc_id = result['id']
                    if doc_id not in seen_docs:
                        # Calculate materials/methods relevance
                        score = self._calculate_materials_methods_relevance(result, components)
                        if score >= 0.2:  # Threshold for materials/methods relevance
                            result['materials_methods_score'] = score
                            relevant_docs.append(result)
                            seen_docs.add(doc_id)
            
            # Sort by materials/methods relevance score
            relevant_docs.sort(key=lambda x: x.get('materials_methods_score', 0), reverse=True)
            
            logger.info("Materials/methods document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Materials/methods document search failed", error=str(e))
            return []

    async def _search_internal_knowledge_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing internal knowledge and expertise information."""
        try:
            # For specific technical queries, use more targeted search
            specific_technical_terms = self._extract_specific_technical_terms(search_terms)
            
            if specific_technical_terms:
                # Use specific technical term search for better results
                search_query = " ".join(specific_technical_terms)
                logger.info("Using specific technical search", terms=specific_technical_terms)
            else:
                search_query = search_terms
            
            # Search with internal knowledge focus
            results = self.search_client.search(
                search_text=search_query,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                filter=None
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                if result.get('id'):
                    doc_id = result['id']
                    if doc_id not in seen_docs:
                        # Calculate internal knowledge relevance
                        score = self._calculate_internal_knowledge_relevance(result, components)
                        
                        # Boost score for specific technical terms
                        if specific_technical_terms:
                            content = (result.get('content', '') + ' ' + result.get('filename', '')).lower()
                            for term in specific_technical_terms:
                                if term.lower() in content:
                                    score += 0.3  # Significant boost for exact matches
                        
                        if score >= 0.2:  # Threshold for internal knowledge relevance
                            result['internal_knowledge_score'] = score
                            relevant_docs.append(result)
                            seen_docs.add(doc_id)
            
            # Sort by internal knowledge relevance score
            relevant_docs.sort(key=lambda x: x.get('internal_knowledge_score', 0), reverse=True)
            
            logger.info("Internal knowledge document search completed", 
                       total_found=len(relevant_docs),
                       specific_terms=specific_technical_terms,
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Internal knowledge document search failed", error=str(e))
            return []

    def _extract_specific_technical_terms(self, search_terms: str) -> List[str]:
        """Extract specific technical terms that should be searched exactly."""
        search_lower = search_terms.lower()
        
        # List of specific technical terms that should be searched exactly
        technical_terms = [
            'seismic strengthening', 'seismic retrofit', 'earthquake strengthening',
            'liquefaction', 'lateral loads', 'shear walls', 'base isolation',
            'moment frame', 'steel bracing', 'concrete shear wall',
            'foundation upgrade', 'pile foundation', 'deep foundation',
            'wind load', 'snow load', 'live load', 'dead load',
            'building consent', 'producer statement', 'ps1', 'ps3', 'ps4',
            'structural engineer', 'geotechnical engineer', 'senior engineer',
            'project notes', 'design notes', 'calculation notes',
            'structural calculations', 'foundation design', 'steel design',
            'concrete design', 'timber design', 'masonry design'
        ]
        
        found_terms = []
        for term in technical_terms:
            if term in search_lower:
                found_terms.append(term)
        
        return found_terms

    def _calculate_cost_time_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches cost/time analysis criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '') + ' ' +
            (document.get('folder') or '')
        ).lower()
        
        score = 0.0
        
        # High-value cost/time indicators
        high_value_terms = {
            'fee_proposal': ['fee proposal', 'proposal', 'quote', 'estimate'],
            'timeline_docs': ['timeline', 'schedule', 'milestone', 'phase'],
            'cost_analysis': ['cost', 'fee', 'budget', 'price'],
            'scope_documents': ['scope', 'brief', 'specification', 'requirements'],
            'scope_changes': ['scope expanded', 'additional work', 'scope change', 'scope increased', 'extra scope'],
            'project_reports': ['report', 'summary', 'review', 'analysis']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators
        doc_type_indicators = {
            'proposal': 0.35,       # Fee proposals likely to contain cost/time info
            'report': 0.25,         # Project reports may contain timeline info
            'brief': 0.3,           # Project briefs contain scope info
            'correspondence': 0.2,  # Emails may discuss timelines/costs
            'memo': 0.25,           # Internal memos about project status
            'schedule': 0.4,        # Schedules contain timeline info
            'budget': 0.4,          # Budget documents contain cost info
            'scope': 0.35,          # Scope documents contain expansion info
            'variation': 0.4,       # Variations indicate scope changes
            'change': 0.3,          # Change documents indicate scope evolution
            'additional': 0.25      # Additional work documents
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches with higher weight for cost/time terms
        for category in ['timeline_types', 'cost_types', 'scope_aspects']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Project type matches
        for component in components.get('project_types', []):
            if component.replace('_', ' ') in content:
                score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    def _calculate_best_practices_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches best practices criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '')
        ).lower()
        
        score = 0.0
        
        # High-value best practices indicators
        high_value_terms = {
            'methodology': ['methodology', 'approach', 'method', 'procedure'],
            'template': ['template', 'standard', 'format', 'form'],
            'practice': ['practice', 'guideline', 'protocol', 'process'],
            'calculation': ['calculation', 'calc', 'analysis', 'design'],
            'specification': ['specification', 'spec', 'requirement', 'criteria'],
            'checklist': ['checklist', 'check', 'verification', 'review']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators for best practices
        doc_type_indicators = {
            'template': 0.4,        # Templates are direct best practices
            'standard': 0.4,        # Standards contain best practices
            'guideline': 0.35,      # Guidelines are best practices
            'procedure': 0.35,      # Procedures are methodologies
            'manual': 0.3,          # Manuals contain practices
            'specification': 0.3,   # Specs contain standard approaches
            'calculation': 0.25,    # Calculations show methods
            'report': 0.2,          # Reports may contain methodologies
            'methodology': 0.4,     # Direct methodology documents
            'approach': 0.3,        # Approach documents
            'process': 0.3,         # Process documents
            'checklist': 0.35       # Checklists are templates
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches
        for category in ['practice_types', 'template_types', 'methodology_types']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Scope and deliverable matches
        for category in ['scope_areas', 'deliverable_types']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    def _calculate_materials_methods_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches materials/methods criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '')
        ).lower()
        
        score = 0.0
        
        # High-value materials/methods indicators
        high_value_terms = {
            'material_selection': ['material selection', 'chosen', 'selected', 'opted'],
            'comparison': ['comparison', 'compared', 'versus', 'vs', 'alternative'],
            'decision': ['decision', 'rationale', 'reason', 'why', 'because'],
            'performance': ['performance', 'strength', 'durability', 'behavior'],
            'construction': ['construction', 'buildability', 'installation', 'erection'],
            'cost_benefit': ['cost', 'economic', 'budget', 'expensive', 'cheaper']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators for materials/methods
        doc_type_indicators = {
            'specification': 0.4,   # Specs contain material choices
            'report': 0.3,          # Reports explain decisions
            'calculation': 0.3,     # Calcs show material properties
            'comparison': 0.4,      # Direct comparison documents
            'assessment': 0.35,     # Assessments compare options
            'analysis': 0.3,        # Analysis documents
            'design': 0.25,         # Design docs show choices
            'structural': 0.2,      # Structural docs use materials
            'methodology': 0.3,     # Methodologies explain approaches
            'rationale': 0.4,       # Rationale explains decisions
            'option': 0.35,         # Option documents compare
            'alternative': 0.35     # Alternative assessments
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches
        for category in ['material_types', 'structural_systems', 'comparison_aspects']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Building elements and context matches
        for category in ['building_elements', 'project_contexts', 'decision_factors']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    def _calculate_internal_knowledge_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches internal knowledge criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '')
        ).lower()
        
        score = 0.0
        
        # High-value internal knowledge indicators
        high_value_terms = {
            'engineer_names': ['engineer', 'designed by', 'checked by', 'lead', 'project engineer'],
            'expertise': ['expertise', 'experience', 'specialist', 'expert', 'skilled'],
            'team': ['team', 'staff', 'personnel', 'resource', 'capability'],
            'knowledge': ['knowledge', 'know-how', 'understanding', 'familiar'],
            'skills': ['skills', 'competent', 'qualified', 'proficient', 'capable'],
            'project_involvement': ['involved', 'worked on', 'responsible', 'assigned']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators for internal knowledge
        doc_type_indicators = {
            'cv': 0.4,              # CVs contain expertise info
            'resume': 0.4,          # Resumes contain expertise
            'profile': 0.35,        # Staff profiles
            'org_chart': 0.3,       # Organizational charts
            'project_list': 0.3,    # Project lists show involvement
            'capability': 0.35,     # Capability statements
            'experience': 0.3,      # Experience documents
            'team': 0.25,           # Team documents
            'resource': 0.25,       # Resource allocation docs
            'assignment': 0.2,      # Project assignments
            'bio': 0.35,            # Staff bios
            'expertise': 0.4        # Expertise documents
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches
        for category in ['expertise_areas', 'engineer_roles', 'technical_skills']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Project types and knowledge matches
        for category in ['project_types', 'experience_levels', 'knowledge_types']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    async def _generate_cost_time_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for cost/time insights queries."""
        if not documents:
            return "No cost or timeline information found for your query."
        
        # Group documents by project for better organization
        projects_found = {}
        for doc in documents:
            project_id = self._extract_project_from_document(doc)
            if project_id not in projects_found:
                projects_found[project_id] = {
                    'documents': [],
                    'max_score': 0
                }
            
            projects_found[project_id]['documents'].append(doc)
            projects_found[project_id]['max_score'] = max(
                projects_found[project_id]['max_score'],
                doc.get('cost_time_score', 0)
            )
        
        # Create context from top documents
        context_parts = []
        for i, doc in enumerate(documents[:5]):
            # Use proper Base64 decoding for document info
            doc_info = self._extract_document_info(doc)
            project = doc_info['project_name'] or 'Unknown Project'
            filename = doc_info['filename'] or self._generate_meaningful_filename(doc)
            content_excerpt = doc.get('content', '')[:400]
            
            context_parts.append(f"Document {i+1}: {filename} (Project: {project})\n{content_excerpt}...")
        
        context = "\n\n".join(context_parts)
        
        # Generate AI response focused on cost/time insights
        cost_time_prompt = f"""Based on the following project documents from DTCE, provide a comprehensive answer for this cost/time insights query:

Question: {question}

Cost/Time Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Timeline Insights**: Typical durations, milestones, and project phases from the examples
2. **Cost Analysis**: Fee ranges, budget information, and cost factors from similar projects
3. **Scope Evolution**: Examples of how project scope changed during development
4. **Project Comparisons**: How similar projects compared in terms of cost and timeline
5. **Lessons Learned**: Key insights for planning similar future projects

Focus on extracting specific numerical data, timeframes, and cost ranges where available. Include project references for context."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior project manager and structural engineer analyzing DTCE project data to provide cost and timeline insights for future project planning."},
                    {"role": "user", "content": cost_time_prompt}
                ],
                temperature=0.3,
                max_tokens=1200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Cost/time answer generation failed", error=str(e))
            return f"Found {len(documents)} relevant project examples across {len(projects_found)} projects. Please review the source documents for detailed cost and timeline information."

    async def _generate_best_practices_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for best practices queries."""
        if not documents:
            return "No best practices or templates found for your query."
        
        # Prepare document context
        context = ""
        for i, doc in enumerate(documents[:10]):  # Limit to top 10 for context
            project_info = self._extract_project_from_document(doc)
            content_preview = (doc.get('content') or '')[:800]
            
            context += f"""
Document {i+1}: {doc.get('filename', 'Unknown')}
Project: {project_info}
Content: {content_preview}...

"""
        
        # Generate AI response focused on best practices
        best_practices_prompt = f"""Based on the following DTCE project documents, provide comprehensive best practices guidance for this query:

Question: {question}

Best Practices Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Standard Approaches**: Common methodologies and approaches used by DTCE for similar work
2. **Templates & Tools**: Available templates, calculation sheets, or standard documents
3. **Design Methodologies**: Proven design processes and analytical approaches
4. **Quality Processes**: Standard checking procedures, review processes, and QA methods
5. **Documentation Standards**: Typical report formats, drawing standards, and deliverable requirements
6. **Lessons & Recommendations**: Key insights and recommendations for best practice implementation

Focus on extracting specific methodologies, standard approaches, and practical guidance that can be applied to similar projects."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a senior structural engineering consultant providing best practices guidance based on DTCE's project experience."},
                    {"role": "user", "content": best_practices_prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Best practices answer generation failed", error=str(e))
            return "I encountered an error while analyzing the best practices information. Please try refining your query."

    async def _generate_materials_methods_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for materials/methods queries."""
        if not documents:
            return "No materials or methods comparison information found for your query."
        
        # Prepare document context
        context = ""
        for i, doc in enumerate(documents[:10]):  # Limit to top 10 for context
            project_info = self._extract_project_from_document(doc)
            content_preview = (doc.get('content') or '')[:800]
            
            context += f"""
Document {i+1}: {doc.get('filename', 'Unknown')}
Project: {project_info}
Content: {content_preview}...

"""
        
        # Generate AI response focused on materials/methods
        materials_methods_prompt = f"""Based on the following DTCE project documents, provide comprehensive materials and methods analysis for this query:

Question: {question}

Materials/Methods Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Material Comparisons**: Specific examples of material choices and comparisons from similar projects
2. **Decision Rationale**: Reasons why certain materials or methods were chosen over alternatives
3. **Performance Considerations**: How materials performed in terms of structural, cost, and construction factors
4. **Construction Methods**: Different construction approaches used and their relative merits
5. **Project Context**: How site conditions, project requirements, or other factors influenced material/method selection
6. **Recommendations**: Guidance on when to choose specific materials or methods based on project characteristics

Focus on extracting specific examples, decision criteria, and practical guidance for material and method selection."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a senior structural engineering consultant providing materials and methods guidance based on DTCE's project experience."},
                    {"role": "user", "content": materials_methods_prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Materials/methods answer generation failed", error=str(e))
            return "I encountered an error while analyzing the materials and methods information. Please try refining your query."

    async def _generate_internal_knowledge_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for internal knowledge queries."""
        if not documents:
            return "No internal knowledge or expertise information found for your query."
        
        # Prepare document context
        context = ""
        for i, doc in enumerate(documents[:10]):  # Limit to top 10 for context
            project_info = self._extract_project_from_document(doc)
            content_preview = (doc.get('content') or '')[:800]
            
            context += f"""
Document {i+1}: {doc.get('filename', 'Unknown')}
Project: {project_info}
Content: {content_preview}...

"""
        
        # Generate AI response focused on internal knowledge
        internal_knowledge_prompt = f"""Based on the following DTCE project documents, provide comprehensive internal knowledge and expertise information for this query:

Question: {question}

Internal Knowledge Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Team Expertise**: Engineers and their areas of specialization and experience
2. **Project Experience**: Specific projects and the expertise involved in their delivery
3. **Technical Capabilities**: Software skills, analysis capabilities, and specialized knowledge areas
4. **Knowledge Areas**: Specific technical domains where DTCE has demonstrated expertise
5. **Resource Allocation**: Insights into how expertise is distributed across the team
6. **Capability Recommendations**: Suggestions for leveraging internal expertise for similar future projects

Focus on identifying specific engineers, their expertise areas, and practical guidance for knowledge utilization within DTCE."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an internal knowledge management system providing expertise mapping and capability insights for DTCE."},
                    {"role": "user", "content": internal_knowledge_prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Internal knowledge answer generation failed", error=str(e))
            return "I encountered an error while analyzing the internal knowledge information. Please try refining your query."

    def _format_cost_time_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format cost/time document sources with enhanced context."""
        sources = []
        
        for doc in documents[:5]:
            cost_time_score = doc.get('cost_time_score', 0)
            
            # Use comprehensive document info extraction
            doc_info = self._extract_document_info(doc)
            filename = doc_info['filename']
            project_id = doc_info['project_id'] or 'Unknown Project'
            
            # Create enhanced excerpt with cost/time context
            content = doc.get('content', '')
            cost_time_indicators = ['cost', 'fee', 'budget', 'timeline', 'duration', 'milestone', 'scope']
            
            excerpt = ""
            if content:
                # Look for sentences containing cost/time indicators
                sentences = content.split('.')
                for sentence in sentences:
                    if any(indicator in sentence.lower() for indicator in cost_time_indicators):
                        excerpt = sentence.strip()[:200] + "..."
                        break
                
                if not excerpt:
                    excerpt = content[:250] + "..." if len(content) > 250 else content
            
            sources.append({
                'filename': filename,
                'project_id': project_id,
                'relevance_score': doc.get('@search.score', cost_time_score),
                'cost_time_score': round(cost_time_score, 2),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': excerpt,
                'cost_time_focus': components['summary'],
                'folder_path': doc_info['folder_path']
            })
        
        return sources

    async def _handle_best_practices_templates_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about standard approaches, best practices, calculation templates, and design methodologies."""
        try:
            logger.info("Processing best practices/templates query", question=question)
            
            # Extract best practices components from the question
            bp_components = self._extract_best_practices_components(question)
            
            # Build search terms focused on templates, standards, and methodologies
            search_terms = self._build_best_practices_search_terms(question, bp_components)
            
            # Search for best practices and template documents
            relevant_docs = await self._search_best_practices_documents(search_terms, bp_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific best practices or templates for: {bp_components.get('summary', question)}. Try searching for design guides, calculation sheets, or methodology documents.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'best_practices_templates',
                    'bp_components': bp_components
                }
            
            # Generate AI answer focused on best practices and templates
            answer = await self._generate_best_practices_answer(question, relevant_docs, bp_components)
            sources = self._format_best_practices_sources(relevant_docs, bp_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'best_practices_templates',
                'bp_components': bp_components
            }
            
        except Exception as e:
            logger.error("Best practices/templates query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for best practices and templates. Please try searching for specific design methods or calculation approaches.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _handle_materials_methods_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about materials comparisons, construction methods, and technical specifications."""
        try:
            logger.info("Processing materials/methods query", question=question)
            
            # Extract materials/methods components from the question
            mm_components = self._extract_materials_methods_components(question)
            
            # Build search terms focused on materials and methods
            search_terms = self._build_materials_methods_search_terms(question, mm_components)
            
            # Search for materials and methods documents
            relevant_docs = await self._search_materials_methods_documents(search_terms, mm_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific materials or methods information for: {mm_components.get('summary', question)}. Try searching for specification documents, material reports, or construction method comparisons.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'materials_methods',
                    'mm_components': mm_components
                }
            
            # Generate AI answer focused on materials and methods
            answer = await self._generate_materials_methods_answer(question, relevant_docs, mm_components)
            sources = self._format_materials_methods_sources(relevant_docs, mm_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'materials_methods',
                'mm_components': mm_components
            }
            
        except Exception as e:
            logger.error("Materials/methods query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for materials and methods information. Please try searching for specific material types or construction techniques.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _handle_internal_knowledge_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about internal team expertise, engineer experience, and knowledge mapping."""
        try:
            logger.info("Processing internal knowledge query", question=question)
            
            # Extract internal knowledge components from the question
            ik_components = self._extract_internal_knowledge_components(question)
            
            # Build search terms focused on engineer expertise and internal knowledge
            search_terms = self._build_internal_knowledge_search_terms(question, ik_components)
            
            # Search for internal knowledge documents
            relevant_docs = await self._search_internal_knowledge_documents(search_terms, ik_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific internal knowledge or expertise information for: {ik_components.get('summary', question)}. Try searching for specific engineer names, project notes, or technical specializations.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'internal_knowledge',
                    'ik_components': ik_components
                }
            
            # Generate AI answer focused on internal knowledge and expertise
            answer = await self._generate_internal_knowledge_answer(question, relevant_docs, ik_components)
            sources = self._format_internal_knowledge_sources(relevant_docs, ik_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'internal_knowledge',
                'ik_components': ik_components
            }
            
        except Exception as e:
            logger.error("Internal knowledge query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for internal knowledge and expertise information. Please try searching for specific engineers or technical areas.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _extract_best_practices_components(self, question: str) -> Dict[str, Any]:
        """Extract best practices and templates components from the query."""
        question_lower = question.lower()
        
        components = {
            'practice_types': [],
            'template_types': [],
            'methodology_types': [],
            'scope_areas': [],
            'deliverable_types': [],
            'summary': ''
        }
        
        # Practice types
        practice_types = {
            'standard_approach': ['standard approach', 'typical approach', 'usual method', 'standard method', 'common practice'],
            'design_process': ['design process', 'design workflow', 'design methodology', 'design approach'],
            'calculation_method': ['calculation method', 'calculation approach', 'analysis method', 'design calculation'],
            'documentation': ['documentation', 'report format', 'report structure', 'document template'],
            'quality_assurance': ['quality assurance', 'qa process', 'checking procedure', 'review process'],
            'coordination': ['coordination', 'interface', 'collaboration', 'team approach']
        }
        
        # Template types
        template_types = {
            'calculation_template': ['calculation template', 'calc template', 'spreadsheet template', 'calculation sheet'],
            'report_template': ['report template', 'document template', 'report format', 'standard report'],
            'drawing_template': ['drawing template', 'drawing format', 'standard drawing', 'cad template'],
            'specification': ['specification', 'spec template', 'technical specification', 'design spec'],
            'checklist': ['checklist', 'check list', 'verification list', 'review checklist'],
            'procedure': ['procedure', 'process document', 'methodology', 'step-by-step']
        }
        
        # Methodology types
        methodology_types = {
            'structural_analysis': ['structural analysis', 'structural design', 'analysis method', 'design method'],
            'load_assessment': ['load assessment', 'loading', 'load analysis', 'load calculation'],
            'seismic_design': ['seismic design', 'earthquake design', 'seismic analysis', 'earthquake analysis'],
            'foundation_design': ['foundation design', 'foundation analysis', 'geotechnical design'],
            'steel_design': ['steel design', 'steel structure', 'steel analysis', 'steel member'],
            'concrete_design': ['concrete design', 'concrete structure', 'concrete analysis', 'reinforced concrete']
        }
        
        # Scope areas
        scope_areas = {
            'residential': ['residential', 'house', 'dwelling', 'apartment', 'townhouse'],
            'commercial': ['commercial', 'office', 'retail', 'mixed use', 'commercial building'],
            'industrial': ['industrial', 'warehouse', 'factory', 'manufacturing', 'industrial building'],
            'infrastructure': ['infrastructure', 'bridge', 'civil', 'public works', 'utilities'],
            'alteration': ['alteration', 'renovation', 'refurbishment', 'modification', 'upgrade'],
            'new_build': ['new build', 'new construction', 'greenfield', 'new development']
        }
        
        # Deliverable types
        deliverable_types = {
            'producer_statement': ['producer statement', 'ps1', 'ps2', 'ps3', 'ps4'],
            'structural_drawings': ['structural drawings', 'structural plans', 'engineering drawings'],
            'calculations': ['calculations', 'structural calculations', 'design calculations', 'engineering calculations'],
            'specifications': ['specifications', 'technical specifications', 'material specifications'],
            'reports': ['structural report', 'engineering report', 'assessment report', 'design report'],
            'certificates': ['certificates', 'compliance certificate', 'design certificate']
        }
        
        # Extract components from question
        for category, terms_dict in [
            ('practice_types', practice_types),
            ('template_types', template_types), 
            ('methodology_types', methodology_types),
            ('scope_areas', scope_areas),
            ('deliverable_types', deliverable_types)
        ]:
            for term_type, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(term_type)
        
        # Create summary
        summary_parts = []
        if components['practice_types']:
            summary_parts.append(f"practice types: {', '.join(components['practice_types'])}")
        if components['template_types']:
            summary_parts.append(f"templates: {', '.join(components['template_types'])}")
        if components['methodology_types']:
            summary_parts.append(f"methodologies: {', '.join(components['methodology_types'])}")
        if components['scope_areas']:
            summary_parts.append(f"scope: {', '.join(components['scope_areas'])}")
        if components['deliverable_types']:
            summary_parts.append(f"deliverables: {', '.join(components['deliverable_types'])}")
            
        components['summary'] = '; '.join(summary_parts) if summary_parts else 'general best practices query'
        
        return components

    def _extract_materials_methods_components(self, question: str) -> Dict[str, Any]:
        """Extract materials and methods comparison components from the query."""
        question_lower = question.lower()
        
        components = {
            'material_types': [],
            'structural_systems': [],
            'comparison_aspects': [],
            'building_elements': [],
            'project_contexts': [],
            'decision_factors': [],
            'summary': ''
        }
        
        # Material types
        material_types = {
            'concrete': ['concrete', 'reinforced concrete', 'precast concrete', 'in-situ concrete', 'prestressed concrete'],
            'steel': ['steel', 'structural steel', 'steel frame', 'steel structure', 'cold-formed steel'],
            'timber': ['timber', 'wood', 'laminated timber', 'glulam', 'engineered timber', 'clt'],
            'masonry': ['masonry', 'brick', 'block', 'concrete block', 'clay brick', 'stone'],
            'composite': ['composite', 'steel-concrete composite', 'hybrid', 'mixed construction'],
            'other': ['aluminum', 'aluminium', 'fibre reinforced', 'frp', 'carbon fibre']
        }
        
        # Structural systems
        structural_systems = {
            'frame': ['frame', 'moment frame', 'braced frame', 'steel frame', 'concrete frame'],
            'wall': ['wall', 'shear wall', 'load bearing wall', 'concrete wall', 'masonry wall'],
            'slab': ['slab', 'floor slab', 'concrete slab', 'composite slab', 'precast slab'],
            'foundation': ['foundation', 'pile', 'pad foundation', 'strip foundation', 'raft foundation'],
            'roof': ['roof', 'roof structure', 'roof framing', 'roof truss', 'portal frame'],
            'tilt_slab': ['tilt slab', 'tilt-up', 'tilt panel', 'precast panel']
        }
        
        # Comparison aspects
        comparison_aspects = {
            'cost': ['cost', 'price', 'budget', 'economic', 'financial', 'expensive', 'cheap'],
            'performance': ['performance', 'structural performance', 'seismic performance', 'strength'],
            'construction': ['construction', 'buildability', 'constructability', 'installation', 'erection'],
            'time': ['time', 'duration', 'schedule', 'fast', 'quick', 'slow', 'construction time'],
            'durability': ['durability', 'longevity', 'maintenance', 'life cycle', 'weathering'],
            'sustainability': ['sustainability', 'environmental', 'carbon', 'embodied energy', 'green']
        }
        
        # Building elements
        building_elements = {
            'floors': ['floor', 'floor slab', 'suspended floor', 'ground floor', 'upper floor'],
            'walls': ['wall', 'external wall', 'internal wall', 'partition wall', 'structural wall'],
            'columns': ['column', 'pillar', 'post', 'vertical support', 'structural column'],
            'beams': ['beam', 'girder', 'lintel', 'header', 'structural beam'],
            'foundations': ['foundation', 'footing', 'pile', 'base', 'substructure'],
            'connections': ['connection', 'joint', 'fastener', 'weld', 'bolt']
        }
        
        # Project contexts
        project_contexts = {
            'seismic': ['seismic', 'earthquake', 'seismic zone', 'high seismic', 'seismic design'],
            'high_rise': ['high rise', 'multi-storey', 'tall building', 'tower', 'high building'],
            'industrial': ['industrial', 'warehouse', 'factory', 'heavy loading', 'crane'],
            'residential': ['residential', 'house', 'apartment', 'dwelling', 'housing'],
            'commercial': ['commercial', 'office', 'retail', 'mixed use'],
            'coastal': ['coastal', 'marine', 'salt', 'corrosive', 'exposure']
        }
        
        # Decision factors
        decision_factors = {
            'client_preference': ['client preference', 'client requirement', 'owner preference'],
            'site_constraints': ['site constraints', 'access', 'site conditions', 'ground conditions'],
            'code_requirements': ['code requirements', 'building code', 'standards', 'compliance'],
            'engineer_experience': ['experience', 'expertise', 'familiarity', 'knowledge'],
            'contractor_capability': ['contractor', 'builder', 'construction capability', 'trade'],
            'availability': ['availability', 'supply', 'material availability', 'lead time']
        }
        
        # Extract components from question
        for category, terms_dict in [
            ('material_types', material_types),
            ('structural_systems', structural_systems),
            ('comparison_aspects', comparison_aspects),
            ('building_elements', building_elements),
            ('project_contexts', project_contexts),
            ('decision_factors', decision_factors)
        ]:
            for term_type, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(term_type)
        
        # Create summary
        summary_parts = []
        if components['material_types']:
            summary_parts.append(f"materials: {', '.join(components['material_types'])}")
        if components['structural_systems']:
            summary_parts.append(f"systems: {', '.join(components['structural_systems'])}")
        if components['comparison_aspects']:
            summary_parts.append(f"comparing: {', '.join(components['comparison_aspects'])}")
        if components['building_elements']:
            summary_parts.append(f"elements: {', '.join(components['building_elements'])}")
        if components['project_contexts']:
            summary_parts.append(f"context: {', '.join(components['project_contexts'])}")
        if components['decision_factors']:
            summary_parts.append(f"factors: {', '.join(components['decision_factors'])}")
            
        components['summary'] = '; '.join(summary_parts) if summary_parts else 'general materials/methods comparison'
        
        return components

    def _extract_internal_knowledge_components(self, question: str) -> Dict[str, Any]:
        """Extract internal knowledge and expertise components from the query."""
        question_lower = question.lower()
        
        components = {
            'expertise_areas': [],
            'engineer_roles': [],
            'project_types': [],
            'technical_skills': [],
            'experience_levels': [],
            'knowledge_types': [],
            'summary': ''
        }
        
        # Expertise areas
        expertise_areas = {
            'structural_design': ['structural design', 'structural engineering', 'structural analysis'],
            'seismic_engineering': ['seismic', 'earthquake', 'seismic design', 'seismic analysis'],
            'geotechnical': ['geotechnical', 'foundation', 'soil', 'ground', 'pile design'],
            'steel_structures': ['steel', 'steel structures', 'steel design', 'steel frame'],
            'concrete_structures': ['concrete', 'reinforced concrete', 'concrete design', 'precast'],
            'timber_structures': ['timber', 'wood', 'timber design', 'engineered timber'],
            'masonry': ['masonry', 'brick', 'block', 'unreinforced masonry'],
            'assessment': ['assessment', 'existing building', 'strengthening', 'evaluation'],
            'tilt_slab': ['tilt slab', 'tilt-up', 'precast', 'tilt panel'],
            'industrial': ['industrial', 'warehouse', 'crane', 'heavy loading'],
            'high_rise': ['high rise', 'multi-storey', 'tall building', 'tower'],
            'bridge': ['bridge', 'civil', 'infrastructure', 'transportation']
        }
        
        # Engineer roles
        engineer_roles = {
            'senior_engineer': ['senior engineer', 'principal engineer', 'lead engineer', 'senior'],
            'project_engineer': ['project engineer', 'project lead', 'project manager'],
            'design_engineer': ['design engineer', 'designer', 'design team'],
            'graduate_engineer': ['graduate engineer', 'junior engineer', 'graduate'],
            'specialist': ['specialist', 'expert', 'consultant', 'technical specialist'],
            'checker': ['checker', 'reviewer', 'peer reviewer', 'design checker']
        }
        
        # Project types for experience
        project_types = {
            'residential': ['residential', 'house', 'apartment', 'dwelling', 'housing'],
            'commercial': ['commercial', 'office', 'retail', 'mixed use'],
            'industrial': ['industrial', 'warehouse', 'factory', 'manufacturing'],
            'infrastructure': ['infrastructure', 'bridge', 'civil', 'public works'],
            'education': ['education', 'school', 'university', 'institutional'],
            'healthcare': ['healthcare', 'hospital', 'medical', 'clinic'],
            'alteration': ['alteration', 'renovation', 'strengthening', 'seismic upgrade']
        }
        
        # Technical skills
        technical_skills = {
            'software': ['software', 'etabs', 'sap', 'spacegass', 'tekla', 'revit', 'autocad'],
            'analysis': ['analysis', 'finite element', 'dynamic analysis', 'non-linear'],
            'design_codes': ['design codes', 'nzs', 'standards', 'eurocode', 'building code'],
            'calculation': ['calculation', 'hand calculation', 'spreadsheet', 'verification'],
            'modeling': ['modeling', 'modelling', '3d model', 'structural model'],
            'detailing': ['detailing', 'connection design', 'reinforcement detailing']
        }
        
        # Experience levels
        experience_levels = {
            'experienced': ['experienced', 'senior', 'expert', 'specialist', 'veteran'],
            'intermediate': ['intermediate', 'mid-level', 'competent', 'capable'],
            'junior': ['junior', 'graduate', 'new', 'recent', 'entry level'],
            'highly_experienced': ['highly experienced', 'very experienced', 'extensive experience']
        }
        
        # Knowledge types
        knowledge_types = {
            'technical_knowledge': ['technical knowledge', 'engineering knowledge', 'design knowledge'],
            'project_experience': ['project experience', 'practical experience', 'hands-on'],
            'specialist_expertise': ['specialist expertise', 'specialized knowledge', 'niche'],
            'software_skills': ['software skills', 'technical skills', 'computer skills'],
            'industry_knowledge': ['industry knowledge', 'market knowledge', 'sector'],
            'mentoring': ['mentoring', 'training', 'guidance', 'teaching']
        }
        
        # Extract components from question
        for category, terms_dict in [
            ('expertise_areas', expertise_areas),
            ('engineer_roles', engineer_roles),
            ('project_types', project_types),
            ('technical_skills', technical_skills),
            ('experience_levels', experience_levels),
            ('knowledge_types', knowledge_types)
        ]:
            for term_type, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(term_type)
        
        # Create summary
        summary_parts = []
        if components['expertise_areas']:
            summary_parts.append(f"expertise: {', '.join(components['expertise_areas'])}")
        if components['engineer_roles']:
            summary_parts.append(f"roles: {', '.join(components['engineer_roles'])}")
        if components['project_types']:
            summary_parts.append(f"projects: {', '.join(components['project_types'])}")
        if components['technical_skills']:
            summary_parts.append(f"skills: {', '.join(components['technical_skills'])}")
        if components['experience_levels']:
            summary_parts.append(f"level: {', '.join(components['experience_levels'])}")
        if components['knowledge_types']:
            summary_parts.append(f"knowledge: {', '.join(components['knowledge_types'])}")
            
        components['summary'] = '; '.join(summary_parts) if summary_parts else 'general internal knowledge query'
        
        return components

    def _extract_regulatory_components(self, question: str) -> Dict[str, Any]:
        """Extract regulatory, council, and consent components from the query."""
        question_lower = question.lower()
        
        components = {
            'regulatory_bodies': [],
            'challenge_types': [],
            'solution_types': [],
            'building_elements': [],
            'regulatory_processes': [],
            'summary': ''
        }
        
        # Regulatory bodies and authorities
        regulatory_bodies = {
            'council': ['council', 'city council', 'district council', 'regional council', 'local authority'],
            'mbie': ['mbie', 'building and housing', 'ministry of business'],
            'building_consent_authority': ['bca', 'building consent authority', 'consent authority'],
            'engineer': ['engineer', 'structural engineer', 'reviewing engineer'],
            'code_compliance': ['code compliance', 'ccc', 'certificate of code compliance']
        }
        
        # Types of regulatory challenges
        challenge_types = {
            'questioned_calculations': ['questioned', 'queried', 'challenged', 'disputed', 'raised concerns', 'requested clarification'],
            'alternative_solution': ['alternative solution', 'alternative design', 'alternative method', 'departures'],
            'non_compliance': ['non-compliant', 'non-standard', 'non-conforming', 'deviation'],
            'additional_requirements': ['additional requirements', 'further information', 'more detail', 'peer review'],
            'appeals': ['appeal', 'objection', 'dispute', 'disagreement']
        }
        
        # Solution types
        solution_types = {
            'precedent': ['precedent', 'previous approval', 'similar case', 'past example'],
            'engineering_justification': ['engineering justification', 'technical report', 'peer review'],
            'alternative_compliance': ['alternative compliance', 'alternative solution', 'performance-based'],
            'specialist_input': ['specialist', 'expert', 'consultant', 'third party review']
        }
        
        # Building elements commonly requiring special attention
        building_elements = {
            'wind_loads': ['wind load', 'wind pressure', 'wind analysis', 'wind calculations'],
            'seismic': ['seismic', 'earthquake', 'seismic analysis', 'seismic design'],
            'stairs': ['stair', 'staircase', 'stairway', 'step'],
            'bracing': ['bracing', 'lateral stability', 'shear walls', 'diaphragm'],
            'heritage': ['heritage', 'historic', 'conservation', 'character'],
            'fire_safety': ['fire', 'fire safety', 'fire rating', 'egress'],
            'accessibility': ['accessibility', 'disabled access', 'barrier-free']
        }
        
        # Regulatory processes
        regulatory_processes = {
            'consent_application': ['consent application', 'building consent', 'resource consent'],
            'design_review': ['design review', 'plan review', 'structural review'],
            'inspection': ['inspection', 'site visit', 'verification'],
            'certification': ['certification', 'sign-off', 'ps1', 'ps3', 'ps4']
        }
        
        # Extract components
        for category, terms_dict in [
            ('regulatory_bodies', regulatory_bodies),
            ('challenge_types', challenge_types),
            ('solution_types', solution_types),
            ('building_elements', building_elements),
            ('regulatory_processes', regulatory_processes)
        ]:
            for key, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(key)
        
        # Create summary
        summary_parts = []
        if components['regulatory_bodies']:
            summary_parts.append(f"Authority: {', '.join(components['regulatory_bodies'])}")
        if components['challenge_types']:
            summary_parts.append(f"Challenge: {', '.join(components['challenge_types'])}")
        if components['building_elements']:
            summary_parts.append(f"Element: {', '.join(components['building_elements'])}")
        if components['solution_types']:
            summary_parts.append(f"Solution: {', '.join(components['solution_types'])}")
        if components['regulatory_processes']:
            summary_parts.append(f"Process: {', '.join(components['regulatory_processes'])}")
            
        components['summary'] = " | ".join(summary_parts) if summary_parts else question
        
        return components

    def _build_regulatory_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms optimized for finding regulatory/consent documents."""
        search_terms = []
        
        # Add original question
        search_terms.append(question)
        
        # Add regulatory-specific terms
        regulatory_keywords = [
            # Council communication
            'council', 'building consent', 'consent application', 'council response',
            'council query', 'council comments', 'peer review', 'reviewing engineer',
            
            # Alternative solutions
            'alternative solution', 'alternative design', 'alternative method',
            'departures', 'non-standard', 'special design',
            
            # Documentation types
            'engineering report', 'technical justification', 'design rationale',
            'correspondence', 'email', 'letter', 'memo', 'response',
            
            # Regulatory processes  
            'building consent', 'resource consent', 'code compliance',
            'ps1', 'ps3', 'ps4', 'certificate', 'approval'
        ]
        
        # Add component-specific terms
        for category in ['regulatory_bodies', 'challenge_types', 'solution_types', 'building_elements', 'regulatory_processes']:
            search_terms.extend(components.get(category, []))
        
        # Add regulatory keywords
        search_terms.extend(regulatory_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:20])  # Limit to prevent too long query

    async def _search_regulatory_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing regulatory/consent information."""
        try:
            # Search with regulatory focus
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                search_mode="any"
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                # Score documents based on regulatory relevance
                score = self._calculate_regulatory_relevance(result, components)
                
                if score > 0.2:  # Lower threshold for regulatory docs as they might be more subtle
                    # Avoid duplicate documents
                    doc_id = result.get('id', result.get('filename', ''))
                    if doc_id not in seen_docs:
                        result['regulatory_score'] = score
                        relevant_docs.append(result)
                        seen_docs.add(doc_id)
            
            # Sort by regulatory relevance score
            relevant_docs.sort(key=lambda x: x.get('regulatory_score', 0), reverse=True)
            
            logger.info("Regulatory document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Regulatory document search failed", error=str(e))
            return []

    def _calculate_regulatory_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches regulatory precedent criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '') + ' ' +
            (document.get('folder') or '')
        ).lower()
        
        score = 0.0
        
        # High-value regulatory indicators
        high_value_terms = {
            'council correspondence': ['council', 'email', 'correspondence', 'letter', 'response'],
            'consent process': ['consent', 'application', 'approval', 'building consent'],
            'engineering review': ['peer review', 'reviewing engineer', 'technical review'],
            'alternative solutions': ['alternative', 'solution', 'departures', 'special'],
            'regulatory challenge': ['questioned', 'queried', 'concerns', 'clarification', 'additional']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators
        doc_type_indicators = {
            'correspondence': 0.3,  # emails, letters likely to contain regulatory discussions
            'report': 0.2,          # engineering reports may contain justifications
            'memo': 0.25,           # internal memos about regulatory issues
            'response': 0.3,        # responses to council queries
            'justification': 0.35,  # technical justifications
            'precedent': 0.4        # explicit precedent discussions
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches with higher weight for regulatory terms
        for category in ['regulatory_bodies', 'challenge_types', 'solution_types']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Building element matches
        for component in components.get('building_elements', []):
            if component.replace('_', ' ') in content:
                score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    async def _generate_regulatory_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for regulatory precedent queries."""
        if not documents:
            return "No regulatory precedents found for your query."
        
        # Group documents by project for better organization
        projects_found = {}
        for doc in documents:
            project_id = self._extract_project_from_document(doc)
            if project_id not in projects_found:
                projects_found[project_id] = {
                    'documents': [],
                    'max_score': 0
                }
            
            projects_found[project_id]['documents'].append(doc)
            projects_found[project_id]['max_score'] = max(
                projects_found[project_id]['max_score'],
                doc.get('regulatory_score', 0)
            )
        
        # Create context from top documents
        context_parts = []
        for i, doc in enumerate(documents[:5]):
            project = doc.get('project_name', 'Unknown Project')
            filename = doc.get('filename', 'Unknown Document')
            content_excerpt = doc.get('content', '')[:400]
            
            context_parts.append(f"Document {i+1}: {filename} (Project: {project})\n{content_excerpt}...")
        
        context = "\n\n".join(context_parts)
        
        # Generate AI response focused on regulatory precedents
        regulatory_prompt = f"""Based on the following regulatory and consent documents from DTCE projects, provide a comprehensive answer for this regulatory precedent query:

Question: {question}

Regulatory Components Identified: {components['summary']}

Relevant Regulatory Documents:
{context}

Please provide:
1. **Regulatory Precedents**: Specific examples of how similar regulatory challenges were handled
2. **Council Interactions**: How councils responded to these situations and what they required
3. **Alternative Solutions**: Any alternative compliance methods or special designs that were approved
4. **Documentation Approach**: How DTCE justified their approach to regulatory authorities
5. **Lessons Learned**: Key insights for handling similar regulatory challenges in future

Focus on practical regulatory guidance that can be applied to similar situations. Include specific project references where relevant."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior structural engineer analyzing DTCE regulatory precedents and consent processes to provide guidance on navigating building consent challenges."},
                    {"role": "user", "content": regulatory_prompt}
                ],
                temperature=0.3,
                max_tokens=1200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Regulatory answer generation failed", error=str(e))
            return f"Found {len(documents)} relevant regulatory examples across {len(projects_found)} projects. Please review the source documents for detailed regulatory precedent information."

    def _format_regulatory_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format regulatory document sources with enhanced context."""
        sources = []
        
        for doc in documents[:5]:
            regulatory_score = doc.get('regulatory_score', 0)
            filename = doc.get('filename', 'Unknown Document')
            
            # Handle case where filename is literally 'None' or missing
            if not filename or filename == 'None':
                # Try to create a meaningful filename from content
                filename = self._generate_meaningful_filename(doc)
            
            sources.append({
                'filename': filename,
                'project_id': self._extract_project_from_document(doc),
                'relevance_score': doc.get('@search.score', regulatory_score),
                'regulatory_score': round(regulatory_score, 2),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': (doc.get('content', '')[:250] + '...') if doc.get('content') else '',
                'regulatory_focus': components['summary']
            })
        
        return sources

    async def _handle_template_search_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries asking for templates, forms, spreadsheets, or design tools."""
        try:
            logger.info("Processing template search query", question=question)
            
            # First, analyze the intent - are they asking for templates or asking ABOUT templates?
            intent_analysis = await self._analyze_template_question_intent(question)
            
            if intent_analysis['intent'] == 'process_guidance':
                # They're asking about how to do something, timing, process, etc.
                return await self._provide_template_process_guidance(question, intent_analysis)
            elif intent_analysis['intent'] == 'template_files':
                # They actually want template files
                # Extract template type from question
                template_type = self._identify_template_type(question)
                
                # Search for template documents
                template_docs = self._search_template_documents(question, template_type)
                
                if not template_docs:
                    # If no specific templates found, try a broader search and provide helpful guidance
                    return await self._provide_helpful_template_guidance(question, template_type)
                
                # Format the answer with direct SuiteFiles links
                answer = self._format_template_answer(template_docs, template_type, question)
                sources = self._format_template_sources(template_docs)
                
                return {
                    'answer': answer,
                    'sources': sources,
                    'confidence': 'high',
                    'documents_searched': len(template_docs),
                    'search_type': 'template_search'
                }
            else:
                # Mixed intent or unclear - provide both guidance and templates
                return await self._provide_comprehensive_template_response(question, intent_analysis)
            
        except Exception as e:
            logger.error("Template search query failed", error=str(e), error_type=type(e).__name__)
            # Add more detailed error logging
            import traceback
            logger.error("Template search error traceback", traceback=traceback.format_exc())
            return {
                'answer': 'I encountered an error while searching for templates. Please check SuiteFiles directly or contact your team for template access.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _analyze_template_question_intent(self, question: str) -> Dict[str, Any]:
        """Analyze whether user wants template files or guidance about templates."""
        question_lower = question.lower()
        
        # Process/guidance indicators
        process_indicators = [
            'how long', 'how much time', 'duration', 'take to', 'preparation time',
            'how to', 'process', 'steps', 'procedure', 'requirements', 'what do i need',
            'how do i', 'guidance', 'help with', 'assist', 'explain', 'when to',
            'why', 'what is', 'difference between', 'compare', 'typical',
            'usually', 'normally', 'generally', 'best practice'
        ]
        
        # Template file indicators  
        template_indicators = [
            'template', 'form', 'download', 'file', 'document', 'spreadsheet',
            'get the', 'need the', 'find the', 'access', 'link to', 'copy of'
        ]
        
        process_score = sum(1 for indicator in process_indicators if indicator in question_lower)
        template_score = sum(1 for indicator in template_indicators if indicator in question_lower)
        
        if process_score > template_score:
            return {
                'intent': 'process_guidance',
                'confidence': process_score / len(process_indicators),
                'topic': self._extract_template_topic(question)
            }
        elif template_score > process_score:
            return {
                'intent': 'template_files',
                'confidence': template_score / len(template_indicators),
                'topic': self._extract_template_topic(question)
            }
        else:
            return {
                'intent': 'mixed',
                'confidence': 0.5,
                'topic': self._extract_template_topic(question)
            }

    def _extract_template_topic(self, question: str) -> str:
        """Extract what type of template they're asking about."""
        question_lower = question.lower()
        
        if any(term in question_lower for term in ['ps1', 'producer statement 1']):
            return 'PS1'
        elif any(term in question_lower for term in ['ps3', 'producer statement 3']):
            return 'PS3'
        elif any(term in question_lower for term in ['ps4', 'producer statement 4']):
            return 'PS4'
        elif 'producer statement' in question_lower:
            return 'producer_statement'
        elif any(term in question_lower for term in ['seismic', 'earthquake']):
            return 'seismic'
        elif any(term in question_lower for term in ['foundation', 'footing']):
            return 'foundation'
        else:
            return 'general'

    async def _provide_template_process_guidance(self, question: str, intent_analysis: Dict) -> Dict[str, Any]:
        """Provide guidance about template processes, timing, requirements, etc."""
        
        topic = intent_analysis['topic']
        
        # Use AI to provide comprehensive guidance
        guidance_prompt = f"""
        The user asked: "{question}"
        
        This is about {topic} in structural engineering context. 
        
        Provide a helpful, practical answer that covers:
        1. Typical timeframes and duration
        2. Process steps and requirements  
        3. Who needs to be involved
        4. Key considerations and best practices
        5. Common challenges or tips
        
        Be specific and practical. Draw from engineering best practices.
        Keep it conversational but professional.
        """
        
        try:
            ai_response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful structural engineering assistant with expertise in New Zealand engineering practices, producer statements, and project processes."
                    },
                    {"role": "user", "content": guidance_prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            answer = ai_response.choices[0].message.content
            
            # Add specific template links if relevant
            if topic in ['PS1', 'PS3', 'PS4', 'producer_statement']:
                answer += "\n\n📋 **Need the actual templates?** Let me know and I can help you find the specific template files in SuiteFiles."
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'high',
                'documents_searched': 0,
                'search_type': 'process_guidance'
            }
            
        except Exception as e:
            logger.warning(f"Failed to get AI guidance: {e}")
            
            # Fallback to predefined guidance
            fallback_answer = self._get_fallback_guidance(topic, question)
            
            return {
                'answer': fallback_answer,
                'sources': [],
                'confidence': 'medium',
                'documents_searched': 0,
                'search_type': 'fallback_guidance'
            }

    def _get_fallback_guidance(self, topic: str, question: str) -> str:
        """Provide fallback guidance when AI is unavailable."""
        
        if topic == 'PS1':
            return """**PS1 (Producer Statement Design) - Typical Preparation Time:**

⏱️ **Duration:** Usually 2-4 hours for experienced engineers, depending on complexity

📋 **Process Steps:**
1. **Design Review** (30-60 mins) - Review structural calculations and drawings
2. **Code Compliance Check** (45-90 mins) - Verify compliance with building codes  
3. **Documentation** (30-60 mins) - Complete PS1 form with design details
4. **Quality Review** (15-30 mins) - Internal review before signing

👤 **Requirements:**
• Must be completed by a Chartered Professional Engineer (CPEng)
• Design must be substantially complete
• All relevant calculations and drawings available

💡 **Tips for Efficiency:**
• Have all design documentation ready before starting
• Use standardized templates and checklists
• Allow extra time for complex or unusual structures
• Consider peer review for high-risk projects

Need the PS1 template files? Let me know and I can help you find them in SuiteFiles."""
            
        elif topic in ['PS3', 'PS4', 'producer_statement']:
            return f"""**Producer Statement Preparation - General Guidance:**

⏱️ **Typical Timeline:** 1-4 hours depending on statement type and project complexity

📋 **Key Considerations:**
• PS1 (Design): 2-4 hours - requires complete design review
• PS3 (Construction): 1-3 hours - depends on construction complexity  
• PS4 (Construction Review): 2-3 hours - thorough inspection required

👤 **Who Can Prepare:**
• Must be a Chartered Professional Engineer (CPEng)
• Relevant experience in the specific area required
• Current practicing certificate essential

💡 **Best Practices:**
• Allow adequate time for thorough review
• Keep detailed records of the review process
• Ensure all supporting documentation is available
• Consider the liability implications

Would you like me to help you find specific template files in SuiteFiles?"""
        
        else:
            return f"""**Engineering Process Guidance:**

Based on your question about "{question}", here are some general guidelines:

⏱️ **Planning:** Allow adequate time for thorough preparation and review
📋 **Process:** Follow established procedures and best practices  
👥 **Collaboration:** Involve appropriate team members and stakeholders
📝 **Documentation:** Maintain clear records throughout the process

For specific guidance on your situation, I recommend:
• Consulting with your team lead or senior engineer
• Reviewing relevant standards and guidelines
• Checking DTCE's internal procedures

Would you like me to search for specific templates or documents that might help?"""

    async def _provide_comprehensive_template_response(self, question: str, intent_analysis: Dict) -> Dict[str, Any]:
        """Provide both guidance and template files when intent is mixed."""
        
        # Get the guidance part
        guidance_response = await self._provide_template_process_guidance(question, intent_analysis)
        
        # Get template files
        template_type = self._identify_template_type(question)
        template_docs = self._search_template_documents(question, template_type)
        
        # Combine both
        combined_answer = guidance_response['answer']
        
        if template_docs:
            combined_answer += f"\n\n📁 **Related Templates Found:**\n"
            # Add a brief list of key templates (not the full dump)
            key_templates = template_docs[:3]  # Just show top 3
            for doc in key_templates:
                doc_info = self._extract_document_info(doc)
                filename = doc_info['filename']
                if filename and filename != 'Unknown':
                    combined_answer += f"• {filename}\n"
            
            if len(template_docs) > 3:
                combined_answer += f"• ... and {len(template_docs) - 3} more templates available\n"
                
            combined_answer += "\n💡 Ask specifically for \"PS1 templates\" if you need the complete list of template files."
        
        return {
            'answer': combined_answer,
            'sources': guidance_response.get('sources', []),
            'confidence': 'high',
            'documents_searched': len(template_docs) if template_docs else 0,
            'search_type': 'comprehensive_guidance'
        }

    def _identify_template_type(self, question: str) -> str:
        """Identify what type of template the user is looking for using flexible pattern matching."""
        question_lower = question.lower()
        
        # PS Templates - be more flexible with variations
        if any(term in question_lower for term in ['ps1', 'ps 1', 'ps-1', 'producer statement 1', 'producer statement design']):
            return 'PS1'
        elif any(term in question_lower for term in ['ps1a', 'ps 1a', 'ps-1a', 'producer statement 1a']):
            return 'PS1A'
        elif any(term in question_lower for term in ['ps3', 'ps 3', 'ps-3', 'producer statement 3', 'producer statement construction']):
            return 'PS3'
        elif any(term in question_lower for term in ['ps4', 'ps 4', 'ps-4', 'producer statement 4', 'producer statement review']):
            return 'PS4'
        elif any(term in question_lower for term in ['producer statement', 'ps ', ' ps']):
            return 'PS_GENERAL'
            
        # Design and Engineering Spreadsheets - more flexible terms
        elif any(term in question_lower for term in ['timber beam', 'beam design', 'timber design', 'wood beam', 'timber calculator']):
            return 'TIMBER_BEAM_DESIGN'
        elif any(term in question_lower for term in ['concrete beam', 'concrete design', 'concrete calculator', 'reinforced concrete']):
            return 'CONCRETE_DESIGN'
        elif any(term in question_lower for term in ['steel beam', 'steel design', 'steel calculator', 'structural steel']):
            return 'STEEL_DESIGN'
        elif any(term in question_lower for term in ['foundation design', 'foundation calculator', 'footing design']):
            return 'FOUNDATION_DESIGN'
        elif any(term in question_lower for term in ['seismic', 'earthquake', 'seismic design', 'seismic assessment']):
            return 'SEISMIC_DESIGN'
        elif any(term in question_lower for term in ['spreadsheet', 'calculator', 'design tool', 'excel']):
            return 'DESIGN_SPREADSHEET'
            
        # General document types
        elif any(term in question_lower for term in ['checklist', 'check list']):
            return 'CHECKLIST'
        elif any(term in question_lower for term in ['report template', 'report format']):
            return 'REPORT_TEMPLATE'
        elif any(term in question_lower for term in ['template', 'form', 'format', 'example']):
            return 'GENERAL_TEMPLATE'
        
        # If no specific pattern matches, it's unknown - let the search be flexible
        else:
            return 'UNKNOWN'

    def _search_template_documents(self, question: str, template_type: str) -> List[Dict]:
        """Search for template documents in SuiteFiles using comprehensive approach."""
        
        question_lower = question.lower()
        template_docs = []
        
        # Build comprehensive search terms based on the question content
        search_terms = []
        
        # Specific template type searches
        if any(word in question_lower for word in ['ps1', 'producer statement 1']):
            search_terms.extend(['PS1', 'producer statement 1', 'producer statement', 'PS-1'])
        elif any(word in question_lower for word in ['ps3', 'producer statement 3']):
            search_terms.extend(['PS3', 'producer statement 3', 'producer statement', 'PS-3'])
        elif any(word in question_lower for word in ['ps4', 'producer statement 4']):
            search_terms.extend(['PS4', 'producer statement 4', 'producer statement', 'PS-4'])
        elif any(word in question_lower for word in ['timber', 'beam', 'design']):
            search_terms.extend(['timber beam', 'beam design', 'timber design', 'structural design', 'beam calculator'])
        elif any(word in question_lower for word in ['calculation', 'calc']):
            search_terms.extend(['calculation', 'design calc', 'structural calc', 'engineering calc'])
        elif any(word in question_lower for word in ['report', 'assessment']):
            search_terms.extend(['report template', 'assessment template', 'engineering report'])
        
        # Add generic template terms
        if 'template' in question_lower:
            search_terms.append('template')
        if 'spreadsheet' in question_lower:
            search_terms.extend(['spreadsheet', 'calculator', 'design tool'])
        if 'form' in question_lower:
            search_terms.append('form')
        
        # If no specific terms found, extract key words from question
        if not search_terms:
            # Extract meaningful words from the question
            words = [word for word in question_lower.split() if len(word) > 3 and word not in ['the', 'for', 'that', 'with', 'have', 'uses', 'used']]
            search_terms.extend(words[:3])  # Use top 3 meaningful words
        
        logger.info(f"Template search terms: {search_terms}")
        
        # Search with each term
        for search_term in search_terms:
            try:
                # Try both simple and semantic search
                for query_type in ["simple", "semantic"]:
                    response = self.search_client.search(
                        search_text=search_term,
                        search_fields=["filename", "content"],
                        top=15,
                        query_type=query_type
                    )
                    
                    for result in response:
                        doc_dict = dict(result)
                        filename = (doc_dict.get('filename') or '').lower()
                        content = (doc_dict.get('content') or '').lower()
                        
                        # More flexible filtering for useful documents
                        is_useful_doc = (
                            # File type check - include more types
                            any(ext in filename for ext in ['.doc', '.pdf', '.xls', '.xlsx', '.docx', '.ppt', '.pptx']) and
                            # Exclude emails and irrelevant files
                            not any(bad in filename for bad in ['.msg', 'email', 're:', 'fwd:', 'unknown']) and
                            # Include if it has template-like content or relevant keywords
                            (
                                any(keyword in filename for keyword in ['template', 'form', 'blank', 'standard', 'example']) or
                                any(keyword in content[:500] for keyword in search_terms[:2]) or  # Check if search terms appear in content
                                (len(filename) > 5 and any(word in filename for word in search_terms[:2]))
                            )
                        )
                        
                        if is_useful_doc and doc_dict not in template_docs:
                            # Add search relevance score
                            doc_dict['search_relevance'] = result.get('@search.score', 0)
                            template_docs.append(doc_dict)
                            
                    if len(template_docs) >= 10:  # Stop if we have enough results
                        break
                        
            except Exception as e:
                logger.warning(f"Search term '{search_term}' failed: {e}")
                continue
                
        # Sort by relevance score and return top results
        template_docs.sort(key=lambda x: x.get('search_relevance', 0), reverse=True)
        return template_docs[:8]  # Return top 8 most relevant
    
    async def _search_ps1_templates(self) -> List[Dict]:
        """Specific search for PS1 templates with fallback guidance."""
        
        # Search for actual PS1 template files
        ps1_search_terms = [
            "PS1 template",
            "producer statement 1 template", 
            "producer statement template",
            "PS1 form"
        ]
        
        template_docs = []
        
        for search_term in ps1_search_terms:
            results = self.search_client.search(
                search_text=search_term,
                top=5,
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                query_type="simple"
            )
            
            for result in results:
                doc_dict = dict(result)
                filename = (doc_dict.get('filename') or '').lower()
                
                # Very strict filtering for PS1 templates only
                is_ps1_template = (
                    ('ps1' in filename or 'producer statement' in filename) and
                    ('template' in filename or 'form' in filename) and
                    ('.doc' in filename or '.pdf' in filename or '.xls' in filename) and
                    not ('.msg' in filename or 'email' in filename or 're:' in filename)
                )
                
                if is_ps1_template and doc_dict not in template_docs:
                    template_docs.append(doc_dict)
        
        return template_docs

    async def _provide_helpful_template_guidance(self, question: str, template_type: str) -> Dict[str, Any]:
        """Provide comprehensive guidance and perform broader search for ANY template type."""
        
        # First try a broader search with related terms
        broader_results = []
        
        # Create search terms based on template type
        search_terms = []
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['ps1', 'producer statement 1']):
            search_terms = ['producer statement', 'PS1', 'design', 'structural', 'compliance', 'building consent']
        elif any(word in question_lower for word in ['ps2', 'producer statement 2']):
            search_terms = ['producer statement', 'PS2', 'construction monitoring', 'supervision']
        elif any(word in question_lower for word in ['ps3', 'producer statement 3']):
            search_terms = ['producer statement', 'PS3', 'construction review', 'verification']
        elif any(word in question_lower for word in ['ps4', 'producer statement 4']):
            search_terms = ['producer statement', 'PS4', 'completion', 'building consent']
        elif any(word in question_lower for word in ['calculation', 'calc']):
            search_terms = ['calculation', 'analysis', 'structural', 'design', 'load']
        elif any(word in question_lower for word in ['report', 'assessment']):
            search_terms = ['report', 'assessment', 'investigation', 'structural', 'engineering']
        elif any(word in question_lower for word in ['drawing', 'detail']):
            search_terms = ['drawing', 'detail', 'sketch', 'plan', 'structural']
        elif any(word in question_lower for word in ['letter', 'correspondence']):
            search_terms = ['letter', 'correspondence', 'memo', 'engineering']
        else:
            # Generic template search
            template_words = template_type.lower().split()
            search_terms = template_words + ['template', 'format', 'standard']
        
        # Perform broader search
        for term in search_terms[:3]:  # Limit to top 3 search terms
            try:
                response = self.search_client.search(
                    search_text=term,
                    search_fields=["filename", "content"],
                    top=5,
                    query_type="semantic"
                )
                for result in response:
                    if result.get('@search.score', 0) > 0.6:  # Lower threshold for more results
                        broader_results.append({
                            'title': result.get('filename', 'Untitled'),
                            'content': result.get('content', '')[:300] + '...',
                            'metadata': result.get('metadata', {}),
                            'score': result.get('@search.score', 0)
                        })
                if len(broader_results) >= 5:  # Stop if we found enough relevant docs
                    break
            except Exception:
                continue
        
        # Generate helpful guidance based on template type
        template_guidance = self._generate_template_guidance(template_type, question_lower)
        
        if broader_results:
            template_guidance += "\n\n🔍 **Related Documents Found:**\n"
            for doc in broader_results[:5]:
                template_guidance += f"• **{doc['title']}** (Relevance: {doc['score']:.1f})\n"
        
        return {
            'answer': template_guidance,
            'sources': broader_results,
            'confidence': 'high' if broader_results else 'medium',
            'documents_searched': len(broader_results),
            'search_type': 'comprehensive_guidance'
        }
    
    def _generate_template_guidance(self, template_type: str, question_lower: str) -> str:
        """Generate specific guidance for different template types."""
        
        if any(word in question_lower for word in ['ps1', 'producer statement 1']):
            return """📋 **PS1 (Producer Statement - Design) Template**

While I couldn't find a specific PS1 template, here's comprehensive guidance:

✅ **Template Sources:**
• **MBIE Website**: Download official Producer Statement forms from building.govt.nz
• **Engineering NZ**: Access standardized templates through engineeringnz.org  
• **Your Project Manager**: They may have DTCE-specific PS1 templates
• **Previous Projects**: Check similar completed projects for examples

📝 **What to Include:**
• Project details and consent numbers
• Structural design compliance statement
• Reference to relevant codes (NZS 3604, NZS 1170, etc.)
• CPEng details and registration number
• Clear scope of work covered

⚠️ **Requirements:**
• Must be signed by a CPEng (Chartered Professional Engineer)
• Specific to your project and council requirements"""

        elif any(word in question_lower for word in ['ps2', 'ps3', 'ps4', 'producer statement']):
            ps_type = 'PS2' if 'ps2' in question_lower else 'PS3' if 'ps3' in question_lower else 'PS4'
            
            # Check if user specifically asks for links or can't find in SuiteFiles
            wants_external_link = any(phrase in question_lower for phrase in [
                'link', 'url', 'download', 'legitimate', 'official', 'cannot find', 'can\'t find', 
                'not in suitefiles', 'provide me with', 'give me', 'direct', 'external'
            ])
            
            if wants_external_link and ps_type == 'PS3':
                return """📋 **PS3 Producer Statement Template**

🔗 **Direct Download Links:**
• **MBIE Official PS3 Form**: https://www.building.govt.nz/assets/Uploads/building-code-compliance/producer-statements/ps3-construction-review-producer-statement.pdf
• **Engineering NZ PS3 Resources**: https://www.engineeringnz.org/our-work/advocacy/building-system-reform/producer-statements/
• **General Producer Statements Page**: https://www.building.govt.nz/building-code-compliance/producer-statements/

📝 **PS3 Purpose:**
• Construction review and verification  
• Confirms work complies with consent documentation
• Used for specific construction elements or stages

⚠️ **Requirements:**
• Must be signed by appropriately qualified professional
• Specific to your project and council jurisdiction
• Include detailed scope of construction review
• **Accepted by all New Zealand councils when properly completed**"""
            
            elif wants_external_link and ps_type == 'PS4':
                return """📋 **PS4 Producer Statement Template**

🔗 **Direct Download Links:**
• **MBIE Official PS4 Form**: https://www.building.govt.nz/assets/Uploads/building-code-compliance/producer-statements/ps4-construction-producer-statement.pdf
• **Engineering NZ PS4 Resources**: https://www.engineeringnz.org/our-work/advocacy/building-system-reform/producer-statements/
• **General Producer Statements Page**: https://www.building.govt.nz/building-code-compliance/producer-statements/

📝 **PS4 Purpose:**
• Construction completion certification
• Confirms construction compliance with consent and design

⚠️ **Requirements:**
• Must be signed by appropriately qualified professional
• **Accepted by all New Zealand councils when properly completed**"""
            
            elif wants_external_link and ps_type == 'PS2':
                return """📋 **PS2 Producer Statement Template**

🔗 **Direct Download Links:**
• **MBIE Official PS2 Form**: https://www.building.govt.nz/assets/Uploads/building-code-compliance/producer-statements/ps2-design-review-producer-statement.pdf
• **Engineering NZ PS2 Resources**: https://www.engineeringnz.org/our-work/advocacy/building-system-reform/producer-statements/
• **General Producer Statements Page**: https://www.building.govt.nz/building-code-compliance/producer-statements/

📝 **PS2 Purpose:**
• Design review and verification
• Independent review of structural design

⚠️ **Requirements:**
• Must be signed by appropriately qualified professional
• Independent of original design engineer"""
            
            else:
                return f"""📋 **{ps_type} Producer Statement Template**

**Template Sources:**
• Contact your project manager for DTCE-specific {ps_type} templates
• Visit MBIE Building website for official Producer Statement forms
• Check Engineering NZ resources for professional guidance

**Requirements:**
• Must be signed by appropriately qualified professional
• Specific to your project and council jurisdiction
• Include all relevant scope and compliance statements"""

        elif any(word in question_lower for word in ['calculation', 'calc', 'timber', 'beam', 'design', 'spreadsheet']):
            # Check if user specifically asks for links or can't find in SuiteFiles
            wants_external_link = any(phrase in question_lower for phrase in [
                'link', 'url', 'download', 'legitimate', 'official', 'cannot find', 'can\'t find', 
                'not in suitefiles', 'provide me with', 'give me', 'direct', 'external'
            ])
            
            if 'timber' in question_lower and wants_external_link:
                return """📋 **Timber Beam Design Spreadsheet**


🔗 **Direct Download Links:**

• **NZ Wood Timber Design Tools**: https://www.nzwood.co.nz/building-with-wood/design-tools/

• **STIC Timber Design Spreadsheets**: https://www.stic.org.nz/structural-design-tools

• **WoodSolutions Beam Calculator**: https://www.woodsolutions.com.au/design-tools

• **Engineering NZ Timber Resources**: https://www.engineeringnz.org/resources/


📝 **Alternative Options:**

• **Commercial Software**: Microlam, TimberCalc Pro

• **Free Tools**: Various university and industry calculators

• **Previous DTCE Projects**: Check similar timber design projects


⚠️ **Important Notes:**

• Verify calculations comply with NZS 3603 (Timber Structures)

• Check load combinations per NZS 1170.1

• Consider deflection limits and serviceability requirements"""
            
            elif 'timber' in question_lower:
                return """📋 **Timber Beam Design Spreadsheet**

**What You Need:**
• Check previous similar projects for DTCE calculation formats
• Ask your senior engineer for preferred timber design tools
• Review NZS 3603 for timber design requirements

**Template Should Include:**
• Load analysis and combinations per NZS 1170.1
• Timber grade and material properties
• Deflection and strength checks per NZS 3603
• Clear design methodology and assumptions"""
            
            else:
                return """📋 **Structural Calculation Template**

**What You Need:**
• Check previous similar projects for calculation formats
• Ask your senior engineer for DTCE calculation standards
• Review relevant design codes for required content

**Template Should Include:**
• Design assumptions and criteria
• Load calculations and combinations
• Material properties and design codes used
• Clear analysis methodology and results"""

        elif any(word in question_lower for word in ['report', 'assessment']):
            return """📋 **Engineering Report Template**

**Template Sources:**
• Check SuiteFiles under Templates or similar projects
• Ask your project manager for DTCE report standards
• Review previous reports for format guidance

**Report Should Include:**
• Executive summary and recommendations
• Site conditions and constraints documentation
• Clear conclusions and next steps
• Professional formatting with DTCE standards"""

        elif any(word in question_lower for word in ['drawing', 'detail']):
            return """📋 **Drawing Template**

**Template Sources:**
• CAD standards folder in DTCE systems
• Ask your senior engineer for drawing templates
• Check AutoCAD/Revit template libraries

**Requirements:**
• DTCE title block and drawing standards
• Proper revision tracking and approval boxes
• Scale and dimension standards compliance"""

        elif any(word in question_lower for word in ['letter', 'correspondence']):
            return """📋 **Engineering Letter Template**

**Template Sources:**
• DTCE letterhead templates should be available
• Check with administration or your manager
• Previous correspondence for format examples

**Requirements:**
• Include DTCE letterhead and engineer details
• Clear subject line and reference numbers
• Professional sign-off with qualifications"""

        else:
            template_name = template_type.replace('_', ' ').title()
            return f"""📋 **{template_name} Template**

**Recommended Actions:**
• **Project Team**: Check with your project manager or senior engineer for DTCE-specific templates
• **SuiteFiles Search**: Try searching with alternative keywords or browse relevant project folders
• **Previous Projects**: Look for similar projects that may have used comparable templates
• **Professional Resources**: Consult relevant professional bodies or industry standards

**General Guidance:**
• Ensure templates follow DTCE company standards
• Include appropriate headers and professional formatting
• Verify you have the most current version before use"""

    def _format_template_answer(self, template_docs: List[Dict], template_type: str, question: str) -> str:
        """Format template search results into a comprehensive answer."""
        if not template_docs:
            return f"No {template_type} templates found in SuiteFiles."
        
        answer_parts = []
        
        # Filter out documents with missing essential info and group by project
        valid_templates = []
        templates_by_project = {}
        
        for doc in template_docs:
            # Use the reusable method for proper Base64 decoding
            doc_info = self._extract_document_info(doc)
            filename = doc_info['filename']
            # Use project_name for display, fallback to project_id for backward compatibility
            project = doc_info['project_name'] or doc_info['project_id'] or 'General Templates'
            blob_url = (doc.get('blob_url') or '').strip()
            
            # Skip documents with missing filename
            if not filename or filename == 'None':
                continue
                
            valid_templates.append(doc)
            
            if project not in templates_by_project:
                templates_by_project[project] = []
            
            templates_by_project[project].append({
                'filename': filename,
                'url': blob_url
            })
        
        if not valid_templates:
            return f"Found potential {template_type} documents but they lack proper metadata. Please search SuiteFiles manually or contact your team."
        
        answer_parts.append(f"📋 **{template_type} Templates Found in SuiteFiles:**\n")
        
        for project, templates in templates_by_project.items():
            if len(templates_by_project) > 1 and project != 'General Templates':
                answer_parts.append(f"\n**Project {project}:**")
            
            for template in templates:
                if template['url']:
                    answer_parts.append(f"• [{template['filename']}]({template['url']})")
                else:
                    answer_parts.append(f"• {template['filename']} (Contact team for access)")
        
        # Add usage instructions
        answer_parts.append(f"\n💡 **How to Access:**")
        answer_parts.append(f"• Click the links above to access templates directly in SuiteFiles")
        answer_parts.append(f"• Download and customize for your specific project")
        answer_parts.append(f"• Ensure you're using the most current version")
        
        # Add specific guidance based on template type
        if 'PS' in template_type:
            answer_parts.append(f"\n⚠️ **Important for Producer Statements:**")
            answer_parts.append(f"• Ensure you're a Chartered Professional Engineer (CPEng)")
            answer_parts.append(f"• Review MBIE guidelines for producer statements")
            answer_parts.append(f"• Check council-specific requirements")
        
        return "\n".join(answer_parts)

    def _format_template_sources(self, template_docs: List[Dict]) -> List[Dict]:
        """Format template documents as sources."""
        sources = []
        
        for doc in template_docs[:5]:  # Limit to top 5 sources
            try:
                # Use the reusable method for proper Base64 decoding
                doc_info = self._extract_document_info(doc)
                filename = doc_info['filename']
                project_name = doc_info['project_name'] or doc_info['project_id']  # Smart: prefer project_name for display
                
                # Skip sources with missing essential info
                if not filename or filename == 'None':
                    continue
                    
                sources.append({
                    'filename': filename,
                    'project_id': project_name or 'Template Library',  # Use the smart project_name variable
                    'relevance_score': doc.get('@search.score', 0.9),
                    'blob_url': doc.get('blob_url', ''),
                    'excerpt': f"Template document: {filename}"
                })
            except Exception as e:
                logger.warning(f"Failed to format template source: {e}, doc keys: {list(doc.keys()) if isinstance(doc, dict) else 'not dict'}")
                continue
        
        return sources

    def _format_best_practices_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format best practices document sources with enhanced context."""
        sources = []
        
        for doc in documents:
            # Use comprehensive document info extraction
            doc_info = self._extract_document_info(doc)
            filename = doc_info['filename']
            project_name = doc_info['project_id'] or 'Practice Library'
            
            # Get the best practices relevance score
            relevance_score = doc.get('best_practices_score', doc.get('@search.score', 0.5))
            
            # Create context-aware excerpt
            content = doc.get('content', '')
            
            # Look for practice-specific excerpts
            practice_indicators = [
                'standard approach', 'methodology', 'template', 'procedure',
                'checklist', 'guideline', 'specification', 'process'
            ]
            
            excerpt = ""
            for indicator in practice_indicators:
                if indicator in content.lower():
                    # Find sentence containing the indicator
                    sentences = content.split('.')
                    for sentence in sentences:
                        if indicator in sentence.lower():
                            excerpt = sentence.strip()[:200] + "..."
                            break
                    if excerpt:
                        break
            
            if not excerpt:
                excerpt = content[:200] + "..." if content else "Best practices document"
            
            sources.append({
                'filename': filename,
                'project_id': project_name,
                'relevance_score': relevance_score,
                'blob_url': doc.get('blob_url', ''),
                'excerpt': excerpt,
                'folder_path': doc_info['folder_path']
            })
        
        return sources

    def _format_materials_methods_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format materials/methods document sources with enhanced context."""
        sources = []
        
        for doc in documents:
            # Use comprehensive document info extraction
            doc_info = self._extract_document_info(doc)
            filename = doc_info['filename']
            project_name = doc_info['project_id'] or 'Technical Library'
            
            # Get the materials/methods relevance score
            relevance_score = doc.get('materials_methods_score', doc.get('@search.score', 0.5))
            
            # Create context-aware excerpt
            content = doc.get('content', '')
            
            # Look for materials/methods-specific excerpts
            materials_indicators = [
                'concrete', 'steel', 'timber', 'material selection', 'chosen',
                'comparison', 'versus', 'alternative', 'decision', 'rationale'
            ]
            
            excerpt = ""
            for indicator in materials_indicators:
                if indicator in content.lower():
                    # Find sentence containing the indicator
                    sentences = content.split('.')
                    for sentence in sentences:
                        if indicator in sentence.lower():
                            excerpt = sentence.strip()[:200] + "..."
                            break
                    if excerpt:
                        break
            
            if not excerpt:
                excerpt = content[:200] + "..." if content else "Materials/methods document"
            
            sources.append({
                'filename': filename,
                'project_id': project_name,
                'relevance_score': relevance_score,
                'blob_url': doc.get('blob_url', ''),
                'excerpt': excerpt,
                'folder_path': doc_info['folder_path']
            })
        
        return sources

    def _format_internal_knowledge_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format internal knowledge document sources with enhanced context."""
        sources = []
        
        for doc in documents:
            # Use comprehensive document info extraction
            doc_info = self._extract_document_info(doc)
            filename = doc_info['filename']
            project_name = doc_info['project_id'] or 'Knowledge Base'
            
            # Get the internal knowledge relevance score
            relevance_score = doc.get('internal_knowledge_score', doc.get('@search.score', 0.5))
            
            # Create context-aware excerpt
            content = doc.get('content', '')
            
            # Look for knowledge-specific excerpts
            knowledge_indicators = [
                'engineer', 'expertise', 'experience', 'specialist', 'skilled',
                'team', 'responsible', 'designed by', 'worked on', 'involved'
            ]
            
            excerpt = ""
            for indicator in knowledge_indicators:
                if indicator in content.lower():
                    # Find sentence containing the indicator
                    sentences = content.split('.')
                    for sentence in sentences:
                        if indicator in sentence.lower():
                            excerpt = sentence.strip()[:200] + "..."
                            break
                    if excerpt:
                        break
            
            if not excerpt:
                excerpt = content[:200] + "..." if content else "Internal knowledge document"
            
            sources.append({
                'filename': filename,
                'project_id': project_name,
                'relevance_score': relevance_score,
                'blob_url': doc.get('blob_url', ''),
                'excerpt': excerpt,
                'folder_path': doc_info['folder_path']
            })
        
        return sources

    async def _extract_project_characteristics(self, scoping_text: str, rfp_content: Optional[str] = None) -> Dict[str, Any]:
        """Extract key characteristics from the project scoping request."""
        try:
            # Combine scoping text and RFP content
            full_text = scoping_text
            if rfp_content:
                full_text += "\n\n" + rfp_content
            
            # Use GPT to extract structured project characteristics
            prompt = f"""
            Analyze the following project scoping request and extract key characteristics:

            {full_text}

            Please extract and categorize the following information:
            1. Project Type (e.g., residential, commercial, industrial, infrastructure)
            2. Structure Type (e.g., building, bridge, marquee, temporary structure)
            3. Key Dimensions/Scale
            4. Materials mentioned
            5. Location/Environment
            6. Load Requirements (wind, seismic, live loads)
            7. Specific Challenges mentioned
            8. Certification Requirements (PS1, building consent, etc.)
            9. Timeline considerations
            10. Budget considerations

            Return the analysis in a structured format with clear categories.
            """
            
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a structural engineering expert who specializes in project analysis and scoping."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parse the response to extract characteristics
            characteristics_text = response.choices[0].message.content
            
            # Use another GPT call to structure the characteristics as JSON-like data
            structure_prompt = f"""
            Convert the following project characteristics analysis into a structured format:
            
            {characteristics_text}
            
            Return as categories with specific values. Focus on extracting:
            - structure_type
            - dimensions
            - materials
            - location
            - loads
            - challenges
            - certifications
            - timeline
            - budget_indicators
            """
            
            structure_response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Extract specific project characteristics into clear categories."},
                    {"role": "user", "content": structure_prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            return {
                'raw_analysis': characteristics_text,
                'structured_analysis': structure_response.choices[0].message.content,
                'extracted_keywords': self._extract_search_keywords_from_text(full_text)
            }
            
        except Exception as e:
            logger.error("Failed to extract project characteristics", error=str(e))
            return {'error': str(e)}

    async def _find_similar_projects(self, project_characteristics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar past projects based on project characteristics."""
        try:
            # Extract search terms from characteristics
            search_keywords = project_characteristics.get('extracted_keywords', [])
            
            # Add specific engineering terms for better matching
            engineering_terms = [
                'PS1', 'structural', 'certification', 'design', 'engineering',
                'load', 'wind', 'seismic', 'foundation', 'steel', 'concrete'
            ]
            
            # Search for similar projects using multiple search strategies
            all_similar_docs = []
            
            # Strategy 1: Search by structure type and materials
            structure_search = await self._search_by_characteristics(
                project_characteristics.get('structured_analysis', ''), 
                search_type='structure'
            )
            all_similar_docs.extend(structure_search)
            
            # Strategy 2: Search by keywords
            for keyword in search_keywords[:5]:  # Top 5 keywords
                keyword_docs = self._search_relevant_documents(keyword)
                all_similar_docs.extend(keyword_docs[:3])  # Top 3 per keyword
            
            # Strategy 3: Search by engineering terms combined with characteristics
            for term in engineering_terms[:3]:
                if search_keywords:
                    combined_query = f"{term} {search_keywords[0]}"
                    eng_docs = self._search_relevant_documents(combined_query)
                    all_similar_docs.extend(eng_docs[:2])
            
            # Remove duplicates and rank by relevance
            unique_docs = self._remove_duplicate_documents(all_similar_docs)
            
            # Filter and rank by similarity to project characteristics
            similar_projects = await self._rank_project_similarity(unique_docs, project_characteristics)
            
            return similar_projects[:10]  # Top 10 most similar
            
        except Exception as e:
            logger.error("Failed to find similar projects", error=str(e))
            return []

    async def _analyze_past_issues(self, similar_projects: List[Dict], project_characteristics: Dict) -> Dict[str, Any]:
        """Analyze past issues and solutions from similar projects."""
        try:
            if not similar_projects:
                return {'issues': [], 'solutions': [], 'warnings': []}
            
            # Prepare context from similar projects
            projects_context = ""
            for i, project in enumerate(similar_projects[:5]):  # Top 5 projects
                projects_context += f"\nProject {i+1}:\n"
                projects_context += f"File: {project.get('blob_name', 'Unknown')}\n"
                projects_context += f"Content: {project.get('content_preview', '')[:500]}...\n"
            
            # Analyze for common issues and solutions
            analysis_prompt = f"""
            Based on these similar past projects and the current project characteristics, identify:
            
            SIMILAR PAST PROJECTS:
            {projects_context}
            
            CURRENT PROJECT CHARACTERISTICS:
            {project_characteristics.get('structured_analysis', '')}
            
            Please analyze and provide:
            1. COMMON ISSUES: What problems frequently occurred in similar projects?
            2. PROVEN SOLUTIONS: What solutions worked well for these issues?
            3. RISK WARNINGS: What specific risks should we watch for in this new project?
            4. LESSONS LEARNED: What key learnings can guide this project?
            
            Focus on structural engineering challenges, regulatory compliance, timeline issues, and technical difficulties.
            """
            
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior structural engineer analyzing past project experiences to prevent future issues."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.2,
                max_tokens=1200
            )
            
            issues_analysis = response.choices[0].message.content
            
            return {
                'analysis': issues_analysis,
                'projects_analyzed': len(similar_projects),
                'risk_level': self._assess_risk_level(issues_analysis)
            }
            
        except Exception as e:
            logger.error("Failed to analyze past issues", error=str(e))
            return {'error': str(e)}

    async def _generate_design_philosophy(self, project_characteristics: Dict, similar_projects: List[Dict], issues_analysis: Dict) -> Dict[str, Any]:
        """Generate design philosophy and recommendations for the project."""
        try:
            # Create comprehensive prompt for design philosophy
            philosophy_prompt = f"""
            As a senior structural engineer, develop a design philosophy and approach for this project:
            
            PROJECT CHARACTERISTICS:
            {project_characteristics.get('structured_analysis', '')}
            
            LESSONS FROM SIMILAR PROJECTS:
            {issues_analysis.get('analysis', '')}
            
            Please provide:
            1. DESIGN PHILOSOPHY: Core principles that should guide this project
            2. TECHNICAL APPROACH: Recommended methods and standards
            3. RISK MITIGATION: How to avoid common pitfalls
            4. COMPLIANCE STRATEGY: Approach for certifications and approvals
            5. QUALITY ASSURANCE: Checks and validations needed
            6. TIMELINE CONSIDERATIONS: Key milestones and dependencies
            
            Make this practical and actionable for the engineering team.
            """
            
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a principal structural engineer providing design guidance based on extensive experience."},
                    {"role": "user", "content": philosophy_prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            design_philosophy = response.choices[0].message.content
            
            return {
                'philosophy': design_philosophy,
                'confidence': 'high' if len(similar_projects) > 3 else 'medium',
                'based_on_projects': len(similar_projects)
            }
            
        except Exception as e:
            logger.error("Failed to generate design philosophy", error=str(e))
            return {'error': str(e)}

    async def _generate_comprehensive_project_analysis(self, scoping_text: str, characteristics: Dict, 
                                                     similar_projects: List[Dict], issues_analysis: Dict, 
                                                     design_philosophy: Dict) -> str:
        """Generate a comprehensive analysis combining all findings."""
        try:
            # Create the comprehensive analysis
            analysis_prompt = f"""
            Provide a comprehensive project analysis report for this client request:
            
            CLIENT REQUEST:
            {scoping_text}
            
            PROJECT ANALYSIS:
            {characteristics.get('raw_analysis', '')}
            
            SIMILAR PROJECTS FOUND: {len(similar_projects)} projects
            
            ISSUES ANALYSIS:
            {issues_analysis.get('analysis', '')}
            
            DESIGN PHILOSOPHY:
            {design_philosophy.get('philosophy', '')}
            
            Please write a professional response to the client that includes:
            1. Acknowledgment of their request
            2. Our experience with similar projects (reference specific past work)
            3. Key considerations and potential challenges
            4. Our recommended approach
            5. What we need from them to proceed
            6. Timeline and cost considerations (general guidance)
            
            Make this client-friendly but technically sound.
            """
            
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior structural engineer responding professionally to a client inquiry, drawing on extensive project experience."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.4,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Failed to generate comprehensive analysis", error=str(e))
            return f"I encountered an error generating the comprehensive analysis: {str(e)}"

    async def _search_by_characteristics(self, characteristics_text: str, search_type: str = 'structure') -> List[Dict]:
        """Search documents by specific project characteristics."""
        try:
            # Extract key search terms from characteristics
            search_terms = []
            
            if 'marquee' in characteristics_text.lower():
                search_terms.extend(['marquee', 'temporary structure', 'tent'])
            if 'wind' in characteristics_text.lower():
                search_terms.extend(['wind load', 'wind rating', 'wind resistance'])
            if 'foundation' in characteristics_text.lower() or 'concrete' in characteristics_text.lower():
                search_terms.extend(['foundation', 'concrete pad', 'anchoring'])
            if 'PS1' in characteristics_text:
                search_terms.extend(['PS1', 'producer statement', 'certification'])
            
            # Search using combined terms
            all_docs = []
            for term in search_terms[:5]:  # Limit to prevent too many queries
                docs = self._search_relevant_documents(term)
                all_docs.extend(docs[:3])  # Top 3 per term
            
            return self._remove_duplicate_documents(all_docs)
            
        except Exception as e:
            logger.error("Search by characteristics failed", error=str(e))
            return []

    def _extract_search_keywords_from_text(self, text: str) -> List[str]:
        """Extract relevant engineering keywords from text."""
        # Engineering-specific keywords to look for
        engineering_keywords = [
            'marquee', 'structure', 'foundation', 'concrete', 'steel', 'wind', 'load',
            'PS1', 'certification', 'building consent', 'wellington', 'temporary',
            'anchor', 'bolt', 'seismic', 'design', 'engineer', 'compliance'
        ]
        
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in engineering_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        # Also extract dimensions and technical specifications
        import re
        # Look for dimensions like "15x40m", "120kph", etc.
        dimensions = re.findall(r'\d+x\d+m?|\d+\s*(?:kph|mph|m|mm|kn)', text_lower)
        found_keywords.extend(dimensions)
        
        return found_keywords

    def _remove_duplicate_documents(self, docs: List[Dict]) -> List[Dict]:
        """Remove duplicate documents based on blob_name."""
        seen = set()
        unique_docs = []
        
        for doc in docs:
            blob_name = doc.get('blob_name', '') or doc.get('filename', '')
            if blob_name not in seen:
                seen.add(blob_name)
                unique_docs.append(doc)
        
        return unique_docs

    async def _rank_project_similarity(self, docs: List[Dict], characteristics: Dict) -> List[Dict]:
        """Rank documents by similarity to project characteristics."""
        try:
            # Get key characteristics for comparison
            char_text = characteristics.get('structured_analysis', '') + ' ' + characteristics.get('raw_analysis', '')
            char_keywords = characteristics.get('extracted_keywords', [])
            
            # Score each document
            scored_docs = []
            for doc in docs:
                score = 0
                content = doc.get('content_preview', '') + ' ' + doc.get('blob_name', '')
                
                # Keyword matching
                for keyword in char_keywords:
                    if keyword.lower() in content.lower():
                        score += 2
                
                # Specific engineering terms
                if any(term in content.lower() for term in ['ps1', 'structural', 'design']):
                    score += 3
                
                # Project type matching
                if 'marquee' in char_text.lower() and 'marquee' in content.lower():
                    score += 5
                
                scored_docs.append((score, doc))
            
            # Sort by score (highest first)
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            
            return [doc for score, doc in scored_docs if score > 0]
            
        except Exception as e:
            logger.error("Failed to rank project similarity", error=str(e))
            return docs

    def _assess_risk_level(self, issues_analysis: str) -> str:
        """Assess risk level based on issues analysis."""
        risk_indicators = [
            'complex', 'challenging', 'difficult', 'risk', 'problem', 'issue',
            'failure', 'delay', 'cost overrun', 'non-compliance'
        ]
        
        analysis_lower = issues_analysis.lower()
        risk_count = sum(1 for indicator in risk_indicators if indicator in analysis_lower)
        
        if risk_count >= 5:
            return 'high'
        elif risk_count >= 3:
            return 'medium'
        else:
            return 'low'

    async def _handle_conversational_query(self, question: str, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversational queries, greetings, or unclear input."""
        try:
            logger.info("Processing conversational query", question=question)
            
            question_lower = question.lower().strip()
            
            # Handle pure greetings and very simple queries
            if question_lower in ["hey", "hi", "hello"]:
                answer = "Hello! I'm the DTCE AI Assistant. I can help you find information from DTCE's project documents, templates, standards, and provide engineering guidance. What would you like to know?"
            elif question_lower in ["what", "what?"]:
                answer = """I'm here to help with engineering questions! You can ask me about:

• Past DTCE projects and case studies
• Design templates and calculation sheets  
• Building codes and standards (NZS, AS/NZS)
• Technical design guidance
• Project timelines and costs
• Best practices and methodologies

What specific information are you looking for?"""
            elif question_lower in ["really", "really?"]:
                answer = "Yes! I have access to DTCE's extensive project database and can help you find relevant information. Try asking about specific projects, technical topics, or engineering guidance you need."
            elif len(question.strip()) < 3:
                answer = "I need a bit more information to help you. Please ask a specific question about engineering, projects, standards, or anything else I can assist with!"
            else:
                # For anything else classified as conversational, try searching first
                # The user might have asked something meaningful that was misclassified
                logger.info("Conversational query contains meaningful content, attempting search first", question=question)
                
                # Try a simple search to see if we have relevant documents
                try:
                    search_docs = self._search_relevant_documents(question)
                    
                    if search_docs and len(search_docs) > 0:
                        # Found relevant documents! Process as normal search query
                        logger.info("Found documents for conversational query, processing as search", 
                                   question=question, docs_found=len(search_docs))
                        
                        # Generate answer based on the documents found
                        answer = await self._generate_answer_from_documents(question, search_docs)
                        sources = self._format_sources(search_docs)
                        
                        return {
                            'answer': answer,
                            'sources': sources,
                            'confidence': 'medium',
                            'documents_searched': len(search_docs),
                            'search_type': 'conversational_fallback_search',
                            'classification': classification
                        }
                        
                except Exception as search_error:
                    logger.warning("Search failed for conversational query", error=str(search_error))
                
                # If no documents found or search failed, provide helpful guidance
                answer = f"""I searched for documents related to '{question}' but didn't find specific matches. 

I'm designed to help with engineering questions and DTCE project information. Try asking something like:
• 'Find projects similar to a 3-story office building'
• 'Show me NZS 3101 concrete design information'
• 'What's our standard approach for steel connections?'
• 'How long does PS1 preparation typically take?'

What can I help you find?"""
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'high',
                'documents_searched': 0,
                'search_type': 'conversational',
                'classification': classification
            }
            
        except Exception as e:
            logger.error("Conversational query failed", error=str(e))
            return {
                'answer': "Hello! I'm the DTCE AI Assistant. How can I help you with engineering questions or project information?",
                'sources': [],
                'confidence': 'medium',
                'documents_searched': 0
            }

    async def _handle_intelligent_general_query(self, question: str, project_filter: Optional[str] = None, classification: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Handle general queries with intelligence - understand intent even when not specifically classified.
        This prevents falling back to dumb keyword-based template dumps.
        """
        try:
            logger.info("Processing intelligent general query", question=question)
            
            # Extract user intent from the question using AI analysis
            intent_analysis = await self._analyze_question_intent(question, classification)
            
            # Check source preference from intent analysis
            preferred_source = intent_analysis.get('preferred_source', 'either')
            
            if preferred_source == 'internal_documents':
                # User specifically wants internal documents - search them
                logger.info("User specified internal documents - searching SuiteFiles")
                relevant_docs = await self._search_with_intent(question, intent_analysis, project_filter, force_internal=True)
                
                if not relevant_docs:
                    return {
                        'answer': "I couldn't find any relevant information in our internal documents (SuiteFiles). Could you please rephrase your question or provide more specific details about what you're looking for in our documents?",
                        'sources': [],
                        'confidence': 'low',
                        'documents_searched': 0,
                        'search_type': 'internal_only',
                        'intent_analysis': intent_analysis,
                        'source_breakdown': {'internal_docs': 0, 'ai_knowledge': 0}
                    }
                    
                # Generate answer from internal documents only
                context = self._prepare_intent_aware_context(relevant_docs, intent_analysis)
                answer = await self._generate_intent_aware_answer(question, context, intent_analysis)
                source_analysis = self._analyze_answer_sources(answer, len(relevant_docs))
                
                return {
                    'answer': answer,
                    'sources': self._format_intelligent_sources(relevant_docs, intent_analysis),
                    'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                    'documents_searched': len(relevant_docs),
                    'search_type': 'internal_documents',
                    'intent_analysis': intent_analysis,
                    'source_breakdown': source_analysis
                }
                
            elif preferred_source == 'external_knowledge':
                # User wants general knowledge - provide AI knowledge response
                logger.info("User wants general knowledge - using AI knowledge")
                return await self._generate_no_docs_intelligent_response(question, intent_analysis)
            
            else:
                # Either source preference - try internal documents first, then general knowledge
                logger.info("Checking internal documents first, then general knowledge if needed")
                relevant_docs = await self._search_with_intent(question, intent_analysis, project_filter)
                
                if not relevant_docs:
                    # No internal documents found - use general knowledge
                    logger.info("No internal documents found - using general AI knowledge")
                    return await self._generate_no_docs_intelligent_response(question, intent_analysis)
                
                # Generate answer from found documents
                context = self._prepare_intent_aware_context(relevant_docs, intent_analysis)
                answer = await self._generate_intent_aware_answer(question, context, intent_analysis)
                source_analysis = self._analyze_answer_sources(answer, len(relevant_docs))
                
                return {
                    'answer': answer,
                    'sources': self._format_intelligent_sources(relevant_docs, intent_analysis),
                    'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                    'documents_searched': len(relevant_docs),
                    'search_type': 'intelligent_general',
                    'intent_analysis': intent_analysis,
                    'source_breakdown': source_analysis
                }
            
        except Exception as e:
            logger.error("Intelligent general query failed", error=str(e))
            return {
                'answer': 'I encountered an error while processing your question intelligently. Please try rephrasing your question.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _analyze_question_intent(self, question: str, classification: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze what the user actually wants from their question."""
        
        system_prompt = """Please analyze the user's question to understand what type of information they're looking for.

        Consider these common request types:
        - seeking_guidance: User wants advice or recommendations
        - seeking_examples: User wants to see past examples or case studies
        - seeking_specifications: User wants technical details or standards
        - seeking_processes: User wants to understand workflows or procedures
        - seeking_data: User wants specific facts, numbers, or timelines
        - seeking_contacts: User wants contact information or vendor details
        - seeking_comparison: User wants to compare different options
        - seeking_troubleshooting: User has a problem and wants solutions

        Also determine the PREFERRED SOURCE:
        - internal_documents: If user mentions "suitefiles", "our documents", "our projects", "company files", "internal", etc.
        - external_knowledge: If user asks for general standards, codes, best practices without specifying internal sources
        - either: If not specified

        Please extract key concepts and determine what type of response would be most helpful.

        Respond with JSON containing: intent_category, key_concepts, response_type_needed, user_goal, preferred_source"""
        
        user_prompt = f"""Question: {question}

        Existing classification: {classification}
        
        Analyze this question and return a JSON response with the user's true intent and information needs."""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            import json
            intent_text = response.choices[0].message.content.strip()
            # Extract JSON from response
            if '{' in intent_text:
                json_start = intent_text.find('{')
                json_end = intent_text.rfind('}') + 1
                intent_analysis = json.loads(intent_text[json_start:json_end])
            else:
                # Fallback if JSON parsing fails
                intent_analysis = {
                    "intent_category": "seeking_guidance",
                    "key_concepts": [question.lower()],
                    "response_type_needed": "comprehensive_answer",
                    "user_goal": "general_information"
                }
                
            return intent_analysis
            
        except Exception as e:
            logger.error("Intent analysis failed", error=str(e))
            return {
                "intent_category": "seeking_guidance", 
                "key_concepts": [question.lower()],
                "response_type_needed": "comprehensive_answer",
                "user_goal": "general_information"
            }

    async def _search_with_intent(self, question: str, intent_analysis: Dict, project_filter: Optional[str] = None, force_internal: bool = False) -> List[Dict]:
        """Search for documents with understanding of user intent."""
        
        intent_category = intent_analysis.get('intent_category', 'seeking_guidance')
        key_concepts = intent_analysis.get('key_concepts', [])
        
        # Check if user specifically requested SuiteFiles/internal documents
        question_lower = question.lower()
        internal_document_indicators = [
            'suitefiles', 'suite files', 'our documents', 'our files', 
            'company documents', 'internal documents', 'project files',
            'our projects', 'dtce documents', 'in our', 'from our'
        ]
        
        wants_internal_docs = any(indicator in question_lower for indicator in internal_document_indicators)
        
        # Use enhanced intent-based search query instead of basic keyword matching
        enhanced_search_query = self._enhance_search_query_with_intent(question)
        
        # Build intent-aware search terms for fallback if enhanced query fails
        search_terms = []
        search_terms.extend(key_concepts)
        
        # Add intent-specific search modifiers only if not specifically asking for internal docs
        if not wants_internal_docs:
            if intent_category == "seeking_examples":
                search_terms.extend(["project", "case", "example", "similar", "past"])
            elif intent_category == "seeking_specifications":
                search_terms.extend(["specification", "requirement", "standard", "code", "detail"])
            elif intent_category == "seeking_processes":
                search_terms.extend(["process", "procedure", "workflow", "step", "method"])
            elif intent_category == "seeking_data":
                search_terms.extend(["cost", "time", "duration", "timeline", "data", "number"])
            elif intent_category == "seeking_contacts":
                search_terms.extend(["contact", "vendor", "supplier", "contractor", "consultant"])
        
        # Use enhanced search query first, with fallback to traditional approach
        search_query = enhanced_search_query if enhanced_search_query != question else " AND ".join(key_concepts[:3])
        
        logger.info("Intent-aware search", 
                   original_question=question,
                   enhanced_query=enhanced_search_query,
                   intent_category=intent_category,
                   search_query=search_query)
        
        try:
            search_results = self.search_client.search(
                search_text=search_query,
                top=20,
                include_total_count=True,
                search_fields=["content", "filename", "project_name"],
                select=["content", "filename", "project_name", "blob_url"],
                filter=f"project_name eq '{project_filter}'" if project_filter else None,
                highlight_fields="content"
            )
            
            documents = []
            for result in search_results:
                documents.append(dict(result))
                
            return documents
            
        except Exception as e:
            logger.error("Intent-aware search failed", error=str(e))
            return []

    async def _prepare_intent_aware_context(self, documents: List[Dict], intent_analysis: Dict) -> str:
        """Prepare document context with awareness of user intent."""
        
        intent_category = intent_analysis.get('intent_category', 'seeking_guidance')
        
        # Filter and prioritize documents based on intent
        relevant_content = []
        
        for doc in documents[:10]:  # Top 10 documents
            content = doc.get('content', '')
            filename = doc.get('filename', 'Unknown')
            project_id = doc.get('project_id', 'Unknown')
            
            # Extract relevant content based on intent
            if intent_category == "seeking_data" and any(term in content.lower() for term in ['cost', 'time', 'duration', 'timeline', 'weeks', 'months', 'days']):
                relevant_content.append(f"From {filename} (Project {project_id}):\n{content[:800]}")
            elif intent_category == "seeking_specifications" and any(term in content.lower() for term in ['nzs', 'standard', 'code', 'specification', 'requirement']):
                relevant_content.append(f"From {filename} (Project {project_id}):\n{content[:800]}")  
            elif intent_category == "seeking_examples" and any(term in content.lower() for term in ['project', 'design', 'construction', 'completed']):
                relevant_content.append(f"From {filename} (Project {project_id}):\n{content[:800]}")
            else:
                # Include all content for other intent types
                relevant_content.append(f"From {filename} (Project {project_id}):\n{content[:800]}")
        
        return "\n\n---\n\n".join(relevant_content[:5])  # Top 5 most relevant

    async def _generate_intent_aware_answer(self, question: str, context: str, intent_analysis: Dict) -> str:
        """Generate answer with full understanding of user intent."""
        
        intent_category = intent_analysis.get('intent_category', 'seeking_guidance')
        user_goal = intent_analysis.get('user_goal', 'general_information')
        
        system_prompt = f"""You are an intelligent engineering AI assistant that provides exactly what users need based on their intent.

        USER INTENT: {intent_category}
        USER GOAL: {user_goal}
        
        RESPONSE GUIDELINES FOR EACH INTENT:
        
        seeking_guidance: Provide actionable advice, recommendations, and step-by-step guidance
        seeking_examples: Show specific examples, case studies, and past project references
        seeking_specifications: Provide technical details, codes, standards, and precise requirements
        seeking_processes: Explain workflows, procedures, and step-by-step methods
        seeking_data: Extract and present specific numbers, timelines, costs, and quantitative data
        seeking_contacts: Provide contact information, vendor details, and people references
        seeking_comparison: Compare options, show pros/cons, and help with decision-making
        seeking_troubleshooting: Diagnose problems and provide specific solutions
        
        RESPONSE PRINCIPLES:
        1. Avoid generic template lists or document dumps
        2. Address the user's specific intent and goal directly
        3. Extract the most relevant information from the provided context
        4. When context is incomplete, supplement with professional guidance
        5. Be specific, actionable, and directly helpful
        6. Focus on what the user actually needs, not just what documents contain
        
        RESPONSE STRUCTURE:
        - Start with direct answer to their question
        - Provide specific details from context when available
        - Add professional recommendations when appropriate
        - End with actionable next steps if relevant"""
        
        user_prompt = f"""Question: {question}

        Document Context:
        {context}
        
        Please provide a comprehensive answer that addresses the user's specific intent: {intent_category}.
        
        IMPORTANT: Determine the appropriate source for your response:
        
        IF the user asked about "suitefiles", "our documents", "our projects", or similar internal references:
        - Search the Document Context above for relevant information
        - Start with "Based on our project documents..." or "From our SuiteFiles archive..."
        - If no relevant internal documents found, clearly state this and suggest where to look
        
        IF the user asked about general standards, codes, or best practices without specifying internal sources:
        - Provide general engineering knowledge 
        - Start with "From engineering best practices..." or "Based on industry standards..."
        
        IF combining both sources, clearly distinguish which information comes from which source.
        
        The user specifically asked: "{question}"
        Focus on providing exactly what they requested from the appropriate source."""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=800
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Intent-aware answer generation failed", error=str(e))
            return f"I understand you're {intent_category.replace('_', ' ')}, but I encountered an error generating a comprehensive response. Please try rephrasing your question."

    async def _generate_no_docs_intelligent_response(self, question: str, intent_analysis: Dict) -> Dict[str, Any]:
        """Generate intelligent response even when no documents are found."""
        
        intent_category = intent_analysis.get('intent_category', 'seeking_guidance')
        question_lower = question.lower()
        
        # Check for specific document type requests that found no results
        specific_doc_requests = {
            'bridge': 'bridge drawings, calculations, or project documents',
            'building': 'building drawings, plans, or structural documents', 
            'road': 'road design drawings, alignment plans, or pavement documents',
            'retaining wall': 'retaining wall drawings, calculations, or structural details',
            'foundation': 'foundation drawings, pile designs, or geotechnical documents',
            'water': 'water system drawings, hydraulic calculations, or drainage plans',
            'culvert': 'culvert drawings, hydraulic designs, or structural details'
        }
        
        # Check if this is a specific document type request with no results
        doc_type_found = None
        for doc_type, description in specific_doc_requests.items():
            if doc_type in question_lower:
                doc_type_found = (doc_type, description)
                break
        
        if doc_type_found:
            doc_type, description = doc_type_found
            specific_response = f"""I couldn't find any {description} in our current document database.

🔍 **What this means:**
- We may not have {doc_type} projects currently indexed in our system
- The documents might be stored in different folders or with different naming conventions
- Our document indexing may still be in progress

💡 **Suggestions:**
1. **Check project-specific folders** - Try searching for a specific project number if you know it
2. **Use broader terms** - Try searching for "structural drawings" or "engineering plans" instead
3. **Contact the team** - Our engineering team can help locate specific {doc_type} documents
4. **General guidance** - I can provide general engineering guidance about {doc_type} design and best practices

Would you like me to provide general engineering guidance about {doc_type} projects, or would you prefer to search for a specific project?"""
            
            return {
                'answer': specific_response,
                'sources': [],
                'confidence': 'medium',
                'documents_searched': 0,
                'search_type': 'specific_doc_type_not_found',
                'source_breakdown': {
                    'primary_source': 'helpful_guidance',
                    'has_internal_documents': False,
                    'document_indicators_found': 0,
                    'ai_knowledge_indicators_found': 0,
                    'source_clarity': 'clear',
                    'specific_doc_type': doc_type
                }
            }
        
        # Provide professional guidance based on intent for general queries
        guidance_prompts = {
            "seeking_guidance": "provide professional engineering guidance and best practices",
            "seeking_examples": "suggest where to find examples and recommend typical approaches",  
            "seeking_specifications": "provide general specification guidance and suggest standard references",
            "seeking_processes": "outline typical processes and recommend standard procedures",
            "seeking_data": "provide typical ranges and suggest where to find specific data",
            "seeking_contacts": "suggest how to find appropriate contacts and professional networks",
            "seeking_comparison": "provide comparison framework and decision criteria",
            "seeking_troubleshooting": "suggest troubleshooting approaches and common solutions"
        }
        
        guidance_instruction = guidance_prompts.get(intent_category, "provide helpful professional guidance")
        
        system_prompt = f"""You are a professional engineering consultant. The user asked a question but no specific documents were found in our database.

        Please {guidance_instruction} for their question.
        
        IMPORTANT: Since no internal documents were found, clearly indicate this is general engineering knowledge by starting your response with "Based on general engineering practices..." or "From industry standards and best practices..."
        
        Be helpful and professional, providing actionable advice based on general engineering knowledge."""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Question: {question}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return {
                'answer': response.choices[0].message.content,
                'sources': [],
                'confidence': 'medium',
                'documents_searched': 0,
                'search_type': 'intelligent_guidance',
                'source_breakdown': {
                    'primary_source': 'ai_knowledge',
                    'has_internal_documents': False,
                    'document_indicators_found': 0,
                    'ai_knowledge_indicators_found': 1,
                    'source_clarity': 'clear'
                }
            }
            
        except Exception as e:
            logger.error("No docs intelligent response failed", error=str(e))
            return {
                'answer': "I couldn't find specific documents for your question, but I'd be happy to help if you can provide more details or rephrase your question.",
                'sources': [],
                'confidence': 'low', 
                'documents_searched': 0
            }

    def _format_intelligent_sources(self, documents: List[Dict], intent_analysis: Dict) -> List[Dict]:
        """Format sources with understanding of what user actually needs."""
        
        sources = []
        for doc in documents[:3]:  # Top 3 sources
            doc_info = self._extract_document_info(doc)
            
            # Create more helpful source descriptions based on intent
            intent_category = intent_analysis.get('intent_category', 'seeking_guidance')
            
            excerpt = doc.get('@search.highlights', {}).get('content', [''])[0][:200] + '...'
            
            if intent_category == "seeking_examples":
                source_description = f"Project example from {doc_info['project_id']}"
            elif intent_category == "seeking_specifications":  
                source_description = f"Technical specification from {doc_info['filename']}"
            elif intent_category == "seeking_data":
                source_description = f"Project data from {doc_info['project_id']}"
            else:
                source_description = f"Reference from {doc_info['filename']}"
            
            sources.append({
                'filename': doc_info['filename'],
                'project_id': doc_info['project_id'] or 'Unknown',
                'relevance_score': doc.get('@search.score', 0),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': excerpt,
                'source_type': source_description
            })
            
        return sources

    def _search_documents_with_enhanced_query(self, enhanced_query: str) -> List[Dict]:
        """Search documents using the enhanced intent-based query."""
        try:
            logger.info("Enhanced intent search", enhanced_query=enhanced_query)
            
            # Try semantic search first
            try:
                results = self.search_client.search(
                    search_text=enhanced_query,
                    top=50,
                    highlight_fields="filename,project_name,content",
                    select=["id", "filename", "content", "blob_url", "project_name",
                           "folder", "last_modified", "created_date", "size"],
                    query_type="semantic",
                    semantic_configuration_name="default"
                )
                search_type = "semantic"
            except Exception as semantic_error:
                logger.warning("Enhanced semantic search failed, using simple search", error=str(semantic_error))
                results = self.search_client.search(
                    search_text=enhanced_query,
                    top=50,
                    highlight_fields="filename,project_name,content",
                    select=["id", "filename", "content", "blob_url", "project_name",
                           "folder", "last_modified", "created_date", "size"],
                    query_type="simple"
                )
                search_type = "simple"
            
            documents = []
            for result in results:
                documents.append(dict(result))
                
            logger.info("Enhanced search completed", search_type=search_type, found=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Enhanced search failed", error=str(e), enhanced_query=enhanced_query)
            return []

    def _enhance_search_query_with_intent(self, question: str) -> str:
        """Enhance search query based on detected intent for specific document types."""
        question_lower = question.lower()
        
        # Bridge-specific intent detection
        if any(term in question_lower for term in ['bridge', 'bridges']):
            if any(term in question_lower for term in ['drawing', 'drawings', 'plan', 'plans', 'design']):
                # User wants bridge drawings/plans specifically
                return "bridge AND (drawing OR plan OR design OR structural OR span OR deck OR abutment OR pier)"
            elif any(term in question_lower for term in ['calculation', 'calculations', 'analysis']):
                # User wants bridge calculations
                return "bridge AND (calculation OR analysis OR load OR stress OR moment OR design)"
            else:
                # General bridge query
                return "bridge OR bridges"
        
        # Building-specific intent detection
        elif any(term in question_lower for term in ['building', 'buildings']):
            if any(term in question_lower for term in ['drawing', 'drawings', 'plan', 'plans']):
                return "building AND (drawing OR plan OR architectural OR structural OR floor)"
            else:
                return "building OR buildings"
        
        # Road/highway intent detection
        elif any(term in question_lower for term in ['road', 'highway', 'pavement']):
            if any(term in question_lower for term in ['drawing', 'drawings', 'plan', 'plans']):
                return "road OR highway OR pavement AND (drawing OR plan OR alignment OR profile)"
            else:
                return "road OR highway OR pavement"
        
        # Water/drainage intent detection
        elif any(term in question_lower for term in ['water', 'drainage', 'culvert', 'pipe']):
            if any(term in question_lower for term in ['drawing', 'drawings', 'plan', 'plans']):
                return "water OR drainage OR culvert OR pipe AND (drawing OR plan OR hydraulic OR flow)"
            else:
                return "water OR drainage OR culvert OR pipe"
        
        # Retaining wall intent detection
        elif any(term in question_lower for term in ['retaining wall', 'retaining', 'wall']):
            if any(term in question_lower for term in ['drawing', 'drawings', 'plan', 'plans']):
                return "retaining AND wall AND (drawing OR plan OR structural OR reinforcement)"
            else:
                return "retaining AND wall"
        
        # Foundation intent detection
        elif any(term in question_lower for term in ['foundation', 'pile', 'footing']):
            if any(term in question_lower for term in ['drawing', 'drawings', 'plan', 'plans']):
                return "foundation OR pile OR footing AND (drawing OR plan OR structural OR detail)"
            else:
                return "foundation OR pile OR footing"
        
        # General drawing/plan intent
        elif any(term in question_lower for term in ['drawing', 'drawings', 'plan', 'plans', 'dwg', 'pdf']):
            return f"{question} AND (drawing OR plan OR dwg OR pdf)"
        
        # Calculation intent
        elif any(term in question_lower for term in ['calculation', 'calculations', 'analysis']):
            return f"{question} AND (calculation OR analysis OR compute OR design)"
        
        # Report intent
        elif any(term in question_lower for term in ['report', 'specification', 'spec']):
            return f"{question} AND (report OR specification OR document)"
        
        # If no specific intent detected, return original question
        return question

    def _analyze_answer_sources(self, answer: str, document_count: int) -> Dict[str, Any]:
        """Analyze what sources the answer is drawing from."""
        
        answer_lower = answer.lower()
        
        # Check for indicators of document-based content
        document_indicators = [
            'based on our project documents', 'from our suitefiles', 'according to our records',
            'our project files show', 'documented in our', 'from the documents',
            'project data shows', 'our files indicate'
        ]
        
        # Check for indicators of AI knowledge
        ai_knowledge_indicators = [
            'from engineering best practices', 'based on industry standards', 
            'general engineering guidance', 'typical approach', 'commonly',
            'industry practice', 'standard procedure', 'best practice'
        ]
        
        doc_indicators_found = sum(1 for indicator in document_indicators if indicator in answer_lower)
        ai_indicators_found = sum(1 for indicator in ai_knowledge_indicators if indicator in answer_lower)
        
        # Determine primary source type
        if doc_indicators_found > 0 and document_count > 0:
            if ai_indicators_found > 0:
                primary_source = "hybrid"  # Both internal docs and AI knowledge
            else:
                primary_source = "internal_documents"  # Primarily from SuiteFiles
        elif ai_indicators_found > 0 or document_count == 0:
            primary_source = "ai_knowledge"  # Primarily AI-generated knowledge
        else:
            primary_source = "mixed"  # Unclear or mixed sources
            
        return {
            'primary_source': primary_source,
            'has_internal_documents': document_count > 0,
            'document_indicators_found': doc_indicators_found,
            'ai_knowledge_indicators_found': ai_indicators_found,
            'source_clarity': 'clear' if (doc_indicators_found > 0 or ai_indicators_found > 0) else 'unclear'
        }
    
    async def _handle_intelligent_fallback(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Intelligent fallback when no RAG pattern matches.
        Uses GPT to understand intent and search documents intelligently.
        """
        try:
            logger.info("Using intelligent fallback for question", question=question)
            
            # Step 1: Use GPT to classify engineering intent
            intent_classification = await self._classify_engineering_intent(question)
            
            # Step 2: Extract intelligent search terms based on intent
            search_terms = await self._extract_intelligent_search_terms(question, intent_classification)
            
            # Step 3: Search documents with intelligent terms
            documents = await self._intelligent_document_search(search_terms, project_filter)
            
            # Step 4: Generate natural answer using GPT
            if documents:
                answer = await self._generate_intelligent_natural_answer(question, documents, intent_classification)
                
                return {
                    'answer': answer,
                    'sources': self._format_sources_intelligent(documents),
                    'confidence': self._calculate_intelligent_confidence(documents, intent_classification),
                    'documents_searched': len(documents),
                    'search_type': 'intelligent_fallback',
                    'intent': intent_classification.get('intent', 'GENERAL_SEARCH'),
                    'topic': intent_classification.get('topic', question)
                }
            else:
                # No documents found, but still provide helpful response
                return {
                    'answer': await self._generate_no_documents_response(question, intent_classification),
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'intelligent_fallback_no_docs',
                    'intent': intent_classification.get('intent', 'GENERAL_SEARCH')
                }
                
        except Exception as e:
            logger.error("Intelligent fallback failed", error=str(e), question=question)
            
            # Final fallback - basic document search
            return await self._basic_fallback_search(question, project_filter)
    
    async def _classify_engineering_intent(self, question: str) -> Dict[str, Any]:
        """Use GPT to classify engineering-specific intent and extract domain information."""
        
        classification_prompt = f"""You are an expert AI assistant for a structural engineering consultancy (DTCE). 
Analyze this user query and classify the engineering intent.

INTENT CATEGORIES:
1. **NZS_CODE_LOOKUP**: User wants specific clause, section, or information from NZ Standards (NZS 3101, AS/NZS, etc.)
2. **PROJECT_REFERENCE**: User wants past DTCE projects with specific characteristics or scope
3. **SCENARIO_TECHNICAL**: User wants projects matching specific building type + conditions + location scenarios
4. **LESSONS_LEARNED**: User wants issues, failures, problems, or lessons from past projects
5. **REGULATORY_PRECEDENT**: User wants examples of council approvals, consents, or regulatory challenges
6. **COST_TIME_INSIGHTS**: User wants project timeline analysis, cost information, scope expansion examples
7. **BEST_PRACTICES_TEMPLATES**: User wants standard approaches, best practice examples, or calculation templates
8. **MATERIALS_METHODS**: User wants comparisons of materials, construction methods, or technical specifications
9. **INTERNAL_KNOWLEDGE**: User wants to find engineers with specific expertise or work by team members
10. **PRODUCT_LOOKUP**: User wants product specs, suppliers, or material information
11. **TEMPLATE_REQUEST**: User wants calculation templates, design spreadsheets, or forms (PS1, PS3, etc.)
12. **CONTACT_LOOKUP**: User wants contact info for builders, contractors, clients we've worked with
13. **GENERAL_ENGINEERING**: General engineering questions that don't fit specific categories
14. **DESIGN_GUIDANCE**: User wants design advice, calculations, or technical guidance

Examples:
- "How do I design a timber beam for 6m span?" → DESIGN_GUIDANCE
- "What's the deflection limit for residential floors?" → NZS_CODE_LOOKUP
- "Show me buildings we've done in Wellington" → PROJECT_REFERENCE
- "How do we typically detail steel connections?" → BEST_PRACTICES_TEMPLATES
- "What foundation type for soft clay?" → DESIGN_GUIDANCE

User Question: "{question}"

Respond with ONLY a JSON object:
{{
    "intent": "NZS_CODE_LOOKUP|PROJECT_REFERENCE|SCENARIO_TECHNICAL|LESSONS_LEARNED|REGULATORY_PRECEDENT|COST_TIME_INSIGHTS|BEST_PRACTICES_TEMPLATES|MATERIALS_METHODS|INTERNAL_KNOWLEDGE|PRODUCT_LOOKUP|TEMPLATE_REQUEST|CONTACT_LOOKUP|GENERAL_ENGINEERING|DESIGN_GUIDANCE",
    "topic": "main technical topic",
    "building_type": "residential|commercial|industrial|etc",
    "structural_element": "beam|column|foundation|slab|wall|connection|etc",
    "material": "timber|concrete|steel|masonry|etc",
    "conditions": ["seismic", "wind", "coastal", "soft soil", "etc"],
    "location": "Wellington|Auckland|etc",
    "search_keywords": ["keyword1", "keyword2", "keyword3"],
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert engineering query classifier. Respond only with valid JSON."},
                    {"role": "user", "content": classification_prompt}
                ],
                temperature=0.1,
                max_tokens=400
            )
            
            import json
            intent = json.loads(response.choices[0].message.content.strip())
            
            logger.info("Engineering intent classified",
                       intent=intent.get('intent'),
                       topic=intent.get('topic'),
                       confidence=intent.get('confidence'))
            
            return intent
            
        except Exception as e:
            logger.error("Intent classification failed", error=str(e))
            # Fallback intent
            return {
                "intent": "GENERAL_ENGINEERING",
                "topic": question,
                "search_keywords": question.split()[:5],
                "confidence": 0.5,
                "reasoning": "Classification failed, using fallback"
            }
    
    async def _extract_intelligent_search_terms(self, question: str, intent: Dict[str, Any]) -> List[str]:
        """Extract intelligent search terms based on question and intent."""
        search_terms = []
        
        # Add keywords from intent classification
        if intent.get('search_keywords'):
            search_terms.extend(intent['search_keywords'])
        
        # Add topic
        if intent.get('topic'):
            search_terms.append(intent['topic'])
            
        # Add specific terms based on intent type
        intent_type = intent.get('intent', 'GENERAL_ENGINEERING')
        
        if intent_type == 'NZS_CODE_LOOKUP':
            search_terms.extend(['NZS', 'standard', 'code', 'clause'])
        elif intent_type == 'PROJECT_REFERENCE':
            search_terms.extend(['project', 'job', 'DTCE'])
        elif intent_type == 'DESIGN_GUIDANCE':
            search_terms.extend(['design', 'calculation', 'structural'])
        elif intent_type == 'BEST_PRACTICES_TEMPLATES':
            search_terms.extend(['template', 'standard', 'approach', 'practice'])
        elif intent_type == 'MATERIALS_METHODS':
            search_terms.extend(['material', 'construction', 'method'])
        
        # Add building context
        if intent.get('building_type'):
            search_terms.append(intent['building_type'])
        if intent.get('structural_element'):
            search_terms.append(intent['structural_element'])
        if intent.get('material'):
            search_terms.append(intent['material'])
        if intent.get('location'):
            search_terms.append(intent['location'])
        
        # Add conditions
        if intent.get('conditions'):
            search_terms.extend(intent['conditions'])
        
        # Clean and deduplicate
        search_terms = list(set([term.lower().strip() for term in search_terms if term and len(term) > 2]))
        
        return search_terms[:10]  # Limit to 10 terms
    
    async def _intelligent_document_search(self, search_terms: List[str], project_filter: Optional[str] = None) -> List[Dict]:
        """Search documents using intelligent terms."""
        try:
            # Create search query
            search_query = ' OR '.join(search_terms)
            
            # Build search parameters
            search_params = {
                'search_text': search_query,
                'top': 20,
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder"]
            }
            
            # Add project filter if specified
            if project_filter:
                search_params['filter'] = f"project_name eq '{project_filter}'"
            
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Intelligent search completed", 
                       search_terms=search_terms,
                       documents_found=len(documents))
            
            return documents
            
        except Exception as e:
            logger.error("Intelligent document search failed", error=str(e))
            return []
    
    async def _generate_intelligent_natural_answer(self, question: str, documents: List[Dict], intent: Dict[str, Any]) -> str:
        """Generate natural answer using GPT with intent context."""
        try:
            # Prepare context from documents
            context_parts = []
            for doc in documents[:10]:  # Limit to top 10 documents
                content = doc.get('content', '')
                filename = doc.get('filename', 'Unknown')
                blob_url = doc.get('blob_url', '')
                
                if content:
                    context_part = f"**Document: {filename}**\n{content[:1200]}..."
                    if blob_url:
                        context_part += f"\nURL: {blob_url}"
                    context_parts.append(context_part)
            
            if not context_parts:
                return f"I searched our database but couldn't find specific information about: {question}"
            
            context = "\n\n".join(context_parts)
            intent_type = intent.get('intent', 'GENERAL_ENGINEERING')
            topic = intent.get('topic', 'engineering question')
            
            # Create specialized prompt based on intent
            if intent_type == 'DESIGN_GUIDANCE':
                system_prompt = "You are a senior structural engineer at DTCE. Provide practical design guidance based on the documents provided."
                focus_instructions = """
- Provide step-by-step design guidance
- Include relevant calculations or approaches
- Reference specific standards or codes when mentioned
- Give practical engineering advice
- Mention safety factors and considerations"""
                
            elif intent_type == 'NZS_CODE_LOOKUP':
                system_prompt = "You are an expert in New Zealand building standards. Provide accurate code information."
                focus_instructions = """
- Quote specific clauses or sections when available
- Explain the requirements clearly
- Provide context for when these apply
- Mention related standards if relevant"""
                
            elif intent_type == 'PROJECT_REFERENCE':
                system_prompt = "You are a DTCE project manager with access to past project information."
                focus_instructions = """
- Describe relevant past projects
- Include job numbers when available
- Explain project scope and outcomes
- Provide SuiteFiles links when mentioned"""
                
            else:
                system_prompt = "You are a senior engineer at DTCE. Provide clear, practical engineering guidance."
                focus_instructions = """
- Provide clear, technical explanations
- Include practical considerations
- Reference specific projects or examples when available
- Give actionable engineering advice"""
            
            prompt = f"""Based on the following documents from DTCE's engineering database, please answer this {topic} question: {question}

{focus_instructions}

Context from DTCE documents:
{context}

CRITICAL INSTRUCTIONS:
- Provide a natural, conversational answer
- ONLY use information that is explicitly provided in the context above
- NEVER create or invent project numbers, job numbers, or file names
- NEVER create or mention URLs unless they are explicitly provided in the context
- If a document filename is mentioned in context, you can reference it
- If information is partial or missing, be honest about limitations
- Focus on practical engineering guidance based on available information
- Keep response professional but approachable
- If no specific documents are found, provide general engineering guidance

Answer:"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Failed to generate intelligent natural answer", error=str(e))
            return f"I found relevant documents but encountered an error generating a response. Please try rephrasing your question."
    
    async def _generate_no_documents_response(self, question: str, intent: Dict[str, Any]) -> str:
        """Generate helpful response when no documents found."""
        intent_type = intent.get('intent', 'GENERAL_ENGINEERING')
        topic = intent.get('topic', 'your question')
        
        if intent_type == 'NZS_CODE_LOOKUP':
            return f"I couldn't find specific information about {topic} in our uploaded NZ Standards documents. You may need to refer to the physical NZ Standards or check if this information has been uploaded to our system."
            
        elif intent_type == 'PROJECT_REFERENCE':
            return f"I couldn't find past DTCE projects specifically matching {topic} in our database. This might be because:\n• The project details aren't indexed yet\n• Different keywords were used in the project documentation\n• The projects might be in a different format or location"
            
        elif intent_type == 'DESIGN_GUIDANCE':
            return f"I couldn't find specific design guidance for {topic} in our current database. For detailed design advice, you might want to:\n• Check if relevant standards are uploaded\n• Look for similar projects in SuiteFiles\n• Consult with senior engineers directly"
            
        else:
            return f"I searched our engineering database but couldn't find specific information about {topic}. This might be because the information uses different terminology or hasn't been uploaded to our system yet. Try rephrasing your question or checking SuiteFiles directly."
    
    async def _basic_fallback_search(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Basic fallback search when all else fails."""
        try:
            # Simple keyword search
            keywords = [word for word in question.split() if len(word) > 3][:5]
            search_query = ' OR '.join(keywords)
            
            search_params = {
                'search_text': search_query,
                'top': 10,
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder"]
            }
            
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            if documents:
                # Simple answer generation
                answer = f"I found {len(documents)} documents that might be relevant to your question about: {question}\n\nKey documents found:\n"
                for i, doc in enumerate(documents[:3], 1):
                    answer += f"{i}. {doc.get('filename', 'Unknown')}\n"
                
                answer += "\nPlease check these documents or try rephrasing your question for more specific results."
                
                return {
                    'answer': answer,
                    'sources': self._format_sources_intelligent(documents),
                    'confidence': 'low',
                    'documents_searched': len(documents),
                    'search_type': 'basic_fallback'
                }
            else:
                return {
                    'answer': f"I couldn't find relevant information for your question: {question}\n\nTry:\n• Using different keywords\n• Being more specific about what you're looking for\n• Checking if the information is in SuiteFiles",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'no_results'
                }
                
        except Exception as e:
            logger.error("Basic fallback search failed", error=str(e))
            return {
                'answer': f"I encountered an error while searching for: {question}. Please try again or contact support.",
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'search_type': 'error'
            }
    
    def _format_sources_intelligent(self, documents: List[Dict]) -> List[Dict]:
        """Format sources with intelligent ranking."""
        sources = []
        for doc in documents[:5]:  # Limit to top 5 sources
            blob_url = doc.get('blob_url', '')
            # Convert blob URL to SuiteFiles URL for direct access
            suitefiles_url = self._get_safe_suitefiles_url(blob_url)
            
            sources.append({
                'filename': doc.get('filename', 'Unknown'),
                'url': suitefiles_url,  # Use converted SuiteFiles URL
                'folder': doc.get('folder', 'Unknown'),
                'project': doc.get('project_name', 'Unknown'),
                'relevance': 'high' if len(doc.get('content', '')) > 500 else 'medium'
            })
        return sources
    
    def _calculate_intelligent_confidence(self, documents: List[Dict], intent: Dict[str, Any]) -> str:
        """Calculate confidence based on documents and intent match."""
        if not documents:
            return 'low'
        
        doc_count = len(documents)
        intent_confidence = intent.get('confidence', 0.5)
        
        # High confidence: Many docs + high intent confidence
        if doc_count >= 10 and intent_confidence > 0.8:
            return 'high'
        elif doc_count >= 5 and intent_confidence > 0.6:
            return 'medium'
        else:
            return 'low'
