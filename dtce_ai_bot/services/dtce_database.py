"""
Contact extraction service for finding builder/client contact details from SuiteFiles documents.
"""

import asyncio
import re
from typing import List, Dict, Optional
import structlog
from azure.search.documents import SearchClient

logger = structlog.get_logger(__name__)

class ContactExtractionService:
    """Service for extracting contact information from existing SuiteFiles documents."""
    
    def __init__(self, search_client: SearchClient):
        """Initialize with the existing search client to access SuiteFiles documents."""
        self.search_client = search_client
        
    async def search_builder_contacts(self, criteria: Dict[str, any]) -> List[Dict]:
        """
        Search SuiteFiles documents for builder contact information.
        
        Args:
            criteria: Search criteria like project_type, location, etc.
            
        Returns:
            List of builder contact information extracted from documents
        """
        try:
            # Search for documents containing builder/contractor information
            search_terms = ["contractor", "builder", "construction company", "main contractor", "subcontractor"]
            
            if criteria.get('location'):
                search_terms.append(criteria['location'])
            if criteria.get('project_type'):
                search_terms.append(criteria['project_type'])
                
            search_query = " ".join(search_terms)
            
            results = self.search_client.search(
                search_text=search_query,
                top=30,
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                query_type="semantic",
                semantic_configuration_name="default"
            )
            
            builder_contacts = []
            for result in results:
                doc_dict = dict(result)
                content = doc_dict.get('content', '')
                
                # Extract contact information from document content
                contacts = self._extract_contacts_from_content(content, 'builder')
                
                for contact in contacts:
                    contact['source_document'] = doc_dict.get('filename', 'Unknown')
                    contact['project_id'] = doc_dict.get('project_name', 'Unknown')
                    contact['document_url'] = doc_dict.get('blob_url', '')
                    builder_contacts.append(contact)
            
            logger.info("Builder contact search completed", 
                       criteria=criteria, 
                       results_count=len(builder_contacts))
            
            return builder_contacts
            
        except Exception as e:
            logger.error("Builder contact search failed", error=str(e), criteria=criteria)
            return []
    
    async def search_client_contacts(self, criteria: Dict[str, any]) -> List[Dict]:
        """
        Search SuiteFiles documents for client contact information.
        
        Args:
            criteria: Search criteria like project_type, location, etc.
            
        Returns:
            List of client contact information extracted from documents
        """
        try:
            # Search for documents containing client information
            search_terms = ["client", "architect", "developer", "owner", "contact"]
            
            if criteria.get('location'):
                search_terms.append(criteria['location'])
                
            search_query = " ".join(search_terms)
            
            results = self.search_client.search(
                search_text=search_query,
                top=30,
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                query_type="semantic",
                semantic_configuration_name="default"
            )
            
            client_contacts = []
            for result in results:
                doc_dict = dict(result)
                content = doc_dict.get('content', '')
                
                # Extract contact information from document content
                contacts = self._extract_contacts_from_content(content, 'client')
                
                for contact in contacts:
                    contact['source_document'] = doc_dict.get('filename', 'Unknown')
                    contact['project_id'] = doc_dict.get('project_name', 'Unknown')
                    contact['document_url'] = doc_dict.get('blob_url', '')
                    client_contacts.append(contact)
            
            logger.info("Client contact search completed", 
                       criteria=criteria, 
                       results_count=len(client_contacts))
            
            return client_contacts
            
        except Exception as e:
            logger.error("Client contact search failed", error=str(e), criteria=criteria)
            return []
    
    def _extract_contacts_from_content(self, content: str, contact_type: str) -> List[Dict]:
        """
        Extract contact information from document content using regex patterns.
        
        Args:
            content: Document content to search
            contact_type: 'builder' or 'client'
            
        Returns:
            List of extracted contact information
        """
        contacts = []
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Phone pattern (NZ format)
        phone_pattern = r'(?:\+64|0)[2-9]\d{7,9}'
        
        # Company/person name patterns
        if contact_type == 'builder':
            name_patterns = [
                r'([A-Z][A-Za-z\s&\.]+(?:Construction|Building|Contractors?|Builders?)[\s\w]*)',
                r'(?:contractor|builder|construction)\s*[:\-]?\s*([A-Z][A-Za-z\s&\.]+)',
                r'([A-Z][A-Za-z\s&\.]+(?:Ltd|Limited|Inc|Corporation))'
            ]
        else:  # client
            name_patterns = [
                r'([A-Z][A-Za-z\s&\.]+(?:Architecture|Architects|Design|Studio)[\s\w]*)',
                r'(?:client|architect|developer)\s*[:\-]?\s*([A-Z][A-Za-z\s&\.]+)',
                r'([A-Z][A-Za-z\s&\.]+(?:Ltd|Limited|Inc|Corporation))'
            ]
        
        # Find all emails and phones in the content
        emails = re.findall(email_pattern, content)
        phones = re.findall(phone_pattern, content)
        
        # Find company/person names
        for pattern in name_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                name = match.strip()
                if len(name) > 3:  # Filter out very short matches
                    
                    # Look for contact info near this name
                    name_index = content.find(name)
                    if name_index != -1:
                        context_start = max(0, name_index - 200)
                        context_end = min(len(content), name_index + len(name) + 200)
                        context = content[context_start:context_end]
                        
                        # Find emails and phones in the context
                        context_emails = re.findall(email_pattern, context)
                        context_phones = re.findall(phone_pattern, context)
                        
                        contacts.append({
                            'name': name,
                            'type': contact_type,
                            'emails': context_emails,
                            'phones': context_phones,
                            'all_emails_in_doc': emails,
                            'all_phones_in_doc': phones
                        })
        
        return contacts
