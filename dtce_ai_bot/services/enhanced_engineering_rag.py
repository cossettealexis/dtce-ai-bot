"""
Enhanced RAG Handler for Engineering-Specific Queries
Handles NZ Standards, project references, product specifications, templates, and design discussions
"""

import structlog
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

from .smart_rag_handler import SmartRAGHandler

logger = structlog.get_logger(__name__)


class EnhancedEngineeringRAGHandler(SmartRAGHandler):
    """
    Enhanced RAG Handler specifically designed for engineering queries.
    Handles specialized formatting for NZ Standards, project references, products, etc.
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        super().__init__(search_client, openai_client, model_name)
        
        # Engineering-specific query patterns
        self.engineering_patterns = {
            "nz_standards": {
                "triggers": [
                    "NZS", "NZ standard", "clause", "code", "minimum", "requirements",
                    "clear cover", "detailing requirements", "strength reduction",
                    "structural code", "composite slab", "floor diaphragm",
                    "seismic actions", "concrete element", "beam design"
                ],
                "response_type": "technical_standard"
            },
            "scenario_technical": {
                "triggers": [
                    "examples of", "show me", "mid-rise", "timber frame", "high wind zones",
                    "foundation systems", "steep slopes", "concrete shear walls",
                    "seismic strengthening", "connection details", "balconies",
                    "coastal apartment", "buildings we've designed"
                ],
                "response_type": "scenario_technical"
            },
            "problem_solving": {
                "triggers": [
                    "issues", "problems", "run into", "lessons learned", "failed",
                    "screw piles", "soft soils", "retaining walls", "construction",
                    "waterproofing methods", "basement walls", "high water table",
                    "what worked best", "summarise"
                ],
                "response_type": "problem_solving"
            },
            "regulatory_precedents": {
                "triggers": [
                    "council questioned", "consent", "precedent", "alternative solution",
                    "non-standard", "heritage building", "retrofits", "wind load calculations",
                    "stair designs", "bracing", "approached", "applications"
                ],
                "response_type": "regulatory_precedents"
            },
            "cost_time_insights": {
                "triggers": [
                    "how long", "typically take", "concept to PS1", "cost range",
                    "structural design", "multi-unit residential", "scope expanded",
                    "time", "duration", "budget", "commercial alterations"
                ],
                "response_type": "cost_time_insights"
            },
            "best_practices": {
                "triggers": [
                    "standard approach", "best example", "calculation templates",
                    "steel portal frames", "industrial buildings", "timber diaphragm",
                    "multi-storey timber", "our approach", "templates"
                ],
                "response_type": "best_practices"
            },
            "materials_comparison": {
                "triggers": [
                    "chosen", "over", "compare", "different", "precast concrete",
                    "in-situ concrete", "timber treatment levels", "exterior beams",
                    "coastal conditions", "seismic retrofit methods", "unreinforced masonry",
                    "when have we", "why"
                ],
                "response_type": "materials_comparison"
            },
            "knowledge_mapping": {
                "triggers": [
                    "which engineers", "who has", "experience with", "expertise in",
                    "tilt-slab construction", "pile design", "documented expertise",
                    "project notes", "authored by", "senior engineer"
                ],
                "response_type": "knowledge_mapping"
            },
            "project_reference": {
                "triggers": [
                    "past project", "reference", "job number", "example",
                    "precast panel", "precast connection", "unispans",
                    "timber retaining wall", "design philosophy",
                    "concrete precast panel building", "timber framed structure"
                ],
                "response_type": "project_reference"
            },
            "product_specification": {
                "triggers": [
                    "proprietary product", "waterproofing", "connection details",
                    "timber connection", "specifications", "suppliers",
                    "LVL timber", "sizes", "price", "Wellington",
                    "product links", "alternative products"
                ],
                "response_type": "product_specification"
            },
            "design_discussion": {
                "triggers": [
                    "online threads", "design procedures", "forums",
                    "composite beam", "haunched", "tapered",
                    "reinforced concrete column", "seismic",
                    "gravity actions", "design guidelines"
                ],
                "response_type": "design_discussion"
            },
            "contractor_reference": {
                "triggers": [
                    "builders", "companies", "contact details",
                    "constructed", "construction", "steel structure",
                    "retrofit", "brick building", "past 3 years"
                ],
                "response_type": "contractor_reference"
            },
            "template_access": {
                "triggers": [
                    "template", "spreadsheet", "PS1", "PS2", "PS3", "PS4",
                    "design spreadsheet", "timber beam design",
                    "council", "New Zealand", "SuiteFiles"
                ],
                "response_type": "template_access"
            },
            "scope_comparison": {
                "triggers": [
                    "fee proposal", "similar scope", "cantilever",
                    "corner window", "sliding door", "residential renovation",
                    "posts and beams", "concrete wall structure"
                ],
                "response_type": "scope_comparison"
            }
        }
    
    async def get_engineering_answer(self, user_question: str) -> Dict[str, Any]:
        """
        Enhanced answer generation specifically for engineering queries.
        Provides specialized formatting based on query type.
        """
        try:
            # First, get the basic smart routing
            routing_info = await self.query_router.route_query(user_question)
            
            # Detect engineering-specific patterns
            engineering_type = self._detect_engineering_query_type(user_question)
            
            # Search for documents
            documents = await self.search_service.smart_search(routing_info)
            
            # Generate specialized engineering response
            if documents:
                answer = await self._generate_engineering_answer(
                    user_question, documents, routing_info, engineering_type
                )
            else:
                answer = self._generate_engineering_no_results_answer(
                    user_question, routing_info, engineering_type
                )
            
            return {
                "answer": answer,
                "sources": documents[:5],
                "intent": routing_info.get("intent"),
                "engineering_type": engineering_type,
                "routing_info": routing_info
            }
            
        except Exception as e:
            logger.error("Engineering RAG failed", error=str(e), question=user_question[:100])
            return {
                "answer": "I encountered an error processing your engineering question. Please try rephrasing it or contact support.",
                "sources": [],
                "intent": "error",
                "engineering_type": "unknown"
            }
    
    def _detect_engineering_query_type(self, query: str) -> str:
        """Detect the specific type of engineering query."""
        query_lower = query.lower()
        
        for eng_type, config in self.engineering_patterns.items():
            triggers = config["triggers"]
            if any(trigger.lower() in query_lower for trigger in triggers):
                return config["response_type"]
        
        return "general_engineering"
    
    async def _generate_engineering_answer(self, question: str, documents: List[Dict], 
                                         routing_info: Dict, engineering_type: str) -> str:
        """Generate specialized engineering answers based on query type."""
        
        # Extract content from documents
        content_chunks = []
        source_links = []
        
        for i, doc in enumerate(documents[:3]):
            filename = doc.get('filename', 'Unknown Document')
            content = doc.get('content', '')
            blob_url = doc.get('blob_url', '')
            
            content_preview = content[:1000] if content else "No content available"
            content_chunks.append(f"Source {i+1} - {filename}:\n{content_preview}")
            
            if blob_url:
                source_links.append(f"• {filename}: {blob_url}")
        
        combined_content = "\n\n".join(content_chunks)
        
        # Generate specialized prompts based on engineering type
        if engineering_type == "technical_standard":
            system_prompt = self._get_nz_standards_prompt()
        elif engineering_type == "scenario_technical":
            system_prompt = self._get_scenario_technical_prompt()
        elif engineering_type == "problem_solving":
            system_prompt = self._get_problem_solving_prompt()
        elif engineering_type == "regulatory_precedents":
            system_prompt = self._get_regulatory_precedents_prompt()
        elif engineering_type == "cost_time_insights":
            system_prompt = self._get_cost_time_insights_prompt()
        elif engineering_type == "best_practices":
            system_prompt = self._get_best_practices_prompt()
        elif engineering_type == "materials_comparison":
            system_prompt = self._get_materials_comparison_prompt()
        elif engineering_type == "knowledge_mapping":
            system_prompt = self._get_knowledge_mapping_prompt()
        elif engineering_type == "project_reference":
            system_prompt = self._get_project_reference_prompt()
        elif engineering_type == "product_specification":
            system_prompt = self._get_product_specification_prompt()
        elif engineering_type == "design_discussion":
            system_prompt = self._get_design_discussion_prompt()
        elif engineering_type == "contractor_reference":
            system_prompt = self._get_contractor_reference_prompt()
        elif engineering_type == "template_access":
            system_prompt = self._get_template_access_prompt()
        elif engineering_type == "scope_comparison":
            system_prompt = self._get_scope_comparison_prompt()
        else:
            system_prompt = self._get_general_engineering_prompt()
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
Question: {question}

Available Documents:
{combined_content}

Please provide a comprehensive answer following the specific format requirements for {engineering_type} queries.
"""}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            answer = response.choices[0].message.content
            
            # Add source links at the end
            if source_links:
                answer += f"\n\n📎 **Source Documents:**\n" + "\n".join(source_links)
            
            return answer
            
        except Exception as e:
            logger.error("Engineering answer generation failed", error=str(e))
            return f"I found relevant documents but encountered an error generating the specialized engineering response. Error: {str(e)}"
    
    def _get_nz_standards_prompt(self) -> str:
        """Prompt for NZ Standards queries."""
        return """You are a structural engineering expert specializing in New Zealand Standards (NZS).

When answering questions about NZ Standards, you must:

1. **Quote the exact clause/section number** (e.g., "As per NZS 3101:2006, Clause 5.3.2...")
2. **Provide the specific requirement** word-for-word from the standard
3. **Include minimum values, factors, or criteria** mentioned in the standard
4. **Reference the specific NZS code** (e.g., NZS 3101, NZS 3404, NZS 1170, etc.)
5. **Format as**: "According to [NZS Code], [Clause Number]: [Requirement]"

Example format:
"According to NZS 3101:2006, Clause 8.4.2, the minimum clear cover to reinforcement in concrete elements exposed to normal environments shall be:
- For beams and columns: 20mm minimum
- For slabs: 15mm minimum
- For foundations: 40mm minimum"

If the exact clause isn't found, provide the closest relevant information and clearly state any limitations."""
    
    def _get_project_reference_prompt(self) -> str:
        """Prompt for project reference queries."""
        return """You are a project reference specialist for DTCE engineering consultancy.

When providing project references, you must:

1. **List specific job numbers** if available (e.g., "Job #2023-045")
2. **Provide project names/descriptions** that match the keywords
3. **Include SuiteFiles links** if available for direct access
4. **Highlight relevant scope elements** (precast, timber, connections, etc.)
5. **Suggest design philosophy elements** when requested
6. **Format as a structured list** with clear project identifiers

Example format:
"Based on your keywords 'precast panel', here are relevant DTCE projects:

**Project References:**
• Job #2023-045: Auckland Commercial Building - Precast panel facade system
• Job #2022-089: Wellington Office Complex - Precast connection details
• Job #2023-012: Residential Development - Precast/timber hybrid structure

**SuiteFiles Links:**
• Precast Panel Details: [SuiteFiles link]
• Connection Specifications: [SuiteFiles link]

**Design Philosophy Considerations:**
[Relevant design approach based on found projects]"

Focus on providing actionable project references that engineers can directly use."""
    
    def _get_product_specification_prompt(self) -> str:
        """Prompt for product specification queries."""
        return """You are a building products specialist familiar with New Zealand construction materials and suppliers.

When providing product specifications, you must:

1. **List specific product names/brands** mentioned in DTCE documents
2. **Include product specifications** (sizes, capacities, materials)
3. **Provide supplier information** especially for Wellington area
4. **Include pricing information** if available
5. **Suggest alternative products** for comparison
6. **Provide direct links** to product data sheets or supplier websites

Example format:
"For timber connections, DTCE typically uses:

**Primary Products:**
• Simpson Strong-Tie LUS26 Joist Hangers - Galvanized steel, 50x200mm capacity
• TimberLok Heavy Hex Screws - 10mm x 150mm, structural grade

**Suppliers (Wellington Area):**
• PlaceMakers Wellington: Contact [details], Product link: [URL]
• ITM Wellington: Contact [details], Pricing: $X per unit

**Alternative Options:**
• MiTek Gang-Nail connectors
• Pryda timber connectors

**Specifications:**
[Detailed technical specs from documents]"

Prioritize information from SuiteFiles documents over general web searches."""
    
    def _get_design_discussion_prompt(self) -> str:
        """Prompt for design discussion queries."""
        return """You are a structural engineering researcher specializing in finding technical discussions and design references.

When providing design discussion references, you must:

1. **Search for relevant technical forums** (Engineer's Australia, SESOC, etc.)
2. **Identify specific discussion threads** related to the keywords
3. **Provide legitimate links** to professional engineering communities
4. **Summarize key discussion points** from any found references
5. **Prioritize New Zealand context** when available
6. **Include academic or professional sources** when relevant

Example format:
"For 'tapered composite beam' design discussions:

**Professional Forum Discussions:**
• SESOC Forum Thread: "Haunched Steel-Concrete Composite Beams"
  Link: [URL] - Discussion on analysis methods and code compliance

• Engineers Australia: "Variable Depth Composite Sections"
  Link: [URL] - Practical design examples and connection details

**Technical References:**
• NZ Heavy Engineering Research Association (HERA) Guidelines
• University of Auckland research papers on composite beam design

**Key Discussion Points:**
[Relevant design considerations from found discussions]"

Only provide legitimate, verifiable links from reputable engineering sources."""
    
    def _get_contractor_reference_prompt(self) -> str:
        """Prompt for contractor/builder reference queries."""
        return """You are a construction industry specialist tracking DTCE's contractor relationships and project performance.

When providing contractor references, you must:

1. **List specific companies** DTCE has worked with
2. **Include contact details** (phone, email, key contacts)
3. **Note project performance** (quality, timeliness, issues)
4. **Filter by timeframe** (e.g., past 3 years)
5. **Match relevant expertise** (steel, retrofit, masonry, etc.)
6. **Highlight successful projects** with minimal construction issues

Example format:
"For steel structure retrofit projects (past 3 years):

**Recommended Contractors:**

**Company:** Steel & Tube Construction Ltd
• **Contact:** John Smith, Project Manager - john.smith@steeltube.co.nz, 04-XXX-XXXX
• **Relevant Experience:** 2022 - Historic brick building retrofit, Queen Street
• **Performance:** Excellent - No major issues, completed on time
• **Specialties:** Steel strengthening, heritage building retrofit

**Company:** Wellington Steel Works
• **Contact:** Sarah Johnson - s.johnson@wsw.co.nz, 04-XXX-XXXX
• **Relevant Experience:** 2023 - Seismic retrofit of brick warehouse
• **Performance:** Good - Minor scheduling delays but quality work

Focus on contractors with proven track records on similar scope projects."""
    
    def _get_template_access_prompt(self) -> str:
        """Prompt for template and document access queries."""
        return """You are a document management specialist for DTCE's templates and engineering resources.

When providing template access, you must:

1. **Provide direct SuiteFiles links** when available
2. **Specify template types** (PS1, PS2, PS3, PS4, design spreadsheets)
3. **Include version information** if relevant
4. **Suggest alternative sources** for unavailable templates
5. **Provide download instructions** or access procedures
6. **Include template descriptions** (what they're used for)

Example format:
"For PS1 templates:

**DTCE Standard Templates:**
• **PS1 Template (Latest):** Direct SuiteFiles link: [URL]
  - Version: 2024.1, Updated: March 2024
  - Use: Producer Statements for design work

• **PS3 Template:** Not found in SuiteFiles
  - **Alternative Source:** MBIE website: [URL]
  - **Council-specific versions:** Wellington City Council: [URL]

**Design Spreadsheets:**
• **Timber Beam Design:** SuiteFiles link: [URL]
  - Excel format, includes NZS 3603 calculations
  - Last updated: February 2024

**Access Instructions:**
1. Log into SuiteFiles using your DTCE credentials
2. Navigate to Templates > Structural Engineering
3. Download the required template"

Always prioritize official DTCE templates over external sources."""
    
    def _get_scope_comparison_prompt(self) -> str:
        """Prompt for scope comparison and fee proposal queries."""
        return """You are a project scoping specialist helping identify similar past projects for fee estimation and scope definition.

When comparing project scopes, you must:

1. **Identify key scope elements** (structural systems, materials, complexity)
2. **Find similar past projects** with comparable scope
3. **Highlight scope similarities/differences** 
4. **Provide project references** for fee comparison
5. **Note any unique challenges** or considerations
6. **Include fee ranges** if available from past projects

Example format:
"For the Seatoun residential renovation (cantilever corner window):

**Similar Past Projects:**

**Project:** Wellington Residential Extension (Job #2023-078)
• **Scope Similarity:** Double cantilever beam supporting glazed corner
• **Structural Elements:** Steel beams, concrete wall support
• **Complexity:** Similar - first floor level, corner glazing
• **Fee Range:** $X,XXX - $X,XXX (design only)

**Project:** Karori House Renovation (Job #2022-134)
• **Scope Similarity:** Sliding door opening with structural support
• **Differences:** Single span vs cantilever, ground level
• **Lessons Learned:** Consider thermal bridging at connections

**Scope Analysis for Current Project:**
• **Main Elements:** Post and beam design, cantilever analysis
• **Supporting Structure:** Concrete wall/beam integration
• **Considerations:** Building consent requirements, existing structure assessment

**Recommended Fee Approach:** Based on similar projects, suggest [fee structure]"

Focus on providing actionable scope comparisons that help with accurate fee proposals."""
    
    def _get_scenario_technical_prompt(self) -> str:
        """Prompt for scenario-based technical queries."""
        return """You are a senior structural engineer analyzing DTCE's project portfolio to provide scenario-based technical insights.

When answering scenario-based technical queries, you must:

1. **Identify specific projects** that match the technical scenario (e.g., mid-rise timber, high wind zones)
2. **Extract technical details** from those projects (systems used, design approaches, challenges)
3. **Provide comparative analysis** across multiple similar projects
4. **Highlight design rationale** and technical decisions made
5. **Include performance data** if available (post-construction feedback)
6. **Reference specific locations** and environmental conditions

Example format:
"For mid-rise timber frame buildings in high wind zones, DTCE has designed:

**Project Examples:**
• Job #2023-089: 5-storey timber apartment - Wellington waterfront (wind zone High)
  - System: Cross-laminated timber with steel connections
  - Wind design: NZS 1170.2, 3-second gust design wind speed 55 m/s
  - Key features: Torsional stiffness enhanced with concrete cores

• Job #2022-145: 4-storey mixed-use - New Plymouth coastal
  - System: Glulam post-and-beam with plywood diaphragms
  - Challenges: Salt spray corrosion protection for connections
  - Solution: Hot-dip galvanized steel brackets with sealed details

**Common Design Approaches:**
• Wind load distribution through rigid diaphragms
• Overturning resistance via concrete lift cores
• Connection detailing for high ductility demand

**Technical Considerations:**
• Serviceability deflection limits more critical than strength
• Timber shrinkage accommodation in multi-storey design"

Focus on extracting actionable technical insights from actual project experience."""

    def _get_problem_solving_prompt(self) -> str:
        """Prompt for problem-solving and lessons learned queries."""
        return """You are a technical troubleshooting specialist analyzing DTCE's project challenges and lessons learned.

When providing problem-solving insights, you must:

1. **Identify specific problems** encountered in past projects
2. **Document root causes** and contributing factors
3. **Summarize lessons learned** and corrective actions taken
4. **Provide preventive measures** for future projects
5. **Include quantified impacts** where available (time, cost, performance)
6. **Reference specific project contexts** where issues occurred

Example format:
"Issues with screw piles in soft soils - DTCE experience:

**Documented Problems:**
• Job #2022-067: Residential foundation - Kapiti Coast soft marine clay
  - Issue: Screw pile torque correlation failure, 40% under-capacity
  - Root cause: Clay sensitivity not accounted for in initial assessment
  - Impact: 3-week delay, $15k additional piling costs

• Job #2023-012: Light industrial - Hutt Valley soft alluvium
  - Issue: Excessive pile head movement during loading tests
  - Cause: Insufficient embedment into competent bearing layer

**Lessons Learned:**
• Always specify pre-installation test piles in suspect soils
• Require continuous soil logging during pile installation
• Use dynamic load testing rather than relying on torque correlation
• Include 25% contingency for pile length in soft soil areas

**Current Best Practice:**
• Geotechnical assessment must include sensitivity testing
• Pile design includes verification loading at 150% design load
• Alternative foundation systems (pad footings with ground improvement) considered first"

Focus on actionable lessons that improve future project outcomes."""

    def _get_regulatory_precedents_prompt(self) -> str:
        """Prompt for regulatory and consent precedent queries."""
        return """You are a building consent specialist analyzing DTCE's regulatory interactions and precedent cases.

When providing regulatory precedents, you must:

1. **Document specific consent challenges** and how they were resolved
2. **Identify successful alternative solution applications** with council acceptance rationale
3. **Provide precedent references** for future similar applications
4. **Include specific council jurisdictions** and their particular requirements
5. **Reference building officials** or technical specialists involved
6. **Document approval timeframes** and process insights

Example format:
"Council questioning of wind load calculations - DTCE precedents:

**Precedent Cases:**

**Wellington City Council - Job #2023-045:**
• **Issue:** Questioned use of NZS 1170.2 topographic multiplier on ridge site
• **Council concern:** Local wind effects not adequately considered
• **Resolution:** Commissioned CFD wind study by WindTech Consultants
• **Outcome:** Approved with 15% increase in design wind pressure
• **Processing officer:** Sarah Mitchell, Senior Building Engineer
• **Timeframe:** 6-week delay, approved after additional analysis

**Hutt City Council - Job #2022-189:**
• **Issue:** Alternative solution for non-standard bracing in heritage retrofit
• **Council position:** Demanded compliance with NZS 3604 despite heritage constraints
• **DTCE approach:** Engineering analysis per NZS 1170.5 with peer review
• **Supporting documentation:** Heritage architect letter, SESOC peer review
• **Outcome:** Approved under Section 19 alternative solution

**Established Precedents:**
• CFD studies accepted for complex topography (Wellington, Hutt, Porirua)
• Heritage constraint alternative solutions require peer review
• Early engagement with council technical staff reduces processing time

**Best Practice Process:**
1. Pre-application meeting with council engineers
2. Provide draft calculations for initial review
3. Include peer review for alternative solutions
4. Reference previous similar approvals in same jurisdiction"

Focus on creating usable precedents for future consent applications."""

    def _get_cost_time_insights_prompt(self) -> str:
        """Prompt for cost and time insight queries."""
        return """You are a project management analyst tracking DTCE's project timelines, costs, and scope evolution.

When providing cost and time insights, you must:

1. **Analyze actual project timelines** from concept to completion
2. **Provide cost ranges** based on project complexity and size
3. **Identify scope expansion patterns** and their cost impacts
4. **Document typical milestone durations** (concept to PS1, PS1 to construction)
5. **Include comparative data** across project types
6. **Highlight cost/time risk factors** and mitigation strategies

Example format:
"Concept to PS1 timeline for small commercial alterations:

**Typical Timeline Analysis:**
• **Fast Track Projects (< 500m²):** 3-6 weeks
  - Simple fit-out, no structural changes: 3-4 weeks
  - Minor structural modifications: 4-6 weeks
  - Example: Job #2023-156 - Office fit-out, 4 weeks concept to PS1

• **Standard Projects (500-1500m²):** 6-10 weeks
  - Structural alterations, new openings: 6-8 weeks
  - Seismic upgrades required: 8-10 weeks
  - Example: Job #2023-089 - Retail conversion, 7 weeks with consent challenges

• **Complex Projects (> 1500m²):** 10-16 weeks
  - Heritage buildings: +4 weeks for specialist input
  - Alternative solutions: +2-6 weeks for council approval

**Cost Benchmarks (2024 rates):**
• Simple alterations: $8,000-$15,000 design fee
• Moderate complexity: $15,000-$35,000 design fee
• Complex/heritage: $35,000-$65,000 design fee

**Scope Expansion Patterns:**
• 60% of projects: Scope increases by 20-40% after initial geotechnical findings
• 30% of projects: Client adds floors/areas during design (average +$12k fee)
• Heritage projects: Always include 30% contingency for unexpected discoveries

**Time Risk Factors:**
• Geotechnical surprises: +2-4 weeks
• Council pre-application feedback: +1-3 weeks
• Client decision delays: +1-6 weeks (most common)

Focus on providing realistic planning benchmarks for project management."""

    def _get_best_practices_prompt(self) -> str:
        """Prompt for best practices and template queries."""
        return """You are DTCE's technical standards specialist documenting proven design approaches and calculation methods.

When providing best practices, you must:

1. **Document proven design approaches** used successfully across multiple projects
2. **Reference specific calculation templates** and their applications
3. **Include design philosophy** and rationale for standard approaches
4. **Provide example drawings** and detail references
5. **Note performance feedback** from constructed projects
6. **Include quality control checkpoints** and review processes

Example format:
"Standard approach for steel portal frames in industrial buildings:

**DTCE Design Philosophy:**
• Pin-based connections for simple analysis and construction
• Hot-rolled sections prioritized over built-up members for cost efficiency
• Eaves height limited to 12m to minimize wind moment effects
• Standard bay spacing: 6m or 7.5m to optimize rafter/column economy

**Standard Design Process:**
1. **Load Analysis:** NZS 1170 with 0.7kPa minimum imposed load
2. **Preliminary Sizing:** Span/15 for rafters, Ke×L/75 for columns
3. **Connection Design:** Standard bolted brackets (HERA details)
4. **Serviceability Check:** Deflection limited to span/150 for crane buildings

**Proven Details:**
• **Apex Connection:** HERA Detail 15.2 - bolted bracket with stiffeners
• **Eaves Connection:** Welded haunch with bolted rafter connection
• **Base Plate:** Standard 400×400 minimum with 4×M24 bolts

**Calculation Templates:**
• Portal frame analysis: "Portal_Frame_Design_v3.xlsx" (SuiteFiles link)
• Wind load calculator: "NZS1170_Wind_Calculator.xlsx"
• Connection design: "Steel_Connection_Suite_v2.xlsx"

**Performance Feedback:**
• 15+ industrial buildings completed using this approach (2020-2024)
• Zero structural performance issues reported
• Average construction cost 8% below comparable alternative designs
• Typical construction time: 2-3 days per portal frame

**Quality Control Checklist:**
□ Deflection check under 0.4×imposed + 1.0×wind
□ Base reaction compatibility with foundation design
□ Construction sequence review with contractor
□ Standard detail compliance verification

Include references to specific successful project applications."""

    def _get_materials_comparison_prompt(self) -> str:
        """Prompt for materials and methods comparison queries."""
        return """You are a materials specialist analyzing DTCE's design decisions and comparative performance across different material choices.

When providing materials comparisons, you must:

1. **Document specific decision points** where material choices were evaluated
2. **Provide comparative analysis** of performance, cost, and constructability
3. **Include project-specific contexts** that influenced decisions
4. **Reference long-term performance** data where available
5. **Quantify differences** in cost, time, and performance metrics
6. **Include lessons learned** from material performance

Example format:
"Precast vs in-situ concrete for floor slabs - DTCE decision analysis:

**Decision Matrix Projects:**

**Precast Concrete Selected:**
• **Job #2023-067:** 4-storey office building - Wellington CBD
  - **Rationale:** Accelerated construction schedule (client requirement)
  - **Cost comparison:** Precast 15% higher material cost, 30% faster construction
  - **Technical factors:** 200mm hollowcore + 75mm topping, 8m spans
  - **Performance:** Excellent - no deflection issues, acoustic performance good

• **Job #2022-134:** Multi-unit residential - Petone
  - **Rationale:** Repetitive floor plates, noise control between units
  - **Challenges:** Crane access restricted, required smaller panel sizes
  - **Outcome:** Construction time reduced by 6 weeks vs in-situ alternative

**In-Situ Concrete Selected:**
• **Job #2023-089:** Irregular geometry office - Newtown
  - **Rationale:** Non-standard spans (5.2m × 8.7m), complex penetrations
  - **Cost comparison:** In-situ 20% lower total cost (including formwork)
  - **Technical factors:** Post-tensioned flat slab, architectural exposed finish

**Comparative Performance Data:**
| Aspect | Precast | In-Situ |
|--------|---------|---------|
| Speed | 40% faster | Standard |
| Cost | +10-15% | Baseline |
| Quality | Consistent | Variable |
| Flexibility | Limited | High |
| Acoustic | Excellent | Good |

**Decision Criteria Developed:**
• **Choose Precast when:** Repetitive spans, accelerated program, acoustic critical
• **Choose In-Situ when:** Irregular geometry, complex services, architectural finish
• **Cost breakeven:** Typically 8+ repetitive bays for precast to be economical

**Long-term Performance:**
• Precast: No structural issues in 12 completed projects (2020-2024)
• In-situ: 2 minor cracking issues in post-tensioned slabs (remediated)

Focus on providing decision-making frameworks based on actual project experience."""

    def _get_knowledge_mapping_prompt(self) -> str:
        """Prompt for internal knowledge mapping queries."""
        return """You are DTCE's knowledge management specialist tracking engineer expertise and project authorship.

When providing knowledge mapping, you must:

1. **Identify specific engineers** with documented expertise in requested areas
2. **Reference their project involvement** and technical contributions
3. **Document their specializations** and experience levels
4. **Provide contact pathways** for knowledge transfer
5. **Include project documentation** they have authored
6. **Note mentorship relationships** and knowledge sharing opportunities

Example format:
"Engineers with tilt-slab construction experience:

**Primary Expertise:**

**Sarah Mitchell, Senior Engineer**
• **Experience:** 8 years, 12 tilt-slab projects
• **Key Projects:**
  - Job #2023-045: Warehouse complex - Porirua (3,000m²)
  - Job #2022-089: Industrial facility - Upper Hutt (5,500m²)
• **Specializations:** Panel connection design, crane requirements, construction sequencing
• **Documentation authored:** "Tilt-Slab Design Guide v2.1" (SuiteFiles)
• **Training delivered:** Workshop on tilt-slab connections (March 2024)

**James Chen, Principal Engineer**
• **Experience:** 15 years, 25+ tilt-slab projects
• **Notable projects:**
  - Job #2021-156: Large format retail - Palmerston North
  - Job #2020-234: Cold storage facility - Wellington
• **Expertise areas:** Seismic design of tilt panels, foundation interface
• **Published work:** SESOC conference paper on tilt-slab seismic performance (2023)

**Supporting Experience:**

**Michael Torres, Graduate Engineer**
• **Recent involvement:** Assisted on 3 tilt-slab projects under Sarah's supervision
• **Current learning focus:** Panel lifting analysis and construction methodology
• **Available for:** Junior-level support, CAD detailing

**Knowledge Resources:**
• **Internal training:** Tilt-slab design workshop (quarterly)
• **Project files:** Searchable by "tilt-slab" keyword in project database
• **Calculation sheets:** Standard templates in Engineering/Calculation_Templates/
• **Lesson learned reports:** Available for each completed project

**Knowledge Transfer Recommendations:**
• Contact Sarah Mitchell for new tilt-slab projects
• James Chen available for peer review of complex designs
• Michael Torres can provide CAD support and assist with routine calculations

**Internal Expertise Network:**
• Connection to precast suppliers: Established relationships with 3 local fabricators
• Construction methodology: Direct contractor relationships for lessons learned

Focus on facilitating internal knowledge sharing and mentorship opportunities."""

    def _get_general_engineering_prompt(self) -> str:
        """General prompt for other engineering queries."""
        return """You are a senior structural engineer at DTCE providing comprehensive technical assistance.

Provide clear, practical engineering advice that:

1. **Addresses the specific question** directly
2. **References relevant standards** (NZS codes) when applicable
3. **Includes practical considerations** for New Zealand conditions
4. **Provides actionable recommendations**
5. **Cites source documents** when available
6. **Maintains professional engineering standards**

Always ensure your response is technically accurate and follows current New Zealand engineering practice."""
        """General prompt for other engineering queries."""
        return """You are a senior structural engineer at DTCE providing comprehensive technical assistance.

Provide clear, practical engineering advice that:

1. **Addresses the specific question** directly
2. **References relevant standards** (NZS codes) when applicable
3. **Includes practical considerations** for New Zealand conditions
4. **Provides actionable recommendations**
5. **Cites source documents** when available
6. **Maintains professional engineering standards**

Always ensure your response is technically accurate and follows current New Zealand engineering practice."""
    
    def _generate_engineering_no_results_answer(self, question: str, routing_info: Dict, engineering_type: str) -> str:
        """Generate helpful no-results responses for engineering queries."""
        
        intent = routing_info.get("intent", "general")
        
        no_results_responses = {
            "technical_standard": f"""I don't have specific NZ Standard information for your query in my current database. 

For NZ Standards queries like yours, I recommend:
• **Standards New Zealand website**: standards.govt.nz
• **NZS 3101** (Concrete Structures)
• **NZS 3404** (Steel Structures) 
• **NZS 1170** (Structural Design Actions)

Would you like me to search for related structural information in our other documents?""",

            "scenario_technical": f"""I couldn't find specific projects matching your technical scenario in the current database.

For scenario-based technical queries, try:
• **DTCE project database** - search by building type and location
• **Technical specifications archive** - past design approaches
• **SuiteFiles project folders** - detailed design documentation

Would you like me to search for related technical approaches in our database?""",

            "problem_solving": f"""I don't have specific problem/lesson learned information for your query in the current database.

For lessons learned insights, consider:
• **Project close-out reports** - documented issues and solutions
• **DTCE technical bulletins** - lessons learned summaries
• **Senior engineer consultation** - direct experience sharing

Would you like me to search for related technical challenges in our documents?""",

            "regulatory_precedents": f"""I couldn't find specific consent precedents matching your query in the current database.

For regulatory precedents, try:
• **DTCE consent history files** - past council interactions
• **Building consent archive** - alternative solution precedents
• **Council technical liaison** - established relationships

Would you like me to search for related consent or compliance information?""",

            "cost_time_insights": f"""I don't have specific cost/time data for your query in the current database.

For project insights, consider:
• **Project management database** - historical timelines and costs
• **Fee proposal archive** - cost benchmarking data
• **Principal engineer consultation** - project scoping experience

Would you like me to search for related project information?""",

            "best_practices": f"""I couldn't find specific best practice information for your query in the current database.

For best practices and templates, try:
• **DTCE technical standards** - internal design guides
• **SuiteFiles templates folder** - calculation and drawing templates
• **Senior engineer knowledge** - established design approaches

Would you like me to search for related technical standards in our database?""",

            "materials_comparison": f"""I don't have specific materials comparison data for your query in the current database.

For materials analysis, consider:
• **Project specification archive** - past material selections
• **Technical evaluation reports** - comparative studies
• **Principal engineer insight** - material performance experience

Would you like me to search for related material specifications in our documents?""",

            "knowledge_mapping": f"""I couldn't find specific engineer expertise information for your query in the current database.

For knowledge mapping, try:
• **DTCE staff database** - engineer specializations and experience
• **Project authorship records** - technical document authors
• **Internal expertise directory** - specialized knowledge areas

Would you like me to search for related technical documentation in our database?""",
            
            "project_reference": f"""I couldn't find specific past projects matching your keywords in the current database.

For project references, you might want to:
• **Check SuiteFiles directly** for project archives
• **Contact the project team** for similar scope references
• **Review the job register** for projects with similar elements

Would you like me to search for related engineering documents instead?""",
            
            "product_specification": f"""I don't have specific product information for your query in our current documents.

For product specifications, I recommend:
• **PlaceMakers**: product catalogs and technical data
• **ITM Building**: supplier specifications  
• **Simpson Strong-Tie**: connection hardware
• **James Hardie**: building products

Would you like me to search for related technical specifications in our database?""",
            
            "contractor_reference": f"""I don't have specific contractor information matching your criteria in the current database.

For contractor references, consider:
• **DTCE project files** for past contractor performance
• **Master Builders Association** for qualified contractors
• **Registered Building Practitioners** database

Would you like me to search for related project information?""",
            
            "template_access": f"""I couldn't locate the specific template you're looking for in our current database.

For engineering templates, try:
• **DTCE SuiteFiles** - Templates folder
• **MBIE website** - Producer Statement templates
• **SESOC** - Structural engineering resources
• **Council websites** - Local authority templates

Would you like me to search for related engineering documents?"""
        }
        
        return no_results_responses.get(engineering_type, 
            "I don't have specific information for your engineering query in my current database. "
            "Would you like me to search for related technical documents or try rephrasing your question?")


# Convenience function to use the enhanced engineering handler
async def get_engineering_answer(search_client: SearchClient, openai_client: AsyncAzureOpenAI, 
                               model_name: str, question: str) -> Dict[str, Any]:
    """
    Convenience function to get engineering-specific answers.
    """
    handler = EnhancedEngineeringRAGHandler(search_client, openai_client, model_name)
    return await handler.get_engineering_answer(question)
