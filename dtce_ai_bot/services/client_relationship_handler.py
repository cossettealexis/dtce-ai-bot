"""
Enhanced Client Relationship Handler - Specialized for people/company queries
"""

import re
from typing import Dict, List, Optional, Any
import structlog
from openai import AsyncAzureOpenAI
from azure.search.documents import SearchClient

from .smart_query_router import SmartQueryRouter
from .semantic_search_new import SemanticSearchService
from .smart_rag_handler import SmartRAGHandler

logger = structlog.get_logger(__name__)


class ClientRelationshipHandler(SmartRAGHandler):
    """
    Specialized handler for client relationship queries like:
    - "Is anyone working with Aaron from TGCS?"
    - "What projects do we have with Fletcher Building?"
    - "Contact details for John Smith at Auckland Transport"
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        super().__init__(search_client, openai_client, model_name)
        
        # Company name mappings (full name ↔ abbreviation)
        self.company_mappings = {
            # Common construction companies
            "TGCS": "The George Construction Solution",
            "The George Construction Solution": "TGCS",
            
            # Government organizations
            "NZTA": "New Zealand Transport Agency",
            "New Zealand Transport Agency": "NZTA",
            "AT": "Auckland Transport",
            "Auckland Transport": "AT",
            "WCC": "Wellington City Council", 
            "Wellington City Council": "WCC",
            "ACC": "Auckland City Council",
            "Auckland City Council": "ACC",
            
            # Major construction companies
            "FH": "Fulton Hogan",
            "Fulton Hogan": "FH",
            "HCL": "Hawkins Construction",
            "Hawkins Construction": "HCL",
            "Fletcher": "Fletcher Building",
            "Fletcher Building": "Fletcher",
            
            # Engineering consultants
            "WSP": "WSP Opus",
            "WSP Opus": "WSP",
            "AECOM": "AECOM New Zealand",
            "AECOM New Zealand": "AECOM",
            "Beca": "Beca Group",
            "Beca Group": "Beca",
            
            # Property developers
            "KBC": "Kiwi Building Company",
            "Kiwi Building Company": "KBC",
            "PDL": "Property Development Limited",
            "Property Development Limited": "PDL"
        }
        
        # Client relationship query patterns - improved
        self.relationship_patterns = {
            "person_from_company": {
                "pattern": r"([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(?:from|at)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*|[A-Z]{2,})",
                "description": "Extract person name and company (e.g., 'Aaron from TGCS')"
            },
            "working_with_person": {
                "pattern": r"working\s+with\s+([A-Za-z]+\s+[A-Za-z]+)",
                "description": "Extract person we're working with (first last name)"
            },
            "working_with_company": {
                "pattern": r"working\s+with\s+([A-Za-z]+(?:\s+[A-Za-z]+)*(?:\s+[A-Za-z]+)*|[A-Z]{2,})",
                "description": "Extract company we're working with"
            },
            "contact_at_company": {
                "pattern": r"contact\s+(?:details\s+for\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+at\s+([A-Za-z]+(?:\s+[A-Za-z]+)*|[A-Z]{2,})",
                "description": "Extract person and company for contact queries"
            },
            "projects_with_company": {
                "pattern": r"projects?\s+(?:with|for)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*|[A-Z]{2,})",
                "description": "Extract company for project queries"
            },
            "company_abbreviation": {
                "pattern": r"\b([A-Z]{2,})\b",
                "description": "Extract potential company abbreviations"
            }
        }
    
    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """Extract people, companies, and relationships from the query."""
        entities = {
            "people": [],
            "companies": [],
            "relationships": [],
            "query_type": "general"
        }
        
        query_clean = query.strip()
        
        # Pattern 1: "Aaron from TGCS" or "Aaron at TGCS"
        person_company_match = re.search(r'([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(?:from|at)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*|[A-Z]{2,})', query_clean, re.IGNORECASE)
        if person_company_match:
            person = person_company_match.group(1).strip()
            company = person_company_match.group(2).strip()
            
            entities["people"].append(person)
            entities["companies"].append(company)
            entities["relationships"].append({
                "person": person,
                "company": company,
                "type": "works_at"
            })
            entities["query_type"] = "person_company_relationship"
        
        # Pattern 2: "working with [person/company]"
        working_with_match = re.search(r'working\s+with\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)', query_clean, re.IGNORECASE)
        if working_with_match:
            entity = working_with_match.group(1).strip()
            
            # Check if it looks like a person name (2 words) or company
            if ' ' in entity and len(entity.split()) == 2 and not self._is_known_company(entity):
                entities["people"].append(entity)
                if not entities["query_type"] or entities["query_type"] == "general":
                    entities["query_type"] = "person_query"
            else:
                entities["companies"].append(entity)
                if not entities["query_type"] or entities["query_type"] == "general":
                    entities["query_type"] = "company_query"
        
        # Pattern 3: "projects with/for [company]"
        projects_match = re.search(r'projects?\s+(?:with|for)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)', query_clean, re.IGNORECASE)
        if projects_match:
            company = projects_match.group(1).strip()
            entities["companies"].append(company)
            if not entities["query_type"] or entities["query_type"] == "general":
                entities["query_type"] = "company_query"
        
        # Pattern 4: Look for company abbreviations
        abbreviations = re.findall(r'\b([A-Z]{2,})\b', query_clean)
        for abbrev in abbreviations:
            if abbrev in self.company_mappings:
                entities["companies"].append(abbrev)
                if not entities["query_type"] or entities["query_type"] == "general":
                    entities["query_type"] = "company_query"
        
        # Expand company abbreviations
        expanded_companies = []
        for company in entities["companies"]:
            expanded_companies.append(company)
            company_upper = company.upper()
            if company_upper in self.company_mappings:
                expanded = self.company_mappings[company_upper]
                if expanded != company:
                    expanded_companies.append(expanded)
            elif company in self.company_mappings:
                expanded = self.company_mappings[company]
                if expanded != company:
                    expanded_companies.append(expanded)
        
        entities["companies"] = list(set(expanded_companies))
        entities["people"] = list(set(entities["people"]))
        
        return entities
    
    def _is_known_company(self, text: str) -> bool:
        """Check if text matches a known company name or abbreviation."""
        text_upper = text.upper()
        text_title = text.title()
        
        return (text_upper in self.company_mappings or 
                text_title in self.company_mappings or
                text in self.company_mappings)
    
    def _build_enhanced_search_query(self, entities: Dict[str, Any], original_query: str) -> str:
        """Build a search query that includes all relevant terms."""
        search_terms = []
        
        # Add original query terms
        search_terms.append(original_query)
        
        # Add all people names
        for person in entities["people"]:
            search_terms.append(person)
        
        # Add all company variations
        for company in entities["companies"]:
            search_terms.append(company)
        
        # Add relationship-specific terms
        if entities["query_type"] == "person_company_relationship":
            search_terms.extend(["contact", "email", "correspondence", "project", "work"])
        elif entities["query_type"] == "company_query":
            search_terms.extend(["project", "contract", "job", "client", "work"])
        elif entities["query_type"] == "person_query":
            search_terms.extend(["contact", "email", "person", "representative"])
        
        return " ".join(search_terms)
    
    async def get_client_relationship_answer(self, user_question: str) -> Dict[str, Any]:
        """
        Enhanced answer generation for client relationship queries.
        """
        try:
            # Extract entities from the query
            entities = self._extract_entities(user_question)
            
            logger.info("Extracted entities", entities=entities, query=user_question[:100])
            
            # Get basic routing info
            routing_info = await self.query_router.route_query(user_question)
            
            # Build enhanced search query
            enhanced_query = self._build_enhanced_search_query(entities, user_question)
            
            # Search for documents with enhanced query
            documents = await self.search_service.smart_search({
                **routing_info,
                "enhanced_keywords": enhanced_query.split()
            })
            
            # Generate specialized answer
            if documents:
                answer = await self._generate_client_relationship_answer(
                    user_question, documents, entities, routing_info
                )
            else:
                answer = self._generate_no_results_answer(user_question, entities)
            
            return {
                "answer": answer,
                "sources": documents[:5],
                "entities": entities,
                "intent": routing_info.get("intent"),
                "routing_info": routing_info,
                "enhanced_query": enhanced_query
            }
            
        except Exception as e:
            logger.error("Client relationship handler failed", error=str(e), query=user_question[:100])
            
            # Fallback to basic handler
            return await super().get_smart_answer(user_question)
    
    async def _generate_client_relationship_answer(
        self, 
        user_question: str, 
        documents: List[Dict], 
        entities: Dict[str, Any],
        routing_info: Dict[str, Any]
    ) -> str:
        """Generate a specialized answer for client relationship queries."""
        
        # Build context from documents
        context_parts = []
        for i, doc in enumerate(documents[:5]):
            context_parts.append(f"Document {i+1}: {doc.get('content', 'No content')}")
        
        context = "\n\n".join(context_parts)
        
        # Create specialized prompt based on query type
        if entities["query_type"] == "person_company_relationship":
            prompt = self._build_person_company_prompt(user_question, context, entities)
        elif entities["query_type"] == "company_query":
            prompt = self._build_company_prompt(user_question, context, entities)
        elif entities["query_type"] == "person_query":
            prompt = self._build_person_prompt(user_question, context, entities)
        else:
            prompt = self._build_general_client_prompt(user_question, context, entities)
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Failed to generate client relationship answer", error=str(e))
            return f"I found some information but couldn't process it properly. Error: {str(e)}"
    
    def _build_person_company_prompt(self, question: str, context: str, entities: Dict[str, Any]) -> str:
        """Build prompt for person + company relationship queries."""
        
        people = ", ".join(entities["people"])
        companies = ", ".join(entities["companies"])
        
        return f"""You are an engineering project assistant. Answer this question about client relationships:

Question: {question}

Context from project documents and correspondence:
{context}

The user is asking about relationships between:
- People: {people}
- Companies: {companies}

Please provide a comprehensive answer that includes:
1. **Current Work Status**: Are we currently working with this person/company?
2. **Project Details**: If yes, include:
   - Project names and addresses
   - Job numbers (if mentioned)
   - Project status and timeline
3. **Contact Information**: Any contact details found
4. **Historical Work**: Past projects or correspondence
5. **Key Personnel**: Other people mentioned from the same company

Format your response professionally and include specific details like addresses and job numbers when available.

If no specific information is found, say so clearly and suggest alternative ways to find this information."""
    
    def _build_company_prompt(self, question: str, context: str, entities: Dict[str, Any]) -> str:
        """Build prompt for company-focused queries."""
        
        companies = ", ".join(entities["companies"])
        
        return f"""You are an engineering project assistant. Answer this question about company relationships:

Question: {question}

Context from project documents:
{context}

The user is asking about: {companies}

Please provide:
1. **Active Projects**: Current work with this company
   - Project names and locations
   - Job numbers and reference codes
   - Project scope and status
2. **Key Contacts**: People we work with at this company
3. **Project History**: Past collaborations
4. **Contract Details**: Any contract or agreement information

Include specific project addresses and job numbers when available."""
    
    def _build_person_prompt(self, question: str, context: str, entities: Dict[str, Any]) -> str:
        """Build prompt for person-focused queries."""
        
        people = ", ".join(entities["people"])
        
        return f"""You are an engineering project assistant. Answer this question about personnel:

Question: {question}

Context from documents:
{context}

The user is asking about: {people}

Please provide:
1. **Contact Details**: Email, phone, or other contact information
2. **Company Affiliation**: Which company this person works for
3. **Current Projects**: What projects they're involved in
4. **Role and Responsibilities**: Their role on projects
5. **Communication History**: Recent correspondence or meetings

Be specific about project names, addresses, and job numbers when available."""
    
    def _build_general_client_prompt(self, question: str, context: str, entities: Dict[str, Any]) -> str:
        """Build prompt for general client queries."""
        
        return f"""You are an engineering project assistant. Answer this client relationship question:

Question: {question}

Context from documents:
{context}

Provide a helpful answer including:
- Relevant project information
- Contact details if available
- Job numbers and project addresses
- Current status and next steps

Be specific and professional in your response."""
    
    def _generate_no_results_answer(self, user_question: str, entities: Dict[str, Any]) -> str:
        """Generate answer when no documents are found."""
        
        people = entities.get("people", [])
        companies = entities.get("companies", [])
        
        response_parts = ["I couldn't find specific information about this query in our documents."]
        
        if people:
            response_parts.append(f"\n**People mentioned**: {', '.join(people)}")
        
        if companies:
            response_parts.append(f"\n**Companies mentioned**: {', '.join(companies)}")
            
            # Suggest expanded company names if abbreviations were used
            expanded_companies = []
            for company in companies:
                if company.upper() in self.company_mappings:
                    expanded = self.company_mappings[company.upper()]
                    if expanded != company:
                        expanded_companies.append(f"{company} (possibly {expanded})")
            
            if expanded_companies:
                response_parts.append(f"\n**Note**: {', '.join(expanded_companies)}")
        
        response_parts.append(f"\n\n**Suggestions**:")
        response_parts.append(f"- Check if the company name or abbreviation is spelled correctly")
        response_parts.append(f"- Try searching for project names or locations instead")
        response_parts.append(f"- Look for correspondence or emails with this person/company")
        response_parts.append(f"- Check recent project files and contact lists")
        
        return "".join(response_parts)
