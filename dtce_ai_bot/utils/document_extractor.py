"""
Enhanced document text extraction utilities with OCR support.
Handles PDF text extraction, OCR for scanned files, and various document formats.
Implements retry mechanisms and error logging as per August 4-6 work log.
"""

import os
import tempfile
import mimetypes
import asyncio
from typing import Dict, Any, Optional, List
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient
import structlog
import json
from datetime import datetime

logger = structlog.get_logger(__name__)


class EnhancedDocumentExtractor:
    """
    Enhanced document extractor with OCR and retry mechanisms.
    Implements the PDF extraction and OCR features from August 4 work log.
    """
    
    def __init__(self, form_recognizer_endpoint: str, form_recognizer_key: str):
        """Initialize the enhanced document extractor."""
        self.client = DocumentAnalysisClient(
            endpoint=form_recognizer_endpoint,
            credential=AzureKeyCredential(form_recognizer_key)
        )
        self.max_retries = 3
        self.retry_delay = 2.0
    
    async def extract_text_from_blob(self, blob_client, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract text from a blob with OCR support and retry mechanism.
        Implements the retry and error logging from August 5 work log.
        
        Args:
            blob_client: Azure blob client
            content_type: MIME type of the document
            
        Returns:
            Dictionary with extracted text, metadata, and processing info
        """
        blob_name = blob_client.blob_name
        
        for attempt in range(self.max_retries):
            try:
                logger.info("Starting text extraction", blob_name=blob_name, attempt=attempt + 1)
                
                # Download blob content
                blob_data = blob_client.download_blob().readall()
                
                # Enhanced extraction based on content type (August 4 implementation)
                if content_type and content_type.startswith('text/'):
                    result = self._extract_plain_text(blob_data, content_type)
                elif content_type and 'pdf' in content_type.lower():
                    result = await self._extract_pdf_with_ocr(blob_data, blob_name)
                elif content_type and any(doc_type in content_type.lower() for doc_type in ['word', 'docx', 'document']):
                    result = await self._extract_office_document(blob_data, blob_name)
                elif self._is_unsupported_format(blob_name, content_type):
                    # Handle known unsupported formats gracefully
                    result = self._handle_unsupported_format(blob_name, content_type)
                else:
                    # Try Form Recognizer for unknown types
                    result = await self._extract_with_form_recognizer(blob_data, blob_name)
                
                # Add processing metadata (August 5 metadata schema refinement)
                result.update({
                    'processing_timestamp': datetime.utcnow().isoformat(),
                    'extraction_attempt': attempt + 1,
                    'blob_name': blob_name,
                    'content_type': content_type or 'unknown',
                    'extraction_success': True
                })
                
                logger.info("Text extraction successful", 
                           blob_name=blob_name,
                           character_count=len(result.get('extracted_text', '')),
                           method=result.get('extraction_method', 'unknown'))
                
                return result
                
            except Exception as e:
                logger.warning("Text extraction attempt failed", 
                             blob_name=blob_name, 
                             attempt=attempt + 1, 
                             error=str(e))
                
                if attempt == self.max_retries - 1:
                    # Final attempt failed - comprehensive error logging (August 5)
                    logger.error("Text extraction failed after all retries", 
                               blob_name=blob_name, 
                               error=str(e),
                               total_attempts=self.max_retries)
                    return {
                        'extracted_text': '',
                        'character_count': 0,
                        'page_count': 0,
                        'extraction_method': 'failed',
                        'error': str(e),
                        'processing_timestamp': datetime.utcnow().isoformat(),
                        'blob_name': blob_name,
                        'final_attempt': self.max_retries,
                        'extraction_success': False
                    }
                
                # Wait before retry with exponential backoff
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return {'extracted_text': '', 'error': 'Max retries exceeded'}

    async def _extract_pdf_with_ocr(self, blob_data: bytes, blob_name: str) -> Dict[str, Any]:
        """
        Extract text from PDF with OCR support for scanned documents.
        Implements the PDF + OCR integration from August 4 work log.
        """
        try:
            logger.info("Extracting PDF with OCR support", blob_name=blob_name)
            
            # Use Form Recognizer's read model for PDFs (best for OCR)
            poller = self.client.begin_analyze_document("prebuilt-read", blob_data)
            result = poller.result()
            
            # Extract text content
            extracted_text = ""
            page_count = len(result.pages)
            
            for page in result.pages:
                for line in page.lines:
                    extracted_text += line.content + "\n"
            
            # Detect if OCR was used (confidence scores indicate OCR)
            has_ocr = any(
                hasattr(line, 'polygon') and line.polygon 
                for page in result.pages 
                for line in page.lines
            )
            
            # Extract confidence scores for OCR quality assessment
            confidence_scores = self._extract_confidence_scores(result)
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            return {
                'extracted_text': extracted_text.strip(),
                'character_count': len(extracted_text.strip()),
                'page_count': page_count,
                'extraction_method': 'pdf_ocr' if has_ocr else 'pdf_text',
                'ocr_used': has_ocr,
                'confidence_scores': confidence_scores,
                'average_confidence': avg_confidence,
                'quality_assessment': 'high' if avg_confidence > 0.9 else 'medium' if avg_confidence > 0.7 else 'low'
            }
            
        except Exception as e:
            logger.error("PDF OCR extraction failed", blob_name=blob_name, error=str(e))
            raise

    async def _extract_office_document(self, blob_data: bytes, blob_name: str) -> Dict[str, Any]:
        """Extract text from Office documents (Word, Excel, PowerPoint)."""
        try:
            logger.info("Extracting Office document", blob_name=blob_name)
            
            # Use Form Recognizer's read model for Office docs
            poller = self.client.begin_analyze_document("prebuilt-read", blob_data)
            result = poller.result()
            
            extracted_text = ""
            for page in result.pages:
                for line in page.lines:
                    extracted_text += line.content + "\n"
            
            return {
                'extracted_text': extracted_text.strip(),
                'character_count': len(extracted_text.strip()),
                'page_count': len(result.pages),
                'extraction_method': 'office_document'
            }
            
        except Exception as e:
            logger.error("Office document extraction failed", blob_name=blob_name, error=str(e))
            raise

    async def _extract_with_form_recognizer(self, blob_data: bytes, blob_name: str) -> Dict[str, Any]:
        """Extract text using Form Recognizer's general read model."""
        try:
            logger.info("Extracting with Form Recognizer", blob_name=blob_name)
            
            poller = self.client.begin_analyze_document("prebuilt-read", blob_data)
            result = poller.result()
            
            extracted_text = ""
            for page in result.pages:
                for line in page.lines:
                    extracted_text += line.content + "\n"
            
            return {
                'extracted_text': extracted_text.strip(),
                'character_count': len(extracted_text.strip()),
                'page_count': len(result.pages),
                'extraction_method': 'form_recognizer'
            }
            
        except Exception as e:
            logger.error("Form Recognizer extraction failed", blob_name=blob_name, error=str(e))
            raise

    def _extract_plain_text(self, blob_data: bytes, content_type: str) -> Dict[str, Any]:
        """Extract text from plain text files with encoding detection."""
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
                        'encoding': encoding
                    }
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail, return error
            return {
                'extracted_text': '',
                'character_count': 0,
                'page_count': 0,
                'extraction_method': 'failed',
                'error': 'Could not decode text file with any supported encoding'
            }
            
        except Exception as e:
            logger.error("Plain text extraction failed", error=str(e))
            raise

    def _extract_confidence_scores(self, result) -> List[float]:
        """Extract confidence scores from OCR results for quality assessment."""
        scores = []
        for page in result.pages:
            for line in page.lines:
                if hasattr(line, 'confidence') and line.confidence is not None:
                    scores.append(line.confidence)
        return scores

    def _is_unsupported_format(self, blob_name: str, content_type: Optional[str]) -> bool:
        """Check if file format is known to be unsupported by Form Recognizer."""
        file_extension = os.path.splitext(blob_name)[1].lower()
        unsupported_extensions = {'.msg', '.eml', '.zip', '.rar', '.exe', '.dll', '.bin'}
        
        # Check by file extension
        if file_extension in unsupported_extensions:
            return True
            
        # Check by content type
        if content_type:
            unsupported_types = {'application/vnd.ms-outlook', 'message/rfc822'}
            if content_type in unsupported_types:
                return True
                
        return False

    def _handle_unsupported_format(self, blob_name: str, content_type: Optional[str]) -> Dict[str, Any]:
        """Handle unsupported file formats gracefully."""
        file_extension = os.path.splitext(blob_name)[1].lower()
        
        # Create appropriate metadata based on file type
        if file_extension in ['.msg', '.eml']:
            extracted_text = f"Email message file: {os.path.basename(blob_name)}"
            file_type = "email"
            note = "Email files require specialized extraction tools not currently available"
        elif file_extension in ['.zip', '.rar']:
            extracted_text = f"Archive file: {os.path.basename(blob_name)}"
            file_type = "archive"
            note = "Archive files contain compressed data"
        else:
            extracted_text = f"Unsupported file format: {os.path.basename(blob_name)}"
            file_type = "unsupported"
            note = f"File format {file_extension} is not supported for text extraction"
        
        return {
            'extracted_text': extracted_text,
            'character_count': len(extracted_text),
            'page_count': 1,
            'extraction_method': 'unsupported_format_handler',
            'file_type': file_type,
            'note': note,
            'file_extension': file_extension,
            'content_type': content_type or 'unknown'
        }

    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get statistics about extraction performance (for monitoring)."""
        return {
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'supported_formats': [
                'PDF (with OCR)',
                'Word Documents', 
                'Plain Text',
                'Various image formats',
                'Excel spreadsheets',
                'PowerPoint presentations'
            ],
            'features': [
                'OCR for scanned documents',
                'Confidence scoring',
                'Retry mechanism',
                'Error logging',
                'Multiple encoding support'
            ]
        }


def get_document_extractor(form_recognizer_endpoint: str, form_recognizer_key: str) -> EnhancedDocumentExtractor:
    """
    Factory function to create a document extractor instance.
    
    Args:
        form_recognizer_endpoint: Azure Form Recognizer endpoint URL
        form_recognizer_key: Azure Form Recognizer API key
        
    Returns:
        EnhancedDocumentExtractor instance ready for use
    """
    return EnhancedDocumentExtractor(form_recognizer_endpoint, form_recognizer_key)
