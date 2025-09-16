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
    
    RESPONSE GUIDELINES FOR ALL QUERY TYPES:
    
    1. POLICY QUESTIONS (wellness policy, H&S policies):
       - Provide the actual policy content from documents
       - Include specific clauses and requirements
       - If policy not found, state clearly "I don't have access to that policy"
    
    2. CONTACT/CLIENT INFO (Who works with Aaron?, builders we've worked with):
       - Provide specific contact names, companies, roles
       - Include contact details if available (phone, email)
       - If contact not found, say "I couldn't find contact information for..."
       - NEVER give project analysis when asked for contacts
    
    3. PROJECT SEARCH (What is project 225?):
       - Provide project details: client, scope, location, status
       - Include key deliverables and timeline if available
       - For "INCLUDE SUPERSEDED FOLDERS" - search older/draft versions
    
    4. PROBLEM PROJECTS (clients don't like, complaints):
       - Flag projects with issues, complaints, or negative feedback
       - Include specific problems mentioned in correspondence
       - Warn about potential issues to avoid repeating
    
    5. ENGINEERING ADVICE/ANALYSIS:
       - Summarize technical findings from project documents
       - Provide design considerations and approaches used
       - Include lessons learned and recommendations
       - Reference relevant NZ Standards (NZS 3101, 3404, 1170, etc.)
    
    6. NZ STANDARDS QUERIES (clear cover requirements, strength factors):
       - Quote exact clauses and requirements from NZ Standards
       - Provide clause numbers and specific values
       - Include context and application guidance
    
    7. TEMPLATE/RESOURCE REQUESTS (PS1 templates, spreadsheets):
       - Provide specific documents/templates from SuiteFiles
       - Include direct links when available
       - Suggest alternatives if primary template not found
    
    8. ADVISORY QUESTIONS (Should I reuse?, What to be aware of?):
       - Give specific recommendations based on past projects
       - Include warnings about common pitfalls
       - Suggest best practices and verification steps
       - Always add engineering safety reminders
    
    9. SUPERSEDED/VERSION QUERIES:
       - Include older versions when specifically requested
       - Compare changes between draft and final versions
       - Flag significant revisions or updates
    
    10. LESSONS LEARNED/PROBLEM ANALYSIS:
        - Identify specific issues from past projects
        - Provide actionable recommendations to avoid problems
        - Include client feedback and post-project reviews
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

**CRITICAL: ANSWER THE SPECIFIC QUESTION ASKED**

{core_instructions}

---

### **Context-Specific Instructions:**

{intent_instructions}"""
    
    def _get_policy_instructions(self) -> str:
        """Instructions for policy-related queries."""
        return """**Policy and Procedure Guidance:**
* **DIRECT POLICY CONTENT:** For wellness policy, wellbeing policy, H&S policies - provide the actual policy text from documents
* **SPECIFIC ANSWERS:** 
  - "What is our wellness policy?" → Quote the wellness policy document content
  - "What does it say?" → Provide key provisions and requirements
  - Search for variations: "wellness", "wellbeing", "employee wellness", "staff wellness"
* **FORMAT:** 
  - Policy Name: [Exact policy title]
  - Key Provisions: [Main policy points]
  - Requirements: [What employees must do]
  - Contact: [Who to contact for questions]
* **NOT FOUND:** If policy not in database, state: "I don't have access to the [specific policy name] in our document database. Please check with HR or the office administrator."
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
* **EXACT CLAUSES:** Quote the specific clause numbers and requirements from NZ Standards
* **SPECIFIC QUERIES:**
  - "minimum clear cover requirements" → Quote exact clause from NZS 3101 with cover values
  - "detailing requirements for beams" → Provide specific clause numbers and requirements
  - "strength reduction factors" → List exact φ factors for different load combinations
  - "composite slab design codes" → Reference specific NZS codes (3404, 3101, etc.)
* **FORMAT:**
  - Standard: [NZS number and title]
  - Clause: [Specific clause number]
  - Requirement: [Exact text or values]
  - Application: [When/how to use]
* **DIRECT FROM DATABASE:** Only provide information directly obtained from uploaded NZ Standard documents
* **NOT FOUND:** If specific standard not available, state: "I don't have access to that specific NZS clause in our database."
* **Application:** Explain the practical application of the standard to the user's query.
* **Context:** Briefly explain the purpose of the standard and its importance."""
    
    def _get_project_reference_instructions(self) -> str:
        """Instructions for project reference queries."""
        return """**Project and Client Guidance:**
* **Comprehensive Summary:** Provide a high-level summary of the project's key aspects (e.g., design approach, materials, challenges).
* **Advisory Tone:** Use a conversational and advisory tone. Provide "lessons learned" or "what to do/not to do" based on the project information.
* **Warning System:** If the documents mention a client being upset or a project having issues, explicitly state this in a clear, brief warning before the main answer."""
    
    def _get_project_search_instructions(self) -> str:
        """Instructions for direct project search queries."""
        return """**DIRECT PROJECT INFORMATION:**
* **ANSWER THE SPECIFIC QUESTION:** If asked "What is project X?", provide key project details directly. If asked about contacts, provide contact info only.
* **CONCISE PROJECT DETAILS:**
  - Project: [Number/Name]
  - Client: [Client name]
  - Location: [Address/Location]
  - Scope: [Brief description]
  - Contact: [Contact person if available and requested]
* **NO VERBOSE CONTENT:** Do NOT provide lengthy project summaries, design methodologies, lessons learned, or advisory content unless specifically requested.
* **DIRECT ANSWERS ONLY:** Answer exactly what was asked - nothing more, nothing less."""
    
    def _get_keyword_project_search_instructions(self) -> str:
        """Instructions for keyword-based project searches."""
        return """**KEYWORD PROJECT SEARCH - EXPECTED OUTPUT:**
* **JOB NUMBERS:** Provide specific job numbers that match the keywords
* **DIRECT SUITEFILES LINKS:** Include direct links to specific folders in SuiteFiles where possible
* **KEYWORD MATCHING:**
  - "precast panel" → Find projects with precast panel scope
  - "precast connection" → Projects with precast connection details  
  - "timber retaining wall" → Timber retaining wall projects
  - "steel structure retrofit" → Steel retrofit projects
* **OUTPUT FORMAT:**
  - Project: [Job Number - Project Name]
  - Client: [Client name]
  - Scope: [Relevant scope description matching keywords]
  - SuiteFiles Link: [Direct folder link if available]
  - Keywords Found: [Which specific keywords were matched]
* **DESIGN PHILOSOPHY HELP:** When asked to "help draft design philosophy":
  - Provide examples from past projects
  - Extract design approaches used
  - Include lessons learned and best practices
* **SIMILAR SCOPE MATCHING:** Prioritize projects with most similar scope to user's current needs"""
    
    def _get_template_search_instructions(self) -> str:
        """Instructions for template search queries."""
        return """**TEMPLATE SEARCH - EXPECTED OUTPUT:**
* **SPECIFIC DOCUMENTS:** Provide exact templates/spreadsheets with direct links
* **TEMPLATE TYPES:**
  - "PS1 template" → Provide PS1 template with SuiteFiles link
  - "PS3 template" → If not in SuiteFiles, provide legitimate external link for NZ councils
  - "timber beam design spreadsheet" → DTCE's calculation spreadsheets
  - "calculation templates" → Multi-storey timber, steel design, etc.
* **OUTPUT FORMAT:**
  - Template: [Template name]
  - Location: [SuiteFiles path or external link]
  - Direct Link: [Clickable link for easy access]
  - Purpose: [What the template is used for]
  - Notes: [Any customization requirements]
* **ALTERNATIVE OPTIONS:** If primary template not found, suggest similar alternatives
* **REDUCE SEARCH TIME:** Goal is to eliminate manual searching through SuiteFiles or internet"""
    
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
        return """**DIRECT CONTACT INFORMATION RETRIEVAL:**
* **ANSWER THE QUESTION ASKED:** If the user asks "Who is the contact for project X?", provide ONLY the contact name/details. Do NOT provide project methodology, design approaches, or lengthy analysis.
* **CONTACT FORMAT:** 
  - Contact: [Name]
  - Role: [Title/Position]
  - Company: [Company name]
  - Email: [Email if available]
  - Phone: [Phone if available]
  - Project: [Project context if relevant]

* **SPECIFIC QUERY TYPES:**
  - "Who works with Aaron from TGCS?" → Find Aaron's contact details and DTCE staff who work with him
  - "Builders we've worked with" → List construction companies with contact details from past projects
  - "Contact for project X" → Project manager or client contact for specific project
  - "Who handles project Y" → Staff member assigned to the project

* **BUILDER/CONTRACTOR QUERIES:** When asked about builders/contractors:
  - List company names with contact details
  - Include project history and performance notes
  - Flag any issues or positive feedback mentioned
  - For steel retrofits: prioritize builders with steel experience

* **FORBIDDEN CONTENT:** 
  - DO NOT include project design methodologies
  - DO NOT provide comprehensive project analysis
  - DO NOT discuss technical specifications unless specifically asked
  - DO NOT give "lessons learned" unless requested

* **NOT FOUND RESPONSE:** If contact information isn't available, say: "I couldn't find contact information for [specific request] in our document database. You may want to check with the project manager or office administrator."
* **BE CONCISE:** Extract and present ONLY the contact information requested. Do not add project summaries, scope discussions, or advisory content.
* **NOT FOUND RESPONSE:** If contact information is not available, simply state: "Contact information for project [X] was not found in the available documents."
* **FORBIDDEN:** Do NOT discuss project scope, design approaches, methodologies, lessons learned, or provide step-by-step instructions unless specifically requested."""
    
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
        Detect when users explicitly request to override standard instructions or ask direct questions.
        
        Args:
            user_question: The user's question to analyze
            
        Returns:
            Dictionary of detected overrides
        """
        if not user_question:
            return {}
        
        question_lower = user_question.lower()
        overrides = {}
        
        # Detect direct information questions that require concise answers
        direct_question_patterns = [
            "who is the contact", "who is contact", "contact for", "who works with",
            "what is project", "what is the project", "project number", "project details",
            "who is", "what is", "when is", "where is", "how much", "how many"
        ]
        
        # Detect if this is a direct information request
        if any(pattern in question_lower for pattern in direct_question_patterns):
            overrides['direct_answer_required'] = True
        
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
        
        # Check if this is a direct answer requirement
        if user_overrides.get('direct_answer_required', False):
            instructions.append("1. **DIRECT ANSWER REQUIRED:** The user asked a specific, direct question. Provide ONLY the requested information. Do NOT add project summaries, methodologies, or advisory content.")
        else:
            instructions.append("1. **Understand the Question:** Fully understand the user's question and what they are trying to achieve. ANSWER THE SPECIFIC QUESTION ASKED - do not provide generic summaries if they asked for specific information.")
        
        # Conditional analysis instruction based on query type
        if user_overrides.get('direct_answer_required', False):
            instructions.append("2. **Extract Specific Information:** Find and extract only the specific information requested (contact name, project details, etc.). Present it clearly and concisely.")
        elif not user_overrides.get('skip_analysis', False):
            instructions.append("2. **Be Appropriately Direct:** For direct information requests (contact info, project details, specific facts), provide concise, focused answers. For complex queries requiring analysis, provide comprehensive responses.")
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
        
        # Add special note for direct answer requirements
        if user_overrides.get('direct_answer_required', False):
            override_note = "\n**DIRECT ANSWER MODE:** The user asked a specific question requiring a direct answer. Do NOT provide general project analysis, methodology discussions, or step-by-step instructions unless specifically requested."
            return f"**Core Instructions (Direct Answer Mode):**\n" + "\n".join(instructions) + override_note
        elif user_overrides:
            override_note = "\n**USER OVERRIDE DETECTED:** The user has made explicit requests that override standard instructions. These user requests take absolute priority."
            return f"**Core Instructions (Adapted to User Requests):**\n" + "\n".join(instructions) + override_note
        else:
            return f"**Core Instructions:**\n" + "\n".join(instructions)
    
    def _get_general_instructions(self) -> str:
        """Instructions for general engineering queries."""
        return """**COMPREHENSIVE ENGINEERING GUIDANCE:**

**1. SUPERSEDED FOLDERS:** When user asks "INCLUDE SUPERSEDED FOLDERS" or mentions "older versions":
* Search for and include draft, superseded, and older versions of documents
* Compare changes between draft and final versions
* Flag significant revisions and updates

**2. ENGINEERING ADVICE & SUMMARIZATION:**
* Move beyond just listing files - provide technical insights and advice
* Summarize design considerations from final reports
* Extract foundation types used across similar projects
* Identify typical approaches for wind loading, timber bridges, etc.

**3. CLIENT ISSUE WARNINGS:**
* Detect and warn about projects where clients raised concerns
* Flag correspondence mentioning complaints, rework requests, scope changes
* Provide warnings like "⚠️ CAUTION: Client expressed concerns about..."

**4. ADVISORY RECOMMENDATIONS:**
* Give specific recommendations: "Should I reuse this report?" → Yes/No with reasons
* Highlight what to be aware of when using older methods
* Recommend most suitable designs for specific conditions
* Identify common pitfalls in design phases

**5. ALWAYS ADD ENGINEERING BEST PRACTICES:**
* For ANY question, include relevant reminders:
  - "Make sure to check the latest NZ standards..."
  - "Ensure safety factor checks are included..."
  - "Verify compliance with current seismic requirements..."

**6. COMBINE MULTIPLE KNOWLEDGE SOURCES:**
* Link SuiteFiles data with NZ Standards compliance
* Cross-reference project specs with NZS codes
* Connect past project QA procedures with templates

**7. LESSONS LEARNED FOCUS:**
* Extract what went wrong/right in past projects
* Identify mistakes during review stages
* Highlight common issues during 'Issued' phase
* Provide "what NOT to do" guidance

**8. ALWAYS INCLUDE NZ STANDARDS REMINDERS:**
* Reference relevant NZS codes (3101, 3404, 1170, 4404, 3910)
* Include safety and compliance reminders
* Add verification steps and professional guidance"""
