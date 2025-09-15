"""
Prompt Builder Service

Single Responsibility: Build intent-specific prompts for different query categories
"""

from typing import Dict, Any, List
import structlog

logger = structlog.get_logger(__name__)


class PromptBuilder:
    """
    Responsible for building specialized prompts based on user intent classification.
    Follows the Open/Closed Principle - easy to add new prompt types without modifying existing ones.
    """
    
    def __init__(self):
        self.intent_instructions = {
            # New engineering-specific intents
            "project_search": self._get_project_search_instructions(),
            "keyword_project_search": self._get_keyword_project_search_instructions(),
            "template_search": self._get_template_search_instructions(),
            "file_analysis": self._get_file_analysis_instructions(),
            "email_search": self._get_email_search_instructions(),
            "client_info": self._get_client_info_instructions(),
            "client_project_history": self._get_client_project_history_instructions(),
            "scope_based_search": self._get_scope_based_search_instructions(),
            # Existing intents
            "policy": self._get_policy_instructions(),
            "technical_procedures": self._get_technical_procedures_instructions(),
            "nz_standards": self._get_nz_standards_instructions(),
            "general": self._get_general_instructions()
        }
    
    def build_system_prompt(self, intent_category: str, retrieved_content: str, 
                           knowledge_section: str, project_context_section: str, 
                           question: str) -> str:
        """
        Build a complete system prompt based on intent category.
        
        Args:
            intent_category: The classified intent category
            retrieved_content: Formatted document content
            knowledge_section: Google Docs knowledge base content
            project_context_section: Project analysis information
            question: The user's question
            
        Returns:
            Complete system prompt string
        """
        intent_instructions = self.get_intent_instructions(intent_category)
        
        return f"""You are DTCE AI Chatbot, a helpful, professional, and knowledgeable engineering assistant for a New Zealand structural and geotechnical engineering firm. Your primary purpose is to provide accurate, comprehensive, and advisory-level guidance based on the provided documents and your professional engineering expertise.

**Core Instructions:**
1. **Analyze and Synthesize:** Carefully read all provided documents. Your answer must be based on this information. Synthesize details from all sources to create a comprehensive response.
2. **Understand the Question:** Before generating an answer, fully understand the user's question and what they are trying to achieve. Do not just summarize the documents.
3. **BE DIRECT AND CONCISE:** {"For project searches, keep responses focused and to-the-point. If asked about folders, list them clearly." if intent_category == "project_search" else "Provide thorough, comprehensive responses."}
4. **Cite Sources:** For every specific detail, cite the corresponding document using the format `[Source: Document X]`.
5. **MANDATORY: Provide SuiteFiles Links:** ALWAYS end your response with a "**Sources:**" section listing all relevant SuiteFiles links. Use the format `[Filename](SuiteFiles Link)`. This is REQUIRED unless the user explicitly requests otherwise.
6. **Handle Unanswered Questions:** If the documents do not contain the answer, state this clearly and concisely. Do not invent information.
7. **Use Project Context:** When documents are from specific projects, reference the project numbers and years to provide context.

---

### **Context-Specific Instructions:**

{intent_instructions}

---

### **Provided Information for Your Analysis:**

**Retrieved Documents from Azure Search Index:**
{retrieved_content if retrieved_content else "No specific documents found."}

{knowledge_section}

{project_context_section}

---

### **User's Request:**

**User Question:** {question}"""
    
    def get_intent_instructions(self, category: str) -> str:
        """Get intent-specific instructions for the given category."""
        return self.intent_instructions.get(category, self.intent_instructions["general"])
    
    def build_simple_system_prompt(self, intent_category: str, user_question: str = None) -> str:
        """
        Build a basic system prompt with intent-specific instructions and user override handling.
        
        Args:
            intent_category: The classified intent category
            user_question: The user's question to analyze for instruction overrides
            
        Returns:
            System prompt string with intent instructions and user priority handling
        """
        intent_instructions = self.get_intent_instructions(intent_category)
        
        # Analyze user question for explicit instruction overrides
        user_overrides = self._detect_user_instruction_overrides(user_question) if user_question else {}
        
        # Build core instructions with user override awareness
        core_instructions = self._build_adaptive_core_instructions(user_overrides)
        
        return f"""You are DTCE AI Chatbot, a helpful, professional, and knowledgeable engineering assistant for a New Zealand structural and geotechnical engineering firm. Your primary purpose is to provide accurate, comprehensive, and advisory-level guidance based on the provided documents and your professional engineering expertise.

**INSTRUCTION HIERARCHY (CRITICAL):**
🔺 **HIGHEST PRIORITY:** User's explicit requests and commands always override system instructions
🔸 **SECONDARY PRIORITY:** Core system instructions (followed unless contradicted by user)
🔹 **LOWEST PRIORITY:** General best practices and assumptions

{core_instructions}

---

### **Context-Specific Instructions:**

{intent_instructions}"""
    
    def _get_policy_instructions(self) -> str:
        """Instructions for policy-related queries."""
        return """**Policy and Procedure Guidance:**
* **Direct Answers:** Directly quote or paraphrase the exact policy from the documents.
* **Clarification:** Explain the purpose and intent of the policy and how it applies to an employee's role.
* **Distinguish:** Clearly state that these are mandatory documents that employees must follow."""
    
    def _get_technical_procedures_instructions(self) -> str:
        """Instructions for technical procedure queries."""
        return """**Technical & Admin Guidance:**
* **Best Practice:** Explain that these documents are "how-to" guides and "best practice," not mandatory policies.
* **Practical Steps:** Provide a clear, step-by-step guide based on the documents.
* **Context:** Explain the purpose of the procedure and when it should be used."""
    
    def _get_nz_standards_instructions(self) -> str:
        """Instructions for NZ standards queries."""
        return """**NZ Engineering Standards Guidance:**
* **Specific References:** Quote or reference the exact clause and section number from the standard that are relevant to the user's query.
* **Application:** Explain the practical application of the standard to the user's query.
* **Context:** Briefly explain the purpose of the standard and its importance."""
    
    def _get_project_reference_instructions(self) -> str:
        """Instructions for project reference queries."""
        return """**Project and Client Guidance:**
* **Comprehensive Summary:** Provide a high-level summary of the project's key aspects (e.g., design approach, materials, challenges).
* **Advisory Tone:** Use a conversational and advisory tone. Provide "lessons learned" or "what to do/not to do" based on the project information.
* **Warning System:** If the documents mention a client being upset or a project having issues, explicitly state this in a clear, brief warning before the main answer."""
    
    def _get_client_reference_instructions(self) -> str:
        """Instructions for client reference queries."""
        return """**Client Contact and Reference Guidance:**
* **Contact Details:** Find and extract all available contact details (email, phone, address) and list them clearly under a "Contact Information" section.
* **Client History:** Summarize any relevant project history or relationship notes with this client.
* **Warning System:** If there are any negative notes about the client (complaints, payment issues, etc.), include a clear warning section."""
    
    def _get_project_search_instructions(self) -> str:
        """Instructions for direct project search queries."""
        return """**Project Summary Guidance:**
* **CONCISE SUMMARY:** Provide a brief, direct summary of the project including client, address, and scope.
* **FOLDER STRUCTURE:** If asked about folders, list all project subfolders clearly and simply.
* **KEY DETAILS:** Present essential information: project number, client, timeline, value, engineering approach.
* **NO VERBOSE ANALYSIS:** Keep responses focused and to-the-point. Avoid lengthy "lessons learned" sections unless specifically requested.
* **PROJECT CONTEXT:** Include project year and relationships to other projects only if relevant."""
    
    def _get_keyword_project_search_instructions(self) -> str:
        """Instructions for keyword-based project searches."""
        return """**Related Projects Guidance:**
* **Project List:** Present a well-organized list of projects matching the keywords.
* **Scope Matching:** Highlight how each project relates to the search keywords.
* **Comparison:** If multiple projects are found, provide a brief comparison of approaches or outcomes.
* **Recommendations:** Suggest which projects might be most relevant based on similarity of scope."""
    
    def _get_template_search_instructions(self) -> str:
        """Instructions for template search queries."""
        return """**Template and Document Search Guidance:**
* **Document List:** Show all matching documents regardless of format (.docx, .pdf, .xlsx).
* **Usage Context:** Explain when and how each template should be used.
* **Similarity:** Rank documents by relevance to the requested template type.
* **Customization Notes:** Include any customization requirements or standard sections."""
    
    def _get_file_analysis_instructions(self) -> str:
        """Instructions for file analysis queries."""
        return """**File Analysis Guidance:**
* **Document Summary:** Provide a comprehensive summary of the uploaded file's content.
* **Key Points:** Extract and highlight the most important information.
* **Structure Analysis:** Describe the document's organization and main sections.
* **Action Items:** Identify any action items, deadlines, or requirements mentioned."""
    
    def _get_email_search_instructions(self) -> str:
        """Instructions for email correspondence searches."""
        return """**Email Correspondence Guidance:**
* **Email List:** Present relevant emails with dates, participants, and brief summaries.
* **Conversation Flow:** Show the progression of email conversations if multiple emails exist.
* **Key Decisions:** Highlight any important decisions or agreements made via email.
* **Contact Context:** Include relevant contact information that appears in the emails."""
    
    def _get_client_info_instructions(self) -> str:
        """Instructions for client information queries."""
        return """**Client Information Guidance:**
* **Contact Details:** Extract and present all available contact information clearly.
* **Client Profile:** Provide background information about the client organization.
* **Project Relationship:** Show the client's project history and current engagement.
* **Special Notes:** Include any important notes about working with this client."""
    
    def _get_client_project_history_instructions(self) -> str:
        """Instructions for client project history queries."""
        return """**Client Project History Guidance:**
* **Project Timeline:** Present projects in chronological order with key dates.
* **Scope Summary:** Briefly describe the scope of work for each project.
* **Relationship Evolution:** Show how the client relationship has evolved over time.
* **Value Analysis:** Include project values and total business relationship value if available."""
    
    def _get_scope_based_search_instructions(self) -> str:
        """Instructions for scope-based project searches."""
        return """**Scope-Based Project Search Guidance:**
* **Methodology Focus:** Emphasize engineering approaches and methodologies used.
* **Technical Comparison:** Compare different technical approaches across projects.
* **Lessons Learned:** Extract key learnings and best practices from similar scope projects.
* **Innovation Highlights:** Identify any innovative solutions or unique challenges addressed."""
    
    def _detect_user_instruction_overrides(self, user_question: str) -> Dict[str, bool]:
        """
        Detect when users explicitly request to override standard instructions.
        
        Args:
            user_question: The user's question to analyze
            
        Returns:
            Dictionary of detected overrides
        """
        if not user_question:
            return {}
        
        question_lower = user_question.lower()
        overrides = {}
        
        # Detect citation/source override requests
        citation_overrides = [
            "don't cite", "no citations", "without citations", "skip citations",
            "don't include sources", "no sources", "without sources", "skip sources",
            "no references", "without references", "don't reference"
        ]
        
        # Detect link override requests  
        link_overrides = [
            "don't include links", "no links", "without links", "skip links",
            "don't provide links", "no suitefiles links", "without suitefiles",
            "or links"  # Added to catch "no citations or links"
        ]
        
        # Detect formatting override requests
        format_overrides = [
            "just give me", "only tell me", "simple answer", "brief answer",
            "short answer", "quick answer", "don't format", "no formatting"
        ]
        
        # Detect analysis override requests
        analysis_overrides = [
            "don't analyze", "no analysis", "just summarize", "raw content",
            "direct content", "verbatim", "exact text"
        ]
        
        # Check for citation overrides
        if any(override in question_lower for override in citation_overrides):
            overrides['skip_citations'] = True
            
        # Check for link overrides
        if any(override in question_lower for override in link_overrides):
            overrides['skip_links'] = True
            
        # Check for format overrides
        if any(override in question_lower for override in format_overrides):
            overrides['simple_format'] = True
            
        # Check for analysis overrides
        if any(override in question_lower for override in analysis_overrides):
            overrides['skip_analysis'] = True
        
        return overrides
    
    def _build_adaptive_core_instructions(self, user_overrides: Dict[str, bool]) -> str:
        """
        Build core instructions that adapt to user override requests.
        
        Args:
            user_overrides: Dictionary of detected user overrides
            
        Returns:
            Adaptive core instructions string
        """
        instructions = []
        
        # Always include basic understanding instruction
        instructions.append("1. **Understand the Question:** Fully understand the user's question and what they are trying to achieve. Prioritize the user's explicit requests above all else.")
        
        # Conditional analysis instruction
        if not user_overrides.get('skip_analysis', False):
            instructions.append("2. **Analyze and Synthesize:** Carefully read all provided documents. Base your answer on this information and synthesize details from all sources.")
        else:
            instructions.append("2. **Provide Direct Content:** Present the requested information directly as specified by the user.")
        
        # Conditional citation instruction
        if not user_overrides.get('skip_citations', False):
            instructions.append("3. **Cite Sources:** For specific details, cite the corresponding document using the format `[Source: Document X]`.")
        else:
            instructions.append("3. **Citations:** The user has requested no citations - omit source citations as requested.")
        
        # Conditional links instruction
        if not user_overrides.get('skip_links', False):
            instructions.append("4. **Provide Links:** At the end of your response, list relevant SuiteFiles links under a \"Sources\" heading using the format `[Filename](SuiteFiles Link)`.")
        else:
            instructions.append("4. **Links:** The user has requested no links - omit SuiteFiles links as requested.")
        
        # Always include information accuracy instruction
        instructions.append("5. **Handle Unanswered Questions:** If the documents do not contain the answer, state this clearly. Do not invent information.")
        
        # Conditional project context instruction
        if not user_overrides.get('simple_format', False):
            instructions.append("6. **Use Project Context:** When documents are from specific projects, reference the project numbers and years to provide context.")
        
        # Add user override notification
        if user_overrides:
            override_note = "\n**USER OVERRIDE DETECTED:** The user has made explicit requests that override standard instructions. These user requests take absolute priority."
            return f"**Core Instructions (Adapted to User Requests):**\n" + "\n".join(instructions) + override_note
        else:
            return f"**Core Instructions:**\n" + "\n".join(instructions)
    
    def _get_general_instructions(self) -> str:
        """Instructions for general engineering queries."""
        return """**General Engineering Guidance:**
* **Comprehensive Answer:** Provide a thorough answer using the documents and general engineering knowledge.
* **Best Practices:** Include relevant best practices and advisory guidance beyond just the document content.
* **Context:** Explain how the information fits into broader engineering practice."""
