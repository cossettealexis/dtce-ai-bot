"""
Microsoft Graph API integration for Suitefiles/SharePoint document access.
Implements authentication and document retrieval from SharePoint sites.
"""

import os
from typing import List, Dict, Any, Optional
import asyncio
import aiohttp
import structlog
from azure.identity.aio import ClientSecretCredential
from ..config.settings import get_settings
from ..utils.graph_urls import graph_urls

logger = structlog.get_logger(__name__)
settings = get_settings()


class MicrosoftGraphClient:
    """Client for Microsoft Graph API to access SharePoint/Suitefiles."""
    
    def __init__(self):
        self.tenant_id = settings.MICROSOFT_TENANT_ID
        self.client_id = settings.MICROSOFT_CLIENT_ID
        self.client_secret = settings.MICROSOFT_CLIENT_SECRET
        self._credential = None
        self._access_token = None
        
    async def _get_access_token(self) -> str:
        """Get access token for Microsoft Graph API."""
        if not self._credential:
            self._credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
        
        token = await self._credential.get_token(graph_urls.graph_scope())
        return token.token
    
    async def _make_request(self, endpoint: str, method: str = "GET") -> Dict[str, Any]:
        """Make authenticated request to Microsoft Graph API."""
        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{graph_urls.graph_base_url()}/{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(
                        "Microsoft Graph API request failed",
                        status=response.status,
                        endpoint=endpoint,
                        error=error_text
                    )
                    raise Exception(f"Graph API request failed: {response.status} - {error_text}")
    
    async def get_sites(self) -> List[Dict[str, Any]]:
        """Get available SharePoint sites."""
        try:
            logger.info("Fetching SharePoint sites")
            response = await self._make_request("sites")
            sites = response.get("value", [])
            logger.info("Retrieved SharePoint sites", count=len(sites))
            return sites
        except Exception as e:
            logger.error("Failed to get SharePoint sites", error=str(e))
            raise
    
    async def get_site_by_name(self, site_name: str) -> Optional[Dict[str, Any]]:
        """Get specific SharePoint site by name."""
        sites = await self.get_sites()
        for site in sites:
            if site_name.lower() in site.get("displayName", "").lower():
                return site
        return None
    
    async def get_drives(self, site_id: str) -> List[Dict[str, Any]]:
        """Get document libraries (drives) for a SharePoint site."""
        try:
            logger.info("Fetching drives for site", site_id=site_id)
            response = await self._make_request(f"sites/{site_id}/drives")
            drives = response.get("value", [])
            logger.info("Retrieved drives", count=len(drives), site_id=site_id)
            return drives
        except Exception as e:
            logger.error("Failed to get drives", site_id=site_id, error=str(e))
            raise
    
    async def get_files_in_drive(self, site_id: str, drive_id: str, folder_path: str = None, max_depth: int = 20, current_depth: int = 0) -> List[Dict[str, Any]]:
        """
        Get files from a SharePoint drive, recursively exploring ALL subfolders.
        
        Args:
            site_id: SharePoint site ID
            drive_id: Drive ID within the site
            folder_path: Optional path to specific folder (None for root)
            max_depth: Maximum recursion depth to prevent infinite loops
            current_depth: Current recursion depth
            
        Returns:
            List of all files found, including those in subfolders with full path info
        """
        try:
            if current_depth > max_depth:
                logger.warning("Max recursion depth reached", depth=current_depth, folder_path=folder_path)
                return []
                
            # Build endpoint for current folder
            if folder_path:
                endpoint = f"sites/{site_id}/drives/{drive_id}/root:/{folder_path}:/children"
            else:
                endpoint = f"sites/{site_id}/drives/{drive_id}/root/children"
            
            logger.info("Fetching items from drive", 
                       site_id=site_id, drive_id=drive_id, 
                       folder_path=folder_path, depth=current_depth)
            
            response = await self._make_request(endpoint)
            items = response.get("value", [])
            
            all_files = []
            
            for item in items:
                if "file" in item:
                    # It's a file - add it to our results with full path information
                    item["full_path"] = f"{folder_path}/{item['name']}" if folder_path else item["name"]
                    item["folder_path"] = folder_path or ""
                    all_files.append(item)
                    
                elif "folder" in item:
                    # It's a folder - check if we should skip it before recursing
                    folder_name = item["name"]
                    subfolder_path = f"{folder_path}/{folder_name}" if folder_path else folder_name
                    
                    # Skip non-engineering folders early to save time
                    if self._should_skip_folder(subfolder_path, folder_name):
                        logger.debug("Skipping non-engineering folder", folder_name=folder_name, path=subfolder_path)
                        continue
                    
                    # Skip folders with URL-problematic names to avoid API errors
                    if self._has_url_problematic_chars(folder_name):
                        logger.debug("Skipping folder with problematic characters", folder_name=folder_name)
                        continue
                    
                    logger.debug("Exploring subfolder", folder_name=folder_name, path=subfolder_path, depth=current_depth)
                    
                    # Recursively get files from this subfolder
                    try:
                        subfolder_files = await self.get_files_in_drive(
                            site_id, drive_id, subfolder_path, max_depth, current_depth + 1
                        )
                        all_files.extend(subfolder_files)
                    except Exception as e:
                        logger.warning("Failed to explore subfolder", 
                                     folder_name=folder_name, error=str(e))
                        continue
            
            files_count = len([f for f in all_files if "file" in f])
            logger.info("Retrieved files from drive level", 
                       files_count=files_count, 
                       drive_id=drive_id, folder_path=folder_path, depth=current_depth)
            
            return all_files
            
        except Exception as e:
            logger.error("Failed to get files from drive", 
                        drive_id=drive_id, folder_path=folder_path, error=str(e))
            raise
    
    async def download_file(self, site_id: str, drive_id: str, file_id: str) -> bytes:
        """Download file content from SharePoint."""
        try:
            endpoint = f"sites/{site_id}/drives/{drive_id}/items/{file_id}/content"
            logger.info("Downloading file", file_id=file_id)
            
            access_token = await self._get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            url = f"{graph_urls.graph_base_url()}/{endpoint}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.read()
                        logger.info("File downloaded successfully", file_id=file_id, size=len(content))
                        return content
                    else:
                        error_text = await response.text()
                        logger.error("Failed to download file", file_id=file_id, status=response.status, error=error_text)
                        raise Exception(f"File download failed: {response.status} - {error_text}")
        except Exception as e:
            logger.error("Failed to download file", file_id=file_id, error=str(e))
            raise
    
    async def sync_suitefiles_documents(self) -> List[Dict[str, Any]]:
        """
        Main method to sync documents from Suitefiles with focus on Engineering projects.
        Recursively explores ALL folders to find project documents and engineering files.
        """
        try:
            logger.info("Starting comprehensive Suitefiles document sync")
            
            # Find the Suitefiles site
            suitefiles_site = await self.get_site_by_name("suitefiles")
            if not suitefiles_site:
                logger.warning("Suitefiles site not found, trying 'dtce' site")
                suitefiles_site = await self.get_site_by_name("dtce")
            
            if not suitefiles_site:
                logger.error("No suitable SharePoint site found for Suitefiles")
                return []
            
            site_id = suitefiles_site["id"]
            logger.info("Found Suitefiles site", site_id=site_id, name=suitefiles_site.get("displayName"))
            
            # Get document libraries
            drives = await self.get_drives(site_id)
            documents = []
            
            # Set high depth limit to get ALL folders and subfolders 
            max_depth = 50  # Increased to ensure we get every child folder
            
            for drive in drives:
                drive_id = drive["id"]
                drive_name = drive.get("name", "Unknown")
                
                logger.info("Processing drive for COMPLETE scan", drive_id=drive_id, name=drive_name)
                
                # Process ALL drives - no skipping, user wants everything
                try:
                    # Get ALL files from this drive with generous timeout
                    import asyncio
                    files = await asyncio.wait_for(
                        self.get_files_in_drive(site_id, drive_id, max_depth=max_depth),
                        timeout=180.0  # 3 minutes per drive for complete scan
                    )
                    logger.info("Retrieved ALL files from drive", drive_name=drive_name, file_count=len(files))
                except asyncio.TimeoutError:
                    logger.warning("Drive processing timed out - may be incomplete", drive_name=drive_name)
                    continue
                except Exception as e:
                    logger.error("Failed to process drive", drive_name=drive_name, error=str(e))
                    continue
                
                # Track processed files to avoid duplicates
                processed_files = set()
                
                for file in files:
                    file_name = file.get("name", "")
                    full_path = file.get("full_path", "")
                    folder_path = file.get("folder_path", "")
                    file_id = file.get("id", "")
                    
                    # Skip duplicate files (same file_id)
                    if file_id in processed_files:
                        logger.debug("Skipping duplicate file", file_name=file_name, file_id=file_id)
                        continue
                    processed_files.add(file_id)
                    
                    # Extract project metadata based on folder structure
                    project_metadata = self._extract_project_metadata(full_path, file_name, folder_path)
                    
                    # Skip photos folders as specified
                    if self._is_photos_folder(full_path):
                        logger.debug("Skipping photo file", file_name=file_name, path=full_path)
                        continue
                    
                    # Focus on ALL files - minimal filtering to get everything
                    if True:  # Process ALL files, user wants everything
                        # Include ALL document types, not just engineering ones
                        if any(file_name.lower().endswith(ext) for ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.md', '.pptx', '.ppt', '.dwg', '.dxf', '.zip', '.rar']):
                            document_entry = {
                                "site_id": site_id,
                                "drive_id": drive_id,
                                "file_id": file_id,
                                "name": file_name,
                                "size": file.get("size", 0),
                                "modified": file.get("lastModifiedDateTime"),
                                "download_url": file.get("@microsoft.graph.downloadUrl"),
                                "drive_name": drive_name,
                                "mime_type": file.get("file", {}).get("mimeType", ""),
                                "full_path": full_path,
                                "folder_path": folder_path,
                                # Engineering-specific metadata
                                "project_id": project_metadata.get("project_id"),
                                "project_folder": project_metadata.get("project_folder"),
                                "document_type": project_metadata.get("document_type"),
                                "folder_category": project_metadata.get("folder_category"),
                                "is_critical_for_search": project_metadata.get("is_critical_for_search", False)
                            }
                            documents.append(document_entry)
                        else:
                            logger.debug("File type not supported for processing", file_name=file_name, path=full_path)
            
            # Final cleanup: Remove duplicates based on file_id and optimize results
            unique_documents = {}
            for doc in documents:
                file_id = doc.get("file_id")
                if file_id and file_id not in unique_documents:
                    unique_documents[file_id] = doc
                elif file_id:
                    # Keep the more recent version if duplicate
                    existing_modified = unique_documents[file_id].get("modified", "")
                    current_modified = doc.get("modified", "")
                    if current_modified > existing_modified:
                        unique_documents[file_id] = doc
                        logger.debug("Replaced older duplicate with newer version", file_id=file_id)
            
            # Convert back to list and sort by relevance
            final_documents = list(unique_documents.values())
            
            # Sort by: 1) Critical for search, 2) Project files, 3) Engineering files, 4) Size (larger first)
            final_documents.sort(key=lambda x: (
                not x.get("is_critical_for_search", False),  # Critical first (False sorts before True)
                not bool(x.get("project_id")),  # Project files first
                "engineering" not in x.get("document_type", "").lower(),  # Engineering files first
                -x.get("size", 0)  # Larger files first
            ))
            
            logger.info("Comprehensive Suitefiles sync completed", 
                       total_documents=len(final_documents),
                       duplicates_removed=len(documents) - len(final_documents))
            return final_documents
            
        except Exception as e:
            logger.error("Failed to sync Suitefiles documents", error=str(e))
            raise

    def _extract_project_metadata(self, full_path: str, file_name: str, folder_path: str) -> Dict[str, Any]:
        """
        Extract project metadata from the file path for ALL projects.
        Analyzes folder structure to determine project info and document classification.
        """
        metadata = {
            "project_id": None,
            "project_folder": None,
            "document_type": "general",
            "folder_category": None,
            "is_critical_for_search": False
        }
        
        if not full_path and not folder_path:
            return metadata
        
        path_to_analyze = full_path or folder_path
        path_parts = path_to_analyze.split('/')
        
        # Look for Projects folder and extract project info
        for i, part in enumerate(path_parts):
            if part.lower() == "projects" and i + 1 < len(path_parts):
                # Next part should be a project folder (e.g., "219", "220", etc.)
                project_part = path_parts[i + 1]
                if project_part.isdigit() or any(char.isdigit() for char in project_part):
                    metadata["project_id"] = project_part
                    metadata["project_folder"] = project_part
                    metadata["is_critical_for_search"] = True
                    
                    # Determine document type based on subsequent folder structure
                    if i + 2 < len(path_parts):
                        subfolder = path_parts[i + 2].lower()
                        if "fees" in subfolder or "invoice" in subfolder:
                            metadata["document_type"] = "fees_invoices"
                            metadata["folder_category"] = "01_Fees_and_Invoices"
                        elif "email" in subfolder:
                            metadata["document_type"] = "emails"
                            metadata["folder_category"] = "02_Emails"
                        elif "internal" in subfolder or "review" in subfolder:
                            metadata["document_type"] = "internal_review"
                            metadata["folder_category"] = "03_For_internal_review"
                        elif "design" in subfolder or "structural" in subfolder or "civil" in subfolder:
                            metadata["document_type"] = "design_calculations"
                            metadata["folder_category"] = "04_Design_and_Structural_Calculations"
                        elif "drawing" in subfolder or "plan" in subfolder:
                            metadata["document_type"] = "drawings_plans"
                            metadata["folder_category"] = "05_Drawings_and_Plans"
                        elif "report" in subfolder:
                            metadata["document_type"] = "reports"
                            metadata["folder_category"] = "06_Reports"
                        elif "spec" in subfolder or "contract" in subfolder:
                            metadata["document_type"] = "specifications_contracts"
                            metadata["folder_category"] = "07_Specifications_and_Contracts"
                        elif "correspondence" in subfolder:
                            metadata["document_type"] = "correspondence"
                            metadata["folder_category"] = "08_Correspondence"
                        elif "photo" in subfolder:
                            metadata["document_type"] = "photos"
                            metadata["folder_category"] = "09_Photos"
                break
        
        # Check for Engineering folder content
        if "engineering" in path_to_analyze.lower():
            metadata["is_critical_for_search"] = True
            metadata["document_type"] = "engineering_reference"
            metadata["folder_category"] = "Engineering"
            
            # Determine specific engineering document type
            lower_path = path_to_analyze.lower()
            if "guide" in lower_path or "procedure" in lower_path:
                metadata["document_type"] = "engineering_guide"
            elif "reference" in lower_path or "manual" in lower_path:
                metadata["document_type"] = "engineering_reference"
            elif "template" in lower_path or "form" in lower_path:
                metadata["document_type"] = "engineering_template"
        
        # Additional document type classification based on file name
        file_lower = file_name.lower()
        if "invoice" in file_lower or "fee" in file_lower:
            metadata["document_type"] = "fees_invoices"
        elif "email" in file_lower or "correspondence" in file_lower:
            metadata["document_type"] = "emails"
        elif "report" in file_lower:
            metadata["document_type"] = "reports"
        elif "drawing" in file_lower or "plan" in file_lower or "dwg" in file_lower:
            metadata["document_type"] = "drawings_plans"
        elif "spec" in file_lower or "contract" in file_lower:
            metadata["document_type"] = "specifications_contracts"
        elif "calc" in file_lower or "calculation" in file_lower:
            metadata["document_type"] = "design_calculations"
        
        return metadata
    
    def _should_skip_folder(self, folder_path: str, folder_name: str) -> bool:
        """
        Determine if a folder should be skipped - MINIMAL filtering since user wants ALL files.
        Only skip folders that are definitely problematic or cause API errors.
        """
        folder_path_lower = folder_path.lower()
        folder_name_lower = folder_name.lower()
        
        # Only skip folders that cause technical issues - user wants everything else
        problematic_only = [
            "recycle bin", "$recycle.bin", "system volume information",
            ".git", ".svn", "node_modules"  # Only technical/system folders
        ]
        
        # Check if any problematic pattern is in the folder path
        for pattern in problematic_only:
            if pattern in folder_path_lower:
                return True
        
        # Skip folders with URL-problematic characters that cause API errors
        if self._has_url_problematic_chars(folder_name):
            return True
        
        return False  # Don't skip anything else - user wants ALL folders and files

    def _has_url_problematic_chars(self, folder_name: str) -> bool:
        """Check if folder name has characters that cause URL encoding issues."""
        problematic_chars = ["#", "###", "%", "&", "+", "=", ":", ";", "?", "[", "]", "{", "}"]
        return any(char in folder_name for char in problematic_chars)

    def _is_engineering_relevant(self, full_path: str, file_name: str) -> bool:
        """
        Determine if a file is relevant for engineering search based on path and name.
        Now includes ALL project folders, not just specific ranges.
        """
        # Always include Engineering folder
        if "engineering" in full_path.lower():
            return True
            
        # Include ALL project folders (any folder under Projects/)
        if "/projects/" in full_path.lower():
            # Check if it's actually a project folder by looking for numeric or project-like names
            path_parts = full_path.lower().split('/')
            for i, part in enumerate(path_parts):
                if part == "projects" and i + 1 < len(path_parts):
                    next_part = path_parts[i + 1]
                    # Include if next part looks like a project (contains digits or is reasonable project name)
                    if (next_part.isdigit() or 
                        any(char.isdigit() for char in next_part) or
                        len(next_part) <= 10):  # Reasonable project folder name length
                        return True
            
        # Check file name for engineering keywords
        file_lower = file_name.lower()
        engineering_keywords = [
            'engineering', 'structural', 'civil', 'calculation', 'design',
            'report', 'specification', 'drawing', 'plan', 'blueprint',
            'analysis', 'load', 'beam', 'foundation', 'concrete', 'steel'
        ]
        
        if any(keyword in file_lower for keyword in engineering_keywords):
            return True
            
        # Include important document types regardless of folder
        important_extensions = ['.pdf', '.docx', '.xlsx', '.dwg', '.dxf']
        if any(file_name.lower().endswith(ext) for ext in important_extensions):
            return True
            
        return False
    
    def _is_photos_folder(self, full_path: str) -> bool:
        """
        Check if the file is in a photos folder that should be skipped.
        """
        return "photos" in full_path.lower() or "09_photos" in full_path.lower()


async def get_graph_client() -> MicrosoftGraphClient:
    """Dependency injection for Microsoft Graph client."""
    return MicrosoftGraphClient()
