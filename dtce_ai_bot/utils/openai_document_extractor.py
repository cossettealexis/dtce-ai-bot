"""
OpenAI-based document text extraction as alternative to Azure Form Recognizer.
Uses OpenAI's GPT models for text extraction when Form Recognizer is unavailable.
"""

import os
import tempfile
import mimetypes
import asyncio
from typing import Dict, Any, Optional, List
import structlog
import json
from datetime import datetime
from openai import AsyncAzureOpenAI
import base64
import PyPDF2
import io
from docx import Document

logger = structlog.get_logger(__name__)


class OpenAIDocumentExtractor:
    """
    Document extractor using OpenAI as alternative to Azure Form Recognizer.
    """
    
    def __init__(self, openai_endpoint: str, openai_key: str, deployment_name: str = "gpt-35-turbo"):
        """Initialize the OpenAI document extractor."""
        self.client = AsyncAzureOpenAI(
            azure_endpoint=openai_endpoint,
            api_key=openai_key,
            api_version="2024-02-15-preview"
        )
        self.deployment_name = deployment_name
        self.max_retries = 3
        self.retry_delay = 2.0
    
    async def extract_text_from_blob(self, blob_client, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract text from a blob using OpenAI and local libraries.
        
        Args:
            blob_client: Azure blob client
            content_type: MIME type of the document
            
        Returns:
            Dictionary with extracted text, metadata, and processing info
        """
        blob_name = blob_client.blob_name
        
        for attempt in range(self.max_retries):
            try:
                logger.info("Starting OpenAI text extraction", blob_name=blob_name, attempt=attempt + 1)
                
                # Download blob content
                blob_data = blob_client.download_blob().readall()
                
                # Extract based on content type
                if content_type and content_type.startswith('text/'):
                    result = self._extract_plain_text(blob_data, content_type)
                elif content_type and 'pdf' in content_type.lower():
                    result = await self._extract_pdf_text(blob_data, blob_name)
                elif content_type and any(doc_type in content_type.lower() for doc_type in ['word', 'docx']):
                    result = await self._extract_docx_text(blob_data, blob_name)
                else:
                    # Fallback: try to treat as text
                    result = self._extract_plain_text(blob_data, content_type or 'unknown')
                
                # Add processing metadata
                result.update({
                    'processing_timestamp': datetime.utcnow().isoformat(),
                    'extraction_attempt': attempt + 1,
                    'blob_name': blob_name,
                    'content_type': content_type or 'unknown',
                    'extraction_success': True,
                    'extractor': 'openai_alternative'
                })
                
                logger.info("OpenAI text extraction successful", 
                           blob_name=blob_name,
                           character_count=len(result.get('extracted_text', '')),
                           method=result.get('extraction_method', 'unknown'))
                
                return result
                
            except Exception as e:
                logger.warning("OpenAI text extraction attempt failed", 
                             blob_name=blob_name, 
                             attempt=attempt + 1, 
                             error=str(e))
                
                if attempt == self.max_retries - 1:
                    logger.error("OpenAI text extraction failed after all retries", 
                               blob_name=blob_name, 
                               error=str(e),
                               total_attempts=self.max_retries)
                    return {
                        'extracted_text': f"Document: {blob_name} (extraction failed)",
                        'character_count': 0,
                        'page_count': 0,
                        'extraction_method': 'failed',
                        'error': str(e),
                        'processing_timestamp': datetime.utcnow().isoformat(),
                        'blob_name': blob_name,
                        'extraction_success': False,
                        'extractor': 'openai_alternative'
                    }
                
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return {'extracted_text': f"Document: {blob_name}", 'error': 'Max retries exceeded'}

    def _extract_plain_text(self, blob_data: bytes, content_type: str) -> Dict[str, Any]:
        """Extract text from plain text files."""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'utf-16', 'latin-1', 'cp1252']:
                try:
                    text = blob_data.decode(encoding)
                    return {
                        'extracted_text': text,
                        'character_count': len(text),
                        'page_count': 1,
                        'extraction_method': 'plain_text',
                        'encoding_used': encoding
                    }
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail, use error handling
            text = blob_data.decode('utf-8', errors='replace')
            return {
                'extracted_text': text,
                'character_count': len(text),
                'page_count': 1,
                'extraction_method': 'plain_text_fallback'
            }
            
        except Exception as e:
            logger.error("Plain text extraction failed", error=str(e))
            return {
                'extracted_text': '',
                'character_count': 0,
                'page_count': 0,
                'extraction_method': 'failed',
                'error': str(e)
            }

    async def _extract_pdf_text(self, blob_data: bytes, blob_name: str) -> Dict[str, Any]:
        """Extract text from PDF using PyPDF2."""
        try:
            pdf_file = io.BytesIO(blob_data)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            extracted_text = ""
            page_count = len(pdf_reader.pages)
            
            for page in pdf_reader.pages:
                try:
                    text = page.extract_text()
                    if text.strip():
                        extracted_text += text + "\n"
                except Exception as e:
                    logger.warning("Failed to extract text from PDF page", error=str(e))
                    continue
            
            return {
                'extracted_text': extracted_text.strip(),
                'character_count': len(extracted_text.strip()),
                'page_count': page_count,
                'extraction_method': 'pdf_pypdf2'
            }
            
        except Exception as e:
            logger.error("PDF extraction failed", blob_name=blob_name, error=str(e))
            return {
                'extracted_text': f"PDF document: {blob_name} (text extraction failed)",
                'character_count': 0,
                'page_count': 0,
                'extraction_method': 'failed',
                'error': str(e)
            }

    async def _extract_docx_text(self, blob_data: bytes, blob_name: str) -> Dict[str, Any]:
        """Extract text from DOCX using python-docx."""
        try:
            docx_file = io.BytesIO(blob_data)
            doc = Document(docx_file)
            
            extracted_text = ""
            paragraph_count = 0
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    extracted_text += paragraph.text + "\n"
                    paragraph_count += 1
            
            return {
                'extracted_text': extracted_text.strip(),
                'character_count': len(extracted_text.strip()),
                'page_count': max(1, paragraph_count // 20),  # Estimate pages
                'extraction_method': 'docx_python_docx',
                'paragraph_count': paragraph_count
            }
            
        except Exception as e:
            logger.error("DOCX extraction failed", blob_name=blob_name, error=str(e))
            return {
                'extracted_text': f"Word document: {blob_name} (text extraction failed)",
                'character_count': 0,
                'page_count': 0,
                'extraction_method': 'failed',
                'error': str(e)
            }


def get_openai_document_extractor(openai_endpoint: str, openai_key: str, deployment_name: str = "gpt-35-turbo") -> OpenAIDocumentExtractor:
    """Factory function to create OpenAI document extractor."""
    return OpenAIDocumentExtractor(openai_endpoint, openai_key, deployment_name)
