"""
Document text extraction utilities using Azure Form Recognizer.
Handles various document formats (PDF, DOCX, TXT, etc.)
"""

import os
import tempfile
import mimetypes
from typing import Dict, Any, Optional
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient
import structlog

logger = structlog.get_logger(__name__)


class DocumentExtractor:
    """Handles text extraction from various document formats."""
    
    def __init__(self, form_recognizer_endpoint: str, form_recognizer_key: str):
        """Initialize the document extractor."""
        self.client = DocumentAnalysisClient(
            endpoint=form_recognizer_endpoint,
            credential=AzureKeyCredential(form_recognizer_key)
        )
    
    async def extract_text_from_blob(self, blob_client, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract text from a blob using Azure Form Recognizer.
        
        Args:
            blob_client: Azure blob client
            content_type: MIME type of the document
            
        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            # Download blob content
            blob_data = blob_client.download_blob().readall()
            
            # Determine extraction method based on content type
            if content_type and content_type.startswith('text/'):
                # Handle plain text files directly
                return self._extract_plain_text(blob_data, content_type)
            else:
                # Use Form Recognizer for complex documents
                return await self._extract_with_form_recognizer(blob_data)
                
        except Exception as e:
            logger.error("Text extraction failed", error=str(e), blob_name=blob_client.blob_name)
            return {
                "extracted_text": "",
                "page_count": 0,
                "error": str(e),
                "extraction_method": "failed"
            }
    
    def _extract_plain_text(self, blob_data: bytes, content_type: str) -> Dict[str, Any]:
        """Extract text from plain text files."""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    text = blob_data.decode(encoding)
                    return {
                        "extracted_text": text,
                        "page_count": 1,
                        "extraction_method": "direct_text",
                        "encoding": encoding,
                        "character_count": len(text)
                    }
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail, use errors='ignore'
            text = blob_data.decode('utf-8', errors='ignore')
            return {
                "extracted_text": text,
                "page_count": 1,
                "extraction_method": "direct_text_fallback",
                "character_count": len(text)
            }
            
        except Exception as e:
            logger.error("Plain text extraction failed", error=str(e))
            return {
                "extracted_text": "",
                "page_count": 0,
                "error": str(e),
                "extraction_method": "plain_text_failed"
            }
    
    async def _extract_with_form_recognizer(self, blob_data: bytes) -> Dict[str, Any]:
        """Extract text using Azure Form Recognizer."""
        temp_file_path = None
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(blob_data)
                temp_file_path = temp_file.name
            
            # Analyze document with Form Recognizer
            with open(temp_file_path, "rb") as document:
                poller = self.client.begin_analyze_document("prebuilt-read", document)
                result = poller.result()
            
            # Extract text content
            extracted_text = ""
            for page in result.pages:
                for line in page.lines:
                    extracted_text += line.content + "\n"
            
            # Extract additional metadata
            tables_count = len(result.tables) if result.tables else 0
            
            return {
                "extracted_text": extracted_text.strip(),
                "page_count": len(result.pages),
                "tables_count": tables_count,
                "extraction_method": "form_recognizer",
                "character_count": len(extracted_text),
                "confidence_scores": [page.angle for page in result.pages] if result.pages else []
            }
            
        except Exception as e:
            logger.error("Form Recognizer extraction failed", error=str(e))
            return {
                "extracted_text": "",
                "page_count": 0,
                "error": str(e),
                "extraction_method": "form_recognizer_failed"
            }
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning("Failed to cleanup temp file", error=str(e))


def get_document_extractor(form_recognizer_endpoint: str, form_recognizer_key: str) -> DocumentExtractor:
    """Factory function to create a document extractor."""
    return DocumentExtractor(form_recognizer_endpoint, form_recognizer_key)
