"""
Prompt Builder Service - Constructs optimized prompts for different RAG scenarios
"""

from typing import Dict, List, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class PromptBuilder:
    """
    Service for building optimized prompts for different RAG scenarios.
    Implements advanced prompt engineering techniques for better LLM responses.
    """
    
    def __init__(self):
        self.prompt_templates = self._initialize_prompt_templates()
    
    def _initialize_prompt_templates(self) -> Dict[str, Dict[str, str]]:
        """
        Initialize prompt templates for different categories and scenarios.
        """
        return {
            'policy': {
                'system': """You are DTCE's AI assistant specializing in company policies and procedures. Extract and explain policy information clearly and comprehensively. Focus on practical implications for employees.""",
                'user_template': """Question: {question}

Policy Documents:
{retrieved_content}

INSTRUCTIONS: Extract the specific policy information and provide a comprehensive answer including:
1. Policy requirements and provisions
2. Practical implications for employees  
3. Key compliance points
4. Related procedures or guidelines

Provide the actual content, not just document references."""
            },
            
            'procedures': {
                'system': """You are DTCE's procedural expert. Extract and explain step-by-step procedures, requirements, and practical implementation guidance from the provided documents.""",
                'user_template': """Question: {question}

Procedure Documents:
{retrieved_content}

INSTRUCTIONS: Extract procedural information and provide:
1. Step-by-step procedures where applicable
2. Requirements and guidelines
3. Forms, templates, or tools mentioned
4. Practical implementation details

Give complete information needed to follow the procedure."""
            },
            
            'nz_standards': {
                'system': """You are a New Zealand structural engineering standards expert. Extract and explain technical requirements, specifications, and compliance guidelines from NZ standards documents.""",
                'user_template': """Question: {question}

NZ Standards Documents:
{retrieved_content}

INSTRUCTIONS: Extract specific technical information including:
1. Exact clauses, requirements, and specifications
2. Technical parameters and limits
3. Design requirements and calculations
4. Compliance guidelines and best practices

Provide precise technical details with standard references."""
            },
            
            'project_reference': {
                'system': """You are DTCE's project information specialist. Answer specific questions about projects directly and concisely. Only provide comprehensive analysis if specifically requested.""",
                'user_template': """Question: {question}

Project Documents:
{retrieved_content}

INSTRUCTIONS: Answer the specific question directly. For:
- Contact information: Provide names and roles
- Project details: Give specific requested information  
- Costs/timelines: Provide exact figures
- Technical specs: Give precise requirements

Be direct and specific, not comprehensive unless asked for analysis."""
            },
            
            'client_reference': {
                'system': """You are DTCE's client information specialist. Answer questions about clients, contacts, and business relationships directly with specific details from the documents.""",
                'user_template': """Question: {question}

Client/Contact Documents:
{retrieved_content}

INSTRUCTIONS: Answer directly with specific information from documents:
- Look for mentions of people/companies
- Provide direct yes/no answers with supporting details
- Include project numbers, emails, or contact information found
- Be specific, not generic"""
            },
            
            'general_engineering': {
                'system': """You are a senior structural engineering consultant providing comprehensive advisory guidance. Combine technical expertise with practical insights, risk assessment, and professional recommendations.""",
                'user_template': """Question: {question}

PROVIDE COMPREHENSIVE ENGINEERING GUIDANCE INCLUDING:
1. Direct technical answer with engineering principles
2. Relevant NZ standards (NZS 3101, 3404, 1170, etc.)
3. Common mistakes and pitfalls to avoid
4. Quality assurance and verification approaches
5. Risk assessment and safety considerations
6. Industry best practices and lessons learned
7. Professional advisory recommendations

Combine technical knowledge with practical professional guidance."""
            },
            
            'conversational': {
                'system': """You are DTCE AI Assistant having a natural conversation. Respond conversationally and helpfully, acknowledging the user's response appropriately.""",
                'user_template': """Previous conversation context:
{conversation_context}

User said: "{question}"

Respond naturally and conversationally. Keep it brief and acknowledge their response appropriately."""
            }
        }
    
    def build_prompt(
        self, 
        category: str, 
        question: str, 
        retrieved_content: str = "",
        conversation_context: str = "",
        additional_context: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """
        Build an optimized prompt for the given category and context.
        
        Args:
            category: The query category (policy, procedures, etc.)
            question: User's question
            retrieved_content: Content retrieved from documents
            conversation_context: Previous conversation for conversational queries
            additional_context: Additional context information
            
        Returns:
            Dictionary with 'system' and 'user' prompts
        """
        try:
            logger.info("Building prompt", category=category)
            
            # Get template for category
            template = self.prompt_templates.get(category, self.prompt_templates['general_engineering'])
            
            # Build system prompt
            system_prompt = template['system']
            
            # Build user prompt
            user_prompt = template['user_template'].format(
                question=question,
                retrieved_content=retrieved_content or "No specific documents found.",
                conversation_context=conversation_context or "No previous conversation"
            )
            
            # Add additional context if provided
            if additional_context:
                context_additions = self._format_additional_context(additional_context)
                if context_additions:
                    user_prompt += f"\n\nAdditional Context:\n{context_additions}"
            
            return {
                'system': system_prompt,
                'user': user_prompt
            }
            
        except Exception as e:
            logger.error("Prompt building failed", error=str(e))
            return self._fallback_prompt(question, retrieved_content)
    
    def build_search_strategy_prompt(self, question: str) -> str:
        """
        Build prompt for determining search strategy and intent classification.
        """
        return f"""Analyze this user query and determine the search strategy:

User Query: "{question}"

Classify into one of these categories:
1. **POLICY** - Company policies, H&S, IT policies
2. **PROCEDURES** - Processes, procedures, handbooks, how-to guides
3. **NZ_STANDARDS** - NZ engineering standards, codes, regulations
4. **PROJECT_REFERENCE** - Specific projects, project details, history
5. **CLIENT_REFERENCE** - Clients, contacts, client information
6. **GENERAL_ENGINEERING** - General engineering questions

Also determine:
- Does this need DTCE document search? (true/false)
- What folders should be searched?
- Confidence level (0.0 to 1.0)
- Key search terms

Respond in JSON format:
{{
    "category": "category_name",
    "needs_dtce_search": true/false,
    "search_folders": ["folder1", "folder2"],
    "confidence": 0.85,
    "reasoning": "explanation",
    "search_terms": ["term1", "term2"]
}}"""
    
    def build_fallback_prompt(self, question: str, error_context: str = "") -> Dict[str, str]:
        """
        Build a fallback prompt when normal processing fails.
        """
        system_prompt = """You are DTCE AI Assistant. An error occurred during document search, but you can still provide helpful general engineering guidance."""
        
        user_prompt = f"""Question: {question}

I encountered an issue searching our document database, but I can still help with general engineering guidance.

{f"Error context: {error_context}" if error_context else ""}

Please provide helpful general engineering advice related to this question, acknowledging that you couldn't access specific DTCE documents."""
        
        return {
            'system': system_prompt,
            'user': user_prompt
        }
    
    def _format_additional_context(self, context: Dict[str, Any]) -> str:
        """
        Format additional context information for inclusion in prompts.
        """
        formatted_parts = []
        
        if context.get('project_info'):
            project_info = context['project_info']
            if project_info.get('project_number'):
                formatted_parts.append(f"Project Number: {project_info['project_number']}")
            if project_info.get('project_year'):
                formatted_parts.append(f"Project Year: {project_info['project_year']}")
        
        if context.get('technical_terms'):
            terms = context['technical_terms']
            if terms:
                formatted_parts.append(f"Technical Terms: {', '.join(terms)}")
        
        if context.get('confidence_level'):
            formatted_parts.append(f"Search Confidence: {context['confidence_level']}")
        
        return '\n'.join(formatted_parts)
    
    def _fallback_prompt(self, question: str, retrieved_content: str) -> Dict[str, str]:
        """
        Fallback prompt when template building fails.
        """
        return {
            'system': "You are DTCE AI Assistant, a helpful engineering AI that provides accurate information based on available documents.",
            'user': f"""Question: {question}

Available Information:
{retrieved_content or "No specific documents found."}

Please provide a helpful response based on the available information."""
        }
    
    def optimize_for_token_limit(self, prompt: Dict[str, str], max_tokens: int = 3000) -> Dict[str, str]:
        """
        Optimize prompt length to fit within token limits.
        """
        # Rough estimate: 1 token ≈ 4 characters
        max_chars = max_tokens * 4
        
        system_prompt = prompt['system']
        user_prompt = prompt['user']
        
        total_length = len(system_prompt) + len(user_prompt)
        
        if total_length <= max_chars:
            return prompt
        
        # Truncate user prompt if needed, keeping system prompt intact
        available_for_user = max_chars - len(system_prompt) - 100  # Buffer
        
        if len(user_prompt) > available_for_user:
            # Truncate while trying to keep the question and instructions
            lines = user_prompt.split('\n')
            question_line = lines[0] if lines else ""
            
            truncated = question_line + "\n\n[Content truncated due to length limits]\n"
            remaining_space = available_for_user - len(truncated)
            
            if remaining_space > 0:
                # Add as much content as possible
                content_part = '\n'.join(lines[1:])[:remaining_space]
                truncated += content_part
            
            user_prompt = truncated
        
        logger.info("Prompt optimized for token limit", 
                   original_length=total_length, 
                   optimized_length=len(system_prompt) + len(user_prompt))
        
        return {
            'system': system_prompt,
            'user': user_prompt
        }
