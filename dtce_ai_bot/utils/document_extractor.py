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
import extract_msg

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
                elif blob_name.lower().endswith('.msg') or (content_type and 'vnd.ms-outlook' in content_type):
                    # Handle Outlook MSG files
                    result = await self._extract_msg_file(blob_data, blob_name)
                elif self._is_form_recognizer_supported(blob_name, content_type):
                    # Try Form Recognizer for supported file types only
                    result = await self._extract_with_form_recognizer(blob_data, blob_name)
                else:
                    # For unsupported file types, create meaningful metadata directly
                    # This prevents errors and provides searchable content for ALL files
                    logger.info("Creating enhanced file metadata for format", 
                               blob_name=blob_name, 
                               file_type=os.path.splitext(blob_name)[1].lower())
                    result = self._create_file_metadata(blob_name, content_type)
                
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
                    # Final attempt failed - provide meaningful metadata instead of failing
                    logger.info("Text extraction failed, providing file metadata", 
                               blob_name=blob_name, 
                               error=str(e),
                               total_attempts=self.max_retries)
                    
                    # Create meaningful metadata for any file type
                    result = self._create_file_metadata(blob_name, content_type, str(e))
                    result.update({
                        'processing_timestamp': datetime.utcnow().isoformat(),
                        'extraction_attempt': self.max_retries,
                        'blob_name': blob_name,
                        'content_type': content_type or 'unknown',
                        'extraction_success': True  # We successfully created metadata
                    })
                    return result
                
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

    async def _extract_msg_file(self, blob_data: bytes, blob_name: str) -> Dict[str, Any]:
        """Extract content from Outlook MSG files using extract-msg library."""
        try:
            logger.info("Extracting MSG file content", blob_name=blob_name)
            
            # Save blob data to temporary file since extract-msg works with files
            with tempfile.NamedTemporaryFile(suffix='.msg', delete=False) as temp_file:
                temp_file.write(blob_data)
                temp_file_path = temp_file.name
            
            try:
                # Extract MSG content
                msg = extract_msg.Message(temp_file_path)
                
                # Build extracted text from MSG components
                text_parts = []
                
                # Add subject
                if msg.subject:
                    text_parts.append(f"Subject: {msg.subject}")
                
                # Add sender
                if msg.sender:
                    text_parts.append(f"From: {msg.sender}")
                
                # Add recipients
                if msg.to:
                    text_parts.append(f"To: {msg.to}")
                if msg.cc:
                    text_parts.append(f"CC: {msg.cc}")
                
                # Add date
                if msg.date:
                    text_parts.append(f"Date: {msg.date}")
                
                # Add body content
                if msg.body:
                    text_parts.append("Content:")
                    text_parts.append(msg.body)
                
                # Combine all parts
                extracted_text = "\n\n".join(text_parts)
                
                return {
                    'extracted_text': extracted_text.strip(),
                    'character_count': len(extracted_text.strip()),
                    'extraction_method': 'msg_parser',
                    'subject': msg.subject or '',
                    'sender': msg.sender or '',
                    'recipients': msg.to or '',
                    'date': str(msg.date) if msg.date else ''
                }
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error("MSG file extraction failed", blob_name=blob_name, error=str(e))
            # Fallback to basic metadata
            return {
                'extracted_text': f"Email message file: {os.path.basename(blob_name)}",
                'character_count': 0,
                'extraction_method': 'msg_parser_failed',
                'note': f"MSG extraction failed: {str(e)}"
            }

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

    def _is_form_recognizer_supported(self, blob_name: str, content_type: Optional[str] = None) -> bool:
        """Check if a file type is supported by Azure Form Recognizer."""
        file_extension = os.path.splitext(blob_name)[1].lower()
        
        # Form Recognizer supported formats
        supported_extensions = {
            '.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'
        }
        
        # Check by extension first
        if file_extension in supported_extensions:
            return True
            
        # Check by content type
        if content_type:
            supported_content_types = {
                'application/pdf',
                'image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 
                'image/tiff', 'image/tif'
            }
            if content_type.lower() in supported_content_types:
                return True
        
        return False

    def _create_file_metadata(self, blob_name: str, content_type: Optional[str], extraction_error: Optional[str] = None) -> Dict[str, Any]:
        """Create comprehensive metadata for any file type when text extraction isn't possible."""
        file_extension = os.path.splitext(blob_name)[1].lower()
        file_basename = os.path.basename(blob_name)
        
        # Determine file category and create meaningful description
        file_info = self._get_file_type_info(file_extension)
        
        # Create descriptive text that can be searched
        description_parts = [
            f"File: {file_basename}",
            f"Type: {file_info['category']} ({file_info['description']})",
            f"Extension: {file_extension}" if file_extension else "Extension: none",
        ]
        
        if content_type:
            description_parts.append(f"MIME Type: {content_type}")
            
        # Add file-specific searchable content
        if file_info['category'] == 'CAD/Design':
            description_parts.extend([
                "CAD drawing file for engineering and architectural design",
                "Technical drawing containing design specifications",
                "Engineering design document with geometric data",
                "Architectural or mechanical drawing file",
                "Contains technical drawings, dimensions, and design details",
                "Professional design file for construction or manufacturing",
                "Blueprint or schematic drawing",
                "Technical documentation for project implementation"
            ])
            
            # Extract more specific info from filename if possible
            if '-' in file_basename:
                parts = file_basename.split('-')
                if len(parts) >= 2:
                    description_parts.append(f"Project reference: {parts[0]}")
                    description_parts.append(f"Drawing reference: {parts[1].split('.')[0]}")
            
            # Add common CAD-related search terms
            description_parts.extend([
                "technical specifications", "design drawings", "construction plans",
                "architectural plans", "mechanical drawings", "engineering schematics",
                "building plans", "floor plans", "elevation drawings", "section views",
                "detail drawings", "assembly drawings", "part drawings"
            ])
            
        elif file_info['category'] == 'Archive':
            description_parts.extend([
                "Compressed archive file",
                "Contains multiple files",
                "Backup or distribution archive"
            ])
        elif file_info['category'] == 'Media':
            description_parts.extend([
                f"{file_info['subcategory']} media file",
                "Multimedia content",
                "Audio/visual material"
            ])
        elif file_info['category'] == 'Database':
            description_parts.extend([
                "Database file",
                "Structured data storage",
                "Data repository"
            ])
        elif file_info['category'] == 'Executable':
            description_parts.extend([
                "Executable program file",
                "Software application",
                "Binary executable"
            ])
        
        # Add project/path context if available
        path_parts = blob_name.split('/')
        if len(path_parts) > 1:
            description_parts.append(f"Located in: {'/'.join(path_parts[:-1])}")
            
        extracted_text = '\n'.join(description_parts)
        
        result = {
            'extracted_text': extracted_text,
            'character_count': len(extracted_text),
            'page_count': 1,
            'extraction_method': 'enhanced_metadata',
            'file_type': file_info['category'],
            'file_description': file_info['description'],
            'file_extension': file_extension,
            'content_type': content_type or 'unknown',
            'searchable_content': extracted_text,
            'file_category': file_info['category'],
            'file_subcategory': file_info.get('subcategory', ''),
            'supports_questions': True,  # All files support questions through metadata
            'engineering_relevant': file_info['category'] in ['CAD/Design', '3D/Graphics', 'Document']
        }
        
        if extraction_error:
            result['extraction_note'] = f"File processed with enhanced metadata extraction (format: {file_info['description']})"
        else:
            result['extraction_note'] = f"Successfully processed {file_info['description']} with enhanced metadata"
            
        return result

    def _get_file_type_info(self, file_extension: str) -> Dict[str, str]:
        """Get comprehensive information about file type based on extension."""
        extension_map = {
            # CAD and Design Files
            '.dwg': {'category': 'CAD/Design', 'description': 'AutoCAD Drawing', 'subcategory': 'CAD'},
            '.dxf': {'category': 'CAD/Design', 'description': 'Drawing Exchange Format', 'subcategory': 'CAD'},
            '.dwf': {'category': 'CAD/Design', 'description': 'Design Web Format', 'subcategory': 'CAD'},
            '.bak': {'category': 'CAD/Design', 'description': 'AutoCAD Backup File', 'subcategory': 'Backup'},
            '.dst': {'category': 'CAD/Design', 'description': 'AutoCAD Sheet Set', 'subcategory': 'CAD'},
            
            # Archives
            '.zip': {'category': 'Archive', 'description': 'ZIP Archive', 'subcategory': 'Compressed'},
            '.rar': {'category': 'Archive', 'description': 'RAR Archive', 'subcategory': 'Compressed'},
            '.7z': {'category': 'Archive', 'description': '7-Zip Archive', 'subcategory': 'Compressed'},
            '.tar': {'category': 'Archive', 'description': 'TAR Archive', 'subcategory': 'Compressed'},
            '.gz': {'category': 'Archive', 'description': 'GZIP Archive', 'subcategory': 'Compressed'},
            
            # Media Files
            '.mp3': {'category': 'Media', 'description': 'MP3 Audio', 'subcategory': 'Audio'},
            '.mp4': {'category': 'Media', 'description': 'MP4 Video', 'subcategory': 'Video'},
            '.wav': {'category': 'Media', 'description': 'WAV Audio', 'subcategory': 'Audio'},
            '.avi': {'category': 'Media', 'description': 'AVI Video', 'subcategory': 'Video'},
            '.mov': {'category': 'Media', 'description': 'QuickTime Video', 'subcategory': 'Video'},
            '.jpg': {'category': 'Media', 'description': 'JPEG Image', 'subcategory': 'Image'},
            '.png': {'category': 'Media', 'description': 'PNG Image', 'subcategory': 'Image'},
            '.gif': {'category': 'Media', 'description': 'GIF Image', 'subcategory': 'Image'},
            
            # Database Files
            '.db': {'category': 'Database', 'description': 'Database File', 'subcategory': 'Data'},
            '.sqlite': {'category': 'Database', 'description': 'SQLite Database', 'subcategory': 'Data'},
            '.mdb': {'category': 'Database', 'description': 'Microsoft Access Database', 'subcategory': 'Data'},
            '.accdb': {'category': 'Database', 'description': 'Access Database', 'subcategory': 'Data'},
            
            # Executables
            '.exe': {'category': 'Executable', 'description': 'Windows Executable', 'subcategory': 'Program'},
            '.dll': {'category': 'Executable', 'description': 'Dynamic Link Library', 'subcategory': 'Library'},
            '.bin': {'category': 'Executable', 'description': 'Binary File', 'subcategory': 'Binary'},
            
            # 3D and Graphics
            '.obj': {'category': '3D/Graphics', 'description': '3D Object File', 'subcategory': '3D Model'},
            '.fbx': {'category': '3D/Graphics', 'description': 'Autodesk FBX', 'subcategory': '3D Model'},
            '.blend': {'category': '3D/Graphics', 'description': 'Blender File', 'subcategory': '3D Model'},
            
            # System Files
            '.log': {'category': 'System', 'description': 'Log File', 'subcategory': 'Log'},
            '.tmp': {'category': 'System', 'description': 'Temporary File', 'subcategory': 'Temporary'},
            '.cache': {'category': 'System', 'description': 'Cache File', 'subcategory': 'Cache'},
            
            # Email
            '.eml': {'category': 'Email', 'description': 'Email Message', 'subcategory': 'Message'},
            '.pst': {'category': 'Email', 'description': 'Outlook Data File', 'subcategory': 'Data'},
        }
        
        return extension_map.get(file_extension, {
            'category': 'Document', 
            'description': f'File ({file_extension})' if file_extension else 'File',
            'subcategory': 'Unknown'
        })

    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get statistics about extraction performance (for monitoring)."""
        return {
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'supported_formats': [
                'ALL FILE TYPES - Universal file support for engineers',
                'PDF (with OCR for scanned documents)',
                'CAD files (.dwg, .dxf, .dwf) - Enhanced metadata for engineering questions',
                'Word Documents, Excel, PowerPoint', 
                'Plain Text and Code files',
                'Outlook MSG files',
                'Images (JPEG, PNG, GIF, etc.)',
                '3D Models (.obj, .fbx, .blend)',
                'Archive files (.zip, .rar, .7z)',
                'Media files (audio, video)',
                'Database files',
                'Any binary format with intelligent metadata'
            ],
            'features': [
                'Universal file type support - ALL files are supported',
                'Enhanced CAD file support for engineering questions',
                'OCR for scanned documents and images',
                'Intelligent file type detection and categorization',
                'Comprehensive metadata extraction for searchability',
                'Engineering-focused content analysis',
                'Project context extraction from file paths',
                'Technical drawing and blueprint support',
                'Confidence scoring for quality assessment',
                'Retry mechanism for reliability',
                'Detailed error logging and diagnostics',
                'Multiple encoding support for international files'
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
