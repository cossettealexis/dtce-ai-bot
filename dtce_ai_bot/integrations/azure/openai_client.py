import asyncio
from typing import List, Optional
from openai import AzureOpenAI
import structlog
from datetime import datetime

from config import settings
from src.models import SearchResponse

logger = structlog.get_logger(__name__)


class AzureOpenAIClient:
    """Client for interacting with Azure OpenAI service."""
    
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        self.deployment_name = settings.azure_openai_deployment_name
    
    async def generate_search_summary(self, search_response: SearchResponse) -> str:
        """Generate an AI summary of search results."""
        
        if not search_response.results:
            return "No documents found matching your query."
        
        # Prepare context from search results
        context_parts = []
        for i, result in enumerate(search_response.results[:10], 1):  # Limit to top 10 results
            doc = result.document
            
            context_part = f"""
Document {i}:
- File: {doc.file_name}
- Project: {doc.project_id or 'N/A'}
- Type: {doc.document_type.value}
- Modified: {doc.modified_date.strftime('%Y-%m-%d') if doc.modified_date else 'Unknown'}
- Content Preview: {doc.content_preview[:200] if doc.content_preview else 'No preview available'}...
"""
            context_parts.append(context_part)
        
        context = "\n".join(context_parts)
        
        # Create prompt for GPT
        prompt = f"""
You are an AI assistant helping DTCE engineers find information from their project files. 
Based on the search results below, provide a helpful summary that answers the user's query: "{search_response.query}"

Search Results:
{context}

Please provide a concise, informative summary that:
1. Directly answers the user's question
2. Highlights the most relevant documents found
3. Mentions key project numbers, dates, and document types
4. Suggests any patterns or insights from the results
5. Keeps the response professional and engineering-focused

Summary:"""

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant for DTCE engineers searching their project documentation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info("Generated AI summary", query=search_response.query, summary_length=len(summary))
            return summary
            
        except Exception as e:
            logger.error("Failed to generate AI summary", error=str(e))
            return f"Found {len(search_response.results)} documents matching your query, but AI summary is currently unavailable."
    
    async def extract_document_insights(self, document_text: str, file_name: str) -> dict:
        """Extract insights and metadata from document text."""
        
        if not document_text or len(document_text.strip()) < 50:
            return {}
        
        # Limit text to avoid token limits
        text_preview = document_text[:3000] if len(document_text) > 3000 else document_text
        
        prompt = f"""
Analyze the following DTCE engineering document and extract key information:

Document: {file_name}
Content: {text_preview}

Please extract and return the following information in JSON format:
{{
    "project_title": "Brief project title if identifiable",
    "client_name": "Client organization name if mentioned",
    "key_topics": ["list", "of", "main", "topics", "or", "keywords"],
    "document_summary": "One sentence summary of what this document contains",
    "project_type": "Type of engineering work (bridge, building, seismic, etc.)",
    "important_dates": ["any important dates mentioned"],
    "budget_info": "Any budget or cost information mentioned"
}}

Only include fields where you found clear information. Return "null" for fields where information is not available or unclear.
"""

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that extracts structured information from engineering documents. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.1
            )
            
            # Parse the JSON response
            import json
            insights_text = response.choices[0].message.content.strip()
            
            # Clean up the response to ensure it's valid JSON
            if insights_text.startswith("```json"):
                insights_text = insights_text[7:]
            if insights_text.endswith("```"):
                insights_text = insights_text[:-3]
            
            insights = json.loads(insights_text)
            logger.info("Extracted document insights", file_name=file_name)
            return insights
            
        except Exception as e:
            logger.error("Failed to extract document insights", file_name=file_name, error=str(e))
            return {}
    
    async def answer_engineering_question(self, question: str, context_documents: List[dict]) -> str:
        """Answer a specific engineering question using context from documents."""
        
        if not context_documents:
            return "I don't have enough context from the documents to answer your question."
        
        # Prepare context
        context_parts = []
        for doc in context_documents[:5]:  # Limit context
            context_parts.append(f"""
Document: {doc.get('file_name', 'Unknown')}
Project: {doc.get('project_id', 'N/A')}
Content: {doc.get('content_preview', 'No content available')[:300]}...
""")
        
        context = "\n".join(context_parts)
        
        prompt = f"""
You are an AI assistant helping DTCE engineers with their project documentation.

Question: {question}

Available Context from Documents:
{context}

Please provide a helpful answer based on the available documents. If the documents don't contain enough information to fully answer the question, say so and suggest what type of documents might contain the answer.

Keep your response professional, engineering-focused, and cite specific documents when possible.

Answer:"""

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are a knowledgeable AI assistant for DTCE engineers. Provide accurate, helpful responses based on the available documentation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.3
            )
            
            answer = response.choices[0].message.content.strip()
            logger.info("Generated engineering answer", question=question)
            return answer
            
        except Exception as e:
            logger.error("Failed to generate engineering answer", error=str(e))
            return "I'm unable to process your question at the moment. Please try again later."
    
    async def generate_project_summary(self, project_documents: List[dict]) -> str:
        """Generate a comprehensive summary of a project based on its documents."""
        
        if not project_documents:
            return "No documents found for this project."
        
        # Organize documents by type
        doc_types = {}
        for doc in project_documents:
            doc_type = doc.get('document_type', 'Other')
            if doc_type not in doc_types:
                doc_types[doc_type] = []
            doc_types[doc_type].append(doc)
        
        # Create context organized by document type
        context_parts = []
        for doc_type, docs in doc_types.items():
            context_parts.append(f"\n{doc_type}:")
            for doc in docs[:3]:  # Limit to 3 docs per type
                context_parts.append(f"  - {doc.get('file_name', 'Unknown')}: {doc.get('content_preview', '')[:150]}...")
        
        context = "\n".join(context_parts)
        
        prompt = f"""
Create a comprehensive project summary based on the available DTCE project documents:

Project Documents by Type:
{context}

Please provide a structured summary that includes:
1. Project Overview (what type of project this appears to be)
2. Key Documents Available (organized by type)
3. Project Status (based on available documentation)
4. Key Findings or Notable Information
5. Any Gaps in Documentation

Keep the summary professional and focused on information that would be useful for DTCE engineers.

Project Summary:"""

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are an AI assistant creating project summaries for DTCE engineers. Provide structured, informative summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info("Generated project summary", doc_count=len(project_documents))
            return summary
            
        except Exception as e:
            logger.error("Failed to generate project summary", error=str(e))
            return f"Project contains {len(project_documents)} documents across {len(doc_types)} categories, but detailed summary is currently unavailable."
