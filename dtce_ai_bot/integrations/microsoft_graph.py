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
        print("🔐 AUTH: Starting authentication...")
        logger.info("🔐 Starting authentication...")
        
        if not self._credential:
            print("🔑 AUTH: Creating new credential...")
            logger.info("🔑 Creating new credential...")
            self._credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            print("✅ AUTH: Credential created successfully")
            logger.info("✅ Credential created successfully")
        
        print("🎫 AUTH: Getting access token...")
        logger.info("🎫 Getting access token...")
        token = await self._credential.get_token(graph_urls.graph_scope())
        print("✅ AUTH: Access token received successfully")
        logger.info("✅ Access token received successfully")
        return token.token
    
    async def _make_request(self, endpoint: str, method: str = "GET") -> Dict[str, Any]:
        """Make authenticated request to Microsoft Graph API with improved timeout handling."""
        import asyncio
        
        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{graph_urls.graph_base_url()}/{endpoint}"
        
        # Shorter timeout for faster failure detection
        timeout = aiohttp.ClientTimeout(total=60, connect=15, sock_read=15)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                print(f"🌐 HTTP: Making Graph API request to: {endpoint}")
                logger.info(f"Making Graph API request to: {endpoint}")
                async with session.request(method, url, headers=headers) as response:
                    print(f"📡 HTTP: Graph API response status: {response.status} for {endpoint}")
                    logger.info(f"Graph API response status: {response.status} for {endpoint}")
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ HTTP: Graph API request successful for {endpoint}")
                        logger.info(f"Graph API request successful for {endpoint}")
                        return result
                    else:
                        error_text = await response.text()
                        print(f"❌ HTTP: Graph API request failed for {endpoint}")
                        logger.error(
                            "Microsoft Graph API request failed",
                            status=response.status,
                            endpoint=endpoint,
                            error=error_text
                        )
                        raise Exception(f"Graph API request failed: {response.status} - {error_text}")
        except asyncio.TimeoutError as e:
            print(f"⏰ TIMEOUT: Graph API request timed out for {endpoint}: {str(e)}")
            logger.error(f"Graph API request timed out for {endpoint}: {str(e)}")
            raise Exception(f"Graph API request timed out for {endpoint}")
        except Exception as e:
            print(f"💥 ERROR: Graph API request error for {endpoint}: {str(e)}")
            logger.error(f"Graph API request error for {endpoint}: {str(e)}")
            raise
    
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
        logger.info(f"🔍 Searching for site: {site_name}")
        logger.info("📡 About to call get_sites()...")
        
        sites = await self.get_sites()
        
        logger.info(f"📋 Received {len(sites)} sites, searching for '{site_name}'...")
        for site in sites:
            site_display_name = site.get("displayName", "")
            logger.info(f"🏢 Checking site: {site_display_name}")
            if site_name.lower() in site_display_name.lower():
                logger.info(f"✅ Found matching site: {site_display_name}")
                return site
        
        logger.warning(f"❌ Site '{site_name}' not found")
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
    
    async def sync_projects_folder_only(self) -> List[Dict[str, Any]]:
        """
        Fast sync that focuses ONLY on Projects folders.
        This is much faster than scanning all of Suitefiles.
        """
        try:
            logger.info("Starting fast Projects folder sync")
            
            # Find the Suitefiles site
            suitefiles_site = await self.get_site_by_name("suitefiles")
            if not suitefiles_site:
                logger.warning("Suitefiles site not found, trying 'dtce' site")
                suitefiles_site = await self.get_site_by_name("dtce")
            
            if not suitefiles_site:
                logger.error("No suitable SharePoint site found for Suitefiles")
                return []
            
            site_id = suitefiles_site["id"]
            logger.info("Found Suitefiles site for Projects sync", site_id=site_id)
            
            # Get document libraries
            drives = await self.get_drives(site_id)
            documents = []
            
            for drive in drives:
                drive_id = drive["id"]
                drive_name = drive.get("name", "Unknown")
                
                logger.info("Searching for Projects folder in drive", drive_name=drive_name)
                
                try:
                    # Look for Projects folder specifically
                    projects_files = await self._get_files_in_projects_folder(site_id, drive_id, drive_name)
                    
                    if projects_files:
                        logger.info("Found Projects folder with files", 
                                   drive_name=drive_name, 
                                   file_count=len(projects_files))
                        
                        # Process project files
                        for file in projects_files:
                            file_name = file.get("name", "")
                            full_path = file.get("full_path", "")
                            folder_path = file.get("folder_path", "")
                            file_id = file.get("id", "")
                            
                            # Extract project metadata
                            project_metadata = self._extract_project_metadata(full_path, file_name, folder_path)
                            
                            # Include ALL file types - no filtering by extension
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
                                # Project-specific metadata
                                "project_id": project_metadata.get("project_id"),
                                "project_folder": project_metadata.get("project_folder"),
                                "document_type": project_metadata.get("document_type"),
                                "folder_category": project_metadata.get("folder_category"),
                                "is_critical_for_search": project_metadata.get("is_critical_for_search", False)
                            }
                            documents.append(document_entry)
                    else:
                        logger.info("No Projects folder found in drive", drive_name=drive_name)
                        
                except Exception as e:
                    logger.error("Failed to process Projects folder in drive", 
                               drive_name=drive_name, error=str(e))
                    continue
            
            logger.info("Projects folder sync completed", 
                       total_documents=len(documents))
            
            return documents
            
        except Exception as e:
            logger.error("Projects folder sync failed", error=str(e))
            return []
    
    async def _get_files_in_projects_folder(self, site_id: str, drive_id: str, drive_name: str) -> List[Dict[str, Any]]:
        """Get files specifically from Projects folder and its subfolders."""
        try:
            # First, try to find the Projects folder
            folders_endpoint = f"sites/{site_id}/drives/{drive_id}/root/children"
            folders_response = await self._make_request(folders_endpoint)
            
            projects_folder_id = None
            for item in folders_response.get("value", []):
                if item.get("name", "").lower() == "projects" and "folder" in item:
                    projects_folder_id = item["id"]
                    logger.info("Found Projects folder", drive_name=drive_name, folder_id=projects_folder_id)
                    break
            
            if not projects_folder_id:
                logger.info("No Projects folder found in drive", drive_name=drive_name)
                return []
            
            # Get all files recursively from Projects folder
            files = []
            await self._get_files_recursive(site_id, drive_id, projects_folder_id, files, max_depth=10)
            
            logger.info("Retrieved files from Projects folder", 
                       drive_name=drive_name, 
                       total_files=len(files))
            
            return files
            
        except Exception as e:
            logger.error("Failed to get Projects folder files", 
                        drive_name=drive_name, error=str(e))
            return []
    
    async def _get_files_from_folder_limited(self, site_id: str, drive_id: str, folder_id: str, 
                                            files: List[Dict], max_files: int = 100, max_depth: int = 5, 
                                            current_depth: int = 0, folder_prefix: str = ""):
        """Get files from a folder with strict limits to prevent timeouts."""
        if current_depth >= max_depth or len(files) >= max_files:
            return
        
        try:
            endpoint = f"sites/{site_id}/drives/{drive_id}/items/{folder_id}/children"
            response = await self._make_request(endpoint)
            
            for item in response.get("value", []):
                if len(files) >= max_files:
                    logger.info(f"Reached file limit ({max_files}), stopping scan")
                    return
                    
                if "file" in item:
                    # Add full path info for filtering
                    item["full_path"] = f"{folder_prefix}/{item['name']}"
                    item["folder_path"] = folder_prefix
                    files.append(item)
                elif "folder" in item and current_depth < max_depth - 1:
                    # Recurse into subfolders but respect depth limit
                    subfolder_name = item["name"]
                    if not self._should_skip_folder("", subfolder_name):
                        await self._get_files_from_folder_limited(
                            site_id, drive_id, item["id"], files, 
                            max_files, max_depth, current_depth + 1,
                            f"{folder_prefix}/{subfolder_name}"
                        )
                    
        except Exception as e:
            logger.warning("Failed to get files from folder", 
                          folder_id=folder_id, depth=current_depth, error=str(e))

    async def _get_files_recursive(self, site_id: str, drive_id: str, folder_id: str, 
                                   files: List[Dict], current_depth: int = 0, max_depth: int = 10):
        """Recursively get files from a folder and its subfolders."""
        if current_depth >= max_depth:
            return
        
        try:
            endpoint = f"sites/{site_id}/drives/{drive_id}/items/{folder_id}/children"
            response = await self._make_request(endpoint)
            
            for item in response.get("value", []):
                if "file" in item:
                    # It's a file
                    files.append(item)
                elif "folder" in item:
                    # It's a folder, recurse into it
                    await self._get_files_recursive(
                        site_id, drive_id, item["id"], files, 
                        current_depth + 1, max_depth
                    )
                    
        except Exception as e:
            logger.warning("Failed to get files from folder", 
                          folder_id=folder_id, depth=current_depth, error=str(e))
    
    async def sync_suitefiles_documents(self, folders: List[str] = None, subfolder_filter: str = None) -> List[Dict[str, Any]]:
        """
        Sync documents from Suitefiles with folder-by-folder processing and IMMEDIATE UPLOAD.
        
        Args:
            folders: List of specific folders to sync (e.g., ["Projects", "Engineering"])
            subfolder_filter: Optional specific subfolder name (e.g., "219" for any folder's subfolder)
        
        Returns:
            List of document dictionaries with metadata
        """
        try:
            sync_mode = f"targeted ({', '.join(folders)})" if folders else "comprehensive"
            logger.info(f"Starting {sync_mode} Suitefiles document sync with IMMEDIATE UPLOAD")
            print(f"🚀 COMPREHENSIVE IMMEDIATE SYNC: All files will be uploaded instantly as they're processed!")
            
            # IMMEDIATE UPLOAD MODE - Import storage client
            from ..integrations.azure_storage import get_storage_client
            storage_client = get_storage_client()
            
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
            
            for drive in drives:
                drive_id = drive["id"]
                drive_name = drive.get("name", "Unknown")
                        
                logger.info(f"Processing drive for immediate upload scan", drive_id=drive_id, name=drive_name)
                
                try:
                    if folders:
                        # Process each specified folder one by one, completely with immediate upload
                        for target_folder_name in folders:
                            logger.info(f"Processing target folder: '{target_folder_name}' with immediate upload")
                            
                            if target_folder_name.lower() == "projects":
                                # Special handling for Projects - process each project folder completely
                                await self._process_projects_folder_by_folder(site_id, drive_id, documents, subfolder_filter, drive_name, storage_client)
                            else:
                                # Find and process other folders
                                target_folder_id = await self._find_folder_in_root(site_id, drive_id, target_folder_name)
                                
                                if target_folder_id:
                                    logger.info(f"Processing '{target_folder_name}' completely with immediate upload...")
                                    folder_documents = await self._process_folder_completely_recursive(
                                        site_id, drive_id, target_folder_id, target_folder_name,
                                        subfolder_filter, 0, None, drive_name, storage_client, True
                                    )
                                    documents.extend(folder_documents)
                                    logger.info(f"Completed '{target_folder_name}' - Got {len(folder_documents)} documents")
                                else:
                                    logger.warning(f"Target folder '{target_folder_name}' not found in drive {drive_name}")
                    else:
                        # Comprehensive scan - process all root folders completely with immediate upload
                        logger.info(f"Starting comprehensive scan of all folders in drive '{drive_name}' with immediate upload")
                        folder_documents = await self._process_all_folders_completely(
                            site_id, drive_id, subfolder_filter, drive_name, storage_client
                        )
                        documents.extend(folder_documents)
                    
                    logger.info(f"Completed drive '{drive_name}' processing - Total files so far: {len(documents)}")
                        
                except Exception as e:
                    logger.error(f"Failed to process drive '{drive_name}'", error=str(e))
                    continue
            
            # Final cleanup: Remove duplicates and sort by relevance
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
            
            logger.info(f"Level-by-level Suitefiles sync completed!", 
                       total_documents=len(final_documents),
                       duplicates_removed=len(documents) - len(final_documents))
            return final_documents
            
        except Exception as e:
            logger.error("Failed to sync Suitefiles documents", error=str(e))
            raise

    async def sync_suitefiles_documents_by_path(self, path: str) -> List[Dict[str, Any]]:
        """
        Sync documents from a specific SharePoint path.
        
        Args:
            path: SharePoint path (e.g., "Projects/219", "Projects/219/Drawings", "Engineering/Marketing")
        
        Returns:
            List of document dictionaries with metadata
        """
        print(f"🟢 ENTERED sync_suitefiles_documents_by_path with path: {path}")
        logger.info("=== PATH-BASED SYNC STARTED ===", path=path)
        logger.info("Initializing path-based document sync", target_path=path)
        
        try:
            logger.info(f"🚀 Starting path-based sync: {path}")
            
            # Find the Suitefiles site
            logger.info("📍 Step 1: Finding Suitefiles site...")
            logger.info("🔍 About to call get_site_by_name('suitefiles')...")
            
            suitefiles_site = await self.get_site_by_name("suitefiles")
            
            if not suitefiles_site:
                logger.warning("⚠️ Suitefiles site not found, trying 'dtce' site")
                logger.info("🔍 About to call get_site_by_name('dtce')...")
                suitefiles_site = await self.get_site_by_name("dtce")
            
            if not suitefiles_site:
                logger.error("❌ No suitable SharePoint site found for Suitefiles")
                return []
            
            site_id = suitefiles_site["id"]
            logger.info("✅ Found Suitefiles site", site_id=site_id, name=suitefiles_site.get("displayName"))
            
            # Get document libraries
            logger.info("Step 2: Getting document libraries...")
            drives = await self.get_drives(site_id)
            logger.info("Found drives", drive_count=len(drives))
            documents = []
            
            for i, drive in enumerate(drives):
                drive_id = drive["id"]
                drive_name = drive.get("name", "Unknown")
                        
                logger.info(f"Step 3.{i+1}: Processing drive {i+1}/{len(drives)}", 
                           drive_id=drive_id, name=drive_name, path=path)
                
                try:
                    # Navigate to the specific path and process it completely
                    path_documents = await self._process_specific_path(site_id, drive_id, path)
                    documents.extend(path_documents)
                    
                    logger.info(f"Completed path processing in drive '{drive_name}' - Got {len(path_documents)} documents")
                        
                except Exception as e:
                    logger.error(f"Failed to process path '{path}' in drive '{drive_name}'", error=str(e))
                    continue
            
            # Remove duplicates and sort
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
            
            final_documents = list(unique_documents.values())
            
            # Sort by relevance
            final_documents.sort(key=lambda x: (
                not x.get("is_critical_for_search", False),
                not bool(x.get("project_id")),
                "engineering" not in x.get("document_type", "").lower(),
                -x.get("size", 0)
            ))
            
            logger.info(f"Path-based sync completed!", 
                       path=path,
                       total_documents=len(final_documents),
                       duplicates_removed=len(documents) - len(final_documents))
            return final_documents
            
        except Exception as e:
            logger.error("Failed to sync by path", path=path, error=str(e))
            raise

    async def _process_specific_path(self, site_id: str, drive_id: str, path: str) -> List[Dict[str, Any]]:
        """Process a specific SharePoint path with smart limits and progress tracking."""
        logger.info("=== PROCESSING SPECIFIC PATH ===", path=path, site_id=site_id, drive_id=drive_id)
        
        try:
            logger.info(f"🎯 SMART PROCESSING: Processing path '{path}' with limits")
            
            # Get drive name for document metadata
            drives = await self.get_drives(site_id)
            drive_name = "Unknown"
            for drive in drives:
                if drive["id"] == drive_id:
                    drive_name = drive.get("name", "Unknown")
                    break
            
            # Navigate to the path
            path_parts = path.split('/')
            logger.info("📍 Path navigation started", path_parts=path_parts, total_parts=len(path_parts))
            current_folder_id = None
            
            # Start from root and navigate through each path part
            for i, part in enumerate(path_parts):
                logger.info(f"🔍 Navigating to part {i+1}/{len(path_parts)}: '{part}'")
                
                if i == 0:
                    # Find the root folder
                    logger.info(f"📁 Finding root folder: {part}")
                    current_folder_id = await self._find_folder_in_root(site_id, drive_id, part)
                    if not current_folder_id:
                        logger.warning(f"❌ Root folder '{part}' not found")
                        return []
                    logger.info(f"✅ Found root folder '{part}' with ID: {current_folder_id}")
                else:
                    # Find subfolder in current folder
                    logger.info(f"📂 Finding subfolder: {part} in current folder")
                    current_folder_id = await self._find_subfolder(site_id, drive_id, current_folder_id, part)
                    if not current_folder_id:
                        logger.warning(f"❌ Subfolder '{part}' not found in path")
                        return []
                    logger.info(f"✅ Found subfolder '{part}' with ID: {current_folder_id}")
            
            if not current_folder_id:
                logger.warning(f"❌ Could not navigate to path: {path}")
                return []
            
            # Process the target folder with smart limits
            logger.info(f"⚡ Processing target folder at path '{path}' with smart limits")
            print(f"⚡ SMART SYNC: Processing '{path}' with document limits to ensure completion")
            
            # IMMEDIATE UPLOAD MODE - Import storage client here
            from ..integrations.azure_storage import get_storage_client
            storage_client = get_storage_client()
            
            # NO PLACEHOLDER LOGIC - Just process what actually exists in SharePoint
            documents = []
            print(f"📤 PROCESSING: Getting ALL actual folders and files from SharePoint path '{path}' with IMMEDIATE UPLOAD")
            
            # Process the actual folder contents with immediate upload
            folder_documents = await self._process_folder_completely_recursive(
                site_id, drive_id, current_folder_id, path, None, 0, max_documents=None, drive_name=drive_name,
                storage_client=storage_client, immediate_upload=True
            )
            documents.extend(folder_documents)
            
            logger.info(f"✅ Completed processing path '{path}' - Got {len(documents)} documents")
            print(f"✅ SYNC COMPLETE: Got {len(documents)} documents from '{path}'")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Failed to process specific path '{path}'", error=str(e))
            print(f"❌ SYNC FAILED: Error processing '{path}': {str(e)}")
            return []

    async def _find_subfolder(self, site_id: str, drive_id: str, parent_folder_id: str, subfolder_name: str) -> Optional[str]:
        """Find a subfolder within a parent folder and return its ID."""
        try:
            logger.info(f"Searching for subfolder '{subfolder_name}' in parent folder...")
            response = await self._make_request(f"sites/{site_id}/drives/{drive_id}/items/{parent_folder_id}/children")
            
            for item in response.get("value", []):
                if item.get("name", "").lower() == subfolder_name.lower() and "folder" in item:
                    logger.info(f"Found subfolder '{subfolder_name}' with ID: {item['id']}")
                    return item["id"]
            
            logger.warning(f"Subfolder '{subfolder_name}' not found in parent folder")
            return None
            
        except Exception as e:
            logger.error(f"Failed to find subfolder '{subfolder_name}'", error=str(e))
            return None

    async def _find_folder_in_root(self, site_id: str, drive_id: str, folder_name: str) -> Optional[str]:
        """Find a specific folder in the drive root and return its ID."""
        try:
            logger.info(f"Searching for folder '{folder_name}' in drive root...")
            root_response = await self._make_request(f"sites/{site_id}/drives/{drive_id}/root/children")
            
            for item in root_response.get("value", []):
                if item.get("name", "").lower() == folder_name.lower() and "folder" in item:
                    logger.info(f"Found target folder '{folder_name}' with ID: {item['id']}")
                    return item["id"]
            
            logger.warning(f"Folder '{folder_name}' not found in drive root")
            return None
            
        except Exception as e:
            logger.error(f"Failed to find folder '{folder_name}' in root", error=str(e))
            return None

    async def _upload_document_immediately(self, document: Dict[str, Any], storage_client) -> bool:
        """
        Upload a document to blob storage immediately after processing.
        This provides instant feedback and progress to the user.
        """
        try:
            from ..config.settings import get_settings
            import json
            from datetime import datetime
            
            settings = get_settings()
            
            # Use folder_path to maintain SharePoint structure
            folder_path = document.get('folder_path', '')
            if folder_path:
                blob_name = f"{folder_path}/{document['name']}"
            else:
                # Fallback to basic structure
                blob_name = f"suitefiles/{document['drive_name']}/{document['name']}"
                
            blob_client = storage_client.get_blob_client(
                container=settings.azure_storage_container,
                blob=blob_name
            )
            
            # Check if already exists and up-to-date
            if blob_client.exists():
                properties = blob_client.get_blob_properties()
                if document.get("modified") and properties.last_modified:
                    doc_modified = document.get("modified")
                    blob_modified = properties.last_modified.isoformat()
                    if doc_modified <= blob_modified:
                        print(f"⏭️ SKIPPED: {document['name']} (already up-to-date)")
                        return True
            
            # Handle folders vs files differently
            if document.get("is_folder", False):
                # Create .keep file for empty folders
                keep_file_blob_name = f"{blob_name}/.keep"
                keep_file_content = f"# Folder: {document['name']}\n# Created: {datetime.now().isoformat()}\n# Path: {document.get('full_path', '')}\n"
                
                folder_info = {
                    "type": "folder",
                    "name": document["name"],
                    "full_path": document.get("full_path", ""),
                    "project_id": document.get("project_id", ""),
                    "folder_category": document.get("folder_category", ""),
                    "last_modified": document.get("modified", "")
                }
                
                keep_file_content += f"# Metadata: {json.dumps(folder_info, indent=2)}\n"
                
                # Sanitize metadata to ensure ASCII compatibility
                def sanitize_metadata_value(value):
                    """Convert metadata value to ASCII-safe string."""
                    if not value:
                        return ""
                    # Convert to string and encode/decode to remove non-ASCII characters
                    try:
                        return str(value).encode('ascii', errors='replace').decode('ascii')
                    except Exception:
                        # Fallback: replace all non-ASCII with underscore
                        return ''.join(c if ord(c) < 128 else '_' for c in str(value))
                
                metadata = {
                    "source": "immediate_sync",
                    "original_filename": ".keep",
                    "drive_name": sanitize_metadata_value(document["drive_name"]), 
                    "project_id": sanitize_metadata_value(document.get("project_id", "")),
                    "document_type": "folder_marker",
                    "folder_category": sanitize_metadata_value(document.get("folder_category", "")),
                    "last_modified": sanitize_metadata_value(document.get("modified", "")),
                    "is_critical": str(document.get("is_critical_for_search", False)),
                    "full_path": sanitize_metadata_value(document.get("full_path", "")),
                    "content_type": "text/plain",
                    "is_folder_marker": "true"
                }
                
                keep_file_blob_client = storage_client.get_blob_client(
                    container=settings.azure_storage_container,
                    blob=keep_file_blob_name
                )
                
                keep_file_blob_client.upload_blob(keep_file_content.encode('utf-8'), overwrite=True, metadata=metadata)
                
            else:
                # Download and upload file content immediately
                file_content = await self.download_file(
                    document["site_id"], 
                    document["drive_id"], 
                    document["file_id"]
                )
                
                # Sanitize metadata to ensure ASCII compatibility
                def sanitize_metadata_value(value):
                    """Convert metadata value to ASCII-safe string."""
                    if not value:
                        return ""
                    # Convert to string and encode/decode to remove non-ASCII characters
                    try:
                        return str(value).encode('ascii', errors='replace').decode('ascii')
                    except Exception:
                        # Fallback: replace all non-ASCII with underscore
                        return ''.join(c if ord(c) < 128 else '_' for c in str(value))
                
                metadata = {
                    "source": "immediate_sync",
                    "original_filename": sanitize_metadata_value(document["name"]),
                    "drive_name": sanitize_metadata_value(document["drive_name"]), 
                    "project_id": sanitize_metadata_value(document.get("project_id", "")),
                    "document_type": sanitize_metadata_value(document.get("document_type", "")),
                    "folder_category": sanitize_metadata_value(document.get("folder_category", "")),
                    "last_modified": sanitize_metadata_value(document.get("modified", "")),
                    "is_critical": str(document.get("is_critical_for_search", False)),
                    "full_path": sanitize_metadata_value(document.get("full_path", "")),
                    "content_type": sanitize_metadata_value(document.get("mime_type", "")),
                    "size": str(document.get("size", 0)),
                    "is_folder": "false"
                }
                
                blob_client.upload_blob(file_content, overwrite=True, metadata=metadata)
            
            return True
            
        except Exception as e:
            print(f"❌ UPLOAD FAILED: {document.get('name', 'Unknown')} - {str(e)}")
            logger.error(f"Failed to upload document immediately", doc_name=document.get('name'), error=str(e))
            return False

    async def _process_single_project_completely(self, site_id: str, drive_id: str, 
                                               projects_folder_id: str, project_folder_name: str,
                                               subfolder_filter: str = None, drive_name: str = "Unknown", storage_client=None) -> List[Dict[str, Any]]:
        """
        Process ONE project folder completely to the very bottom before moving to next with immediate upload.
        This processes the entire project folder tree completely.
        """
        documents = []
        immediate_upload = storage_client is not None
        
        try:
            logger.info(f"Starting COMPLETE processing of project '{project_folder_name}' with immediate upload: {immediate_upload}")
            
            # Get the specific project folder
            projects_response = await self._make_request(f"sites/{site_id}/drives/{drive_id}/items/{projects_folder_id}/children")
            project_folder_id = None
            
            for item in projects_response.get("value", []):
                if item.get("name", "") == project_folder_name and "folder" in item:
                    project_folder_id = item["id"]
                    logger.info(f"Found project folder '{project_folder_name}' with ID: {project_folder_id}")
                    break
            
            if not project_folder_id:
                logger.warning(f"Project folder '{project_folder_name}' not found")
                return []
            
            # Process this ONE project completely - go to the very bottom with immediate upload
            project_path = f"Projects/{project_folder_name}"
            project_docs = await self._process_folder_completely_recursive(
                site_id, drive_id, project_folder_id, project_path, subfolder_filter, 0, None, drive_name, storage_client, immediate_upload
            )
            
            documents.extend(project_docs)
            
            logger.info(f"COMPLETED project '{project_folder_name}' - Total documents: {len(project_docs)}")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to process project '{project_folder_name}' completely", error=str(e))
            return documents

    async def _process_folder_completely_recursive(self, site_id: str, drive_id: str, folder_id: str,
                                                  folder_path: str, subfolder_filter: str = None, 
                                                  depth: int = 0, max_documents: int = None, drive_name: str = "Unknown",
                                                  storage_client=None, immediate_upload: bool = True) -> List[Dict[str, Any]]:
        """
        Process a folder completely and recursively with IMMEDIATE UPLOAD.
        This uploads each file immediately after processing it so you see progress right away!
        """
        documents = []
        
        try:
            indent = "  " * depth
            logger.info(f"{indent}Processing folder: {folder_path} (depth {depth}) - IMMEDIATE UPLOAD MODE")
            
            # Get ALL items in this folder
            endpoint = f"sites/{site_id}/drives/{drive_id}/items/{folder_id}/children"
            response = await self._make_request(endpoint)
            items = response.get("value", [])
            
            files_in_folder = []
            subfolders_in_folder = []
            
            for item in items:
                if "file" in item:
                    files_in_folder.append(item)
                elif "folder" in item:
                    subfolders_in_folder.append(item)
            
            logger.info(f"{indent}Found {len(files_in_folder)} files and {len(subfolders_in_folder)} subfolders")
            print(f"{indent}📂 PROCESSING: {folder_path} - {len(files_in_folder)} files, {len(subfolders_in_folder)} folders")
            
            # CREATE FOLDER ENTRIES for all subfolders (even empty ones)
            for subfolder_item in subfolders_in_folder:
                subfolder_name = subfolder_item.get("name", "")
                subfolder_path = f"{folder_path}/{subfolder_name}"
                
                # Skip problematic folders only
                if self._should_skip_folder(subfolder_path, subfolder_name):
                    continue
                    
                # Create a folder entry
                folder_entry = await self._create_folder_entry(
                    site_id, drive_id, subfolder_item, folder_path, drive_name
                )
                if folder_entry:
                    documents.append(folder_entry)
                    
                    # IMMEDIATE UPLOAD for folder if storage_client provided
                    if immediate_upload and storage_client:
                        await self._upload_document_immediately(folder_entry, storage_client)
                        print(f"📁 UPLOADED: Folder {subfolder_path}")
            
            # Process files IMMEDIATELY - upload each one right after processing
            for i, file_item in enumerate(files_in_folder):
                try:
                    # Create document entry
                    document = await self._create_document_entry(
                        site_id, drive_id, file_item, folder_path, subfolder_filter, drive_name
                    )
                    if document:
                        documents.append(document)
                        
                        # IMMEDIATE UPLOAD if storage_client provided
                        if immediate_upload and storage_client:
                            await self._upload_document_immediately(document, storage_client)
                            print(f"📄 UPLOADED: {i+1}/{len(files_in_folder)} - {document['name']} in {folder_path}")
                        
                except Exception as e:
                    logger.error(f"Failed to process file {file_item.get('name', '')}", error=str(e))
                    continue
            
            logger.info(f"{indent}Processed {len(files_in_folder)} files in {folder_path}")
            
            # Process ALL subfolders recursively
            for subfolder_item in subfolders_in_folder:
                subfolder_name = subfolder_item.get("name", "")
                subfolder_path = f"{folder_path}/{subfolder_name}"
                
                # Skip problematic folders only
                if self._should_skip_folder(subfolder_path, subfolder_name):
                    logger.info(f"{indent}Skipping problematic folder: {subfolder_path}")
                    continue
                
                logger.info(f"{indent}Going deeper into: {subfolder_name}")
                
                # Recursively process this subfolder with immediate upload
                subfolder_docs = await self._process_folder_completely_recursive(
                    site_id, drive_id, subfolder_item["id"], subfolder_path,
                    subfolder_filter, depth + 1, None, drive_name, storage_client, immediate_upload
                )
                
                documents.extend(subfolder_docs)
                logger.info(f"{indent}Completed subfolder '{subfolder_name}' - got {len(subfolder_docs)} documents")
            
            logger.info(f"{indent}COMPLETED {folder_path} - Total: {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to process folder {folder_path} completely", error=str(e))
            return documents

    async def _process_projects_folder_by_folder(self, site_id: str, drive_id: str, 
                                               documents: List[Dict], subfolder_filter: str = None, drive_name: str = "Unknown", storage_client=None):
        """
        Process Projects folder by going through each project folder completely with immediate upload.
        Each project is processed to the very bottom before moving to the next.
        """
        try:
            # Find the Projects folder
            projects_folder_id = await self._find_folder_in_root(site_id, drive_id, "Projects")
            
            if not projects_folder_id:
                logger.warning("Projects folder not found in drive")
                return
            
            # Get all project folders
            projects_response = await self._make_request(f"sites/{site_id}/drives/{drive_id}/items/{projects_folder_id}/children")
            project_folders = [item for item in projects_response.get("value", []) if "folder" in item]
            
            logger.info(f"Found {len(project_folders)} project folders to process")
            
            # Process each project folder COMPLETELY before moving to next
            for i, project_item in enumerate(project_folders):
                project_name = project_item.get("name", "")
                
                # Apply subfolder filter if specified
                if subfolder_filter and subfolder_filter not in project_name:
                    logger.info(f"Skipping project '{project_name}' (doesn't match filter '{subfolder_filter}')")
                    continue
                
                logger.info(f"Processing project {i+1}/{len(project_folders)}: '{project_name}' COMPLETELY")
                
                # Process this project folder completely to the very bottom
                project_docs = await self._process_single_project_completely(
                    site_id, drive_id, projects_folder_id, project_name, subfolder_filter, drive_name, storage_client
                )
                
                documents.extend(project_docs)
                
                logger.info(f"COMPLETED project '{project_name}' - Got {len(project_docs)} documents. Total so far: {len(documents)}")
            
        except Exception as e:
            logger.error("Failed to process Projects folder by folder", error=str(e))

    async def _process_all_folders_completely(self, site_id: str, drive_id: str,
                                            subfolder_filter: str = None, drive_name: str = "Unknown", 
                                            storage_client=None) -> List[Dict[str, Any]]:
        """Process all root folders completely - each folder to the very bottom with immediate upload."""
        documents = []
        immediate_upload = storage_client is not None
        
        try:
            # Get all root folders
            root_response = await self._make_request(f"sites/{site_id}/drives/{drive_id}/root/children")
            root_items = root_response.get("value", [])
            
            root_folders = [item for item in root_items if "folder" in item]
            logger.info(f"Found {len(root_folders)} root folders to process completely")
            
            if immediate_upload:
                print(f"🚀 COMPREHENSIVE IMMEDIATE UPLOAD: Processing {len(root_folders)} root folders with instant file uploads!")
            
            # Process each root folder completely
            for i, folder_item in enumerate(root_folders):
                folder_name = folder_item.get("name", "")
                
                # Skip problematic folders
                if self._should_skip_folder(folder_name, folder_name):
                    logger.debug(f"Skipping root folder: {folder_name}")
                    continue
                
                logger.info(f"Processing root folder {i+1}/{len(root_folders)}: {folder_name} COMPLETELY")
                
                folder_docs = await self._process_folder_completely_recursive(
                    site_id, drive_id, folder_item["id"], folder_name,
                    subfolder_filter, 0, None, drive_name, storage_client, immediate_upload
                )
                
                documents.extend(folder_docs)
                
                logger.info(f"Completed root folder '{folder_name}', total documents: {len(documents)}")
            
            return documents
            
        except Exception as e:
            logger.error("Failed to process all folders completely", error=str(e))
            return documents

    async def _create_document_entry(self, site_id: str, drive_id: str, file_item: Dict, 
                                   folder_path: str, path_filter: str = None, drive_name: str = "Unknown") -> Optional[Dict[str, Any]]:
        """Create a document entry from a file item with proper filtering."""
        try:
            file_name = file_item.get("name", "")
            file_id = file_item.get("id", "")
            full_path = f"{folder_path}/{file_name}"
            
            # Debug logging to see the paths being constructed
            print(f"🔍 DEBUG: Creating document entry for '{file_name}'")
            print(f"🔍 DEBUG: folder_path = '{folder_path}'")
            print(f"🔍 DEBUG: full_path = '{full_path}'")
            logger.info(f"Creating document entry", file_name=file_name, folder_path=folder_path, full_path=full_path)
            
            # Extract project metadata
            project_metadata = self._extract_project_metadata(full_path, file_name, folder_path)
            
            # Apply path filter if specified (this is now unused but kept for compatibility)
            # Path filtering is handled at the navigation level
            
            # Skip photos folders - but allow if user specifically wants all files
            # if self._is_photos_folder(full_path):
            #     return None
            
            # Support ALL file types - no filtering by extension
            # User wants all files to be included
            
            # Create document entry
            document_entry = {
                "site_id": site_id,
                "drive_id": drive_id,
                "drive_name": drive_name,
                "file_id": file_id,
                "name": file_name,
                "size": file_item.get("size", 0),
                "modified": file_item.get("lastModifiedDateTime"),
                "download_url": file_item.get("@microsoft.graph.downloadUrl"),
                "mime_type": file_item.get("file", {}).get("mimeType", ""),
                "full_path": full_path,
                "folder_path": folder_path,
                # Project-specific metadata
                "project_id": project_metadata.get("project_id"),
                "project_folder": project_metadata.get("project_folder"),
                "document_type": project_metadata.get("document_type"),
                "folder_category": project_metadata.get("folder_category"),
                "is_critical_for_search": project_metadata.get("is_critical_for_search", False)
            }
            
            return document_entry
            
        except Exception as e:
            logger.error(f"Failed to create document entry for file '{file_item.get('name', '')}'", error=str(e))
            return None

    async def _create_folder_entry(self, site_id: str, drive_id: str, folder_item: Dict, 
                                   parent_folder_path: str, drive_name: str = "Unknown") -> Optional[Dict[str, Any]]:
        """Create a folder entry so empty folders appear in blob storage."""
        try:
            folder_name = folder_item.get("name", "")
            folder_id = folder_item.get("id", "")
            full_path = f"{parent_folder_path}/{folder_name}"
            
            print(f"📁 DEBUG: Creating folder entry for '{folder_name}'")
            print(f"📁 DEBUG: parent_folder_path = '{parent_folder_path}'")
            print(f"📁 DEBUG: full_path = '{full_path}'")
            
            # Extract project metadata for folder
            project_metadata = self._extract_project_metadata(full_path, folder_name, parent_folder_path)
            
            # Create folder entry (similar to file entry but marked as folder)
            folder_entry = {
                "site_id": site_id,
                "drive_id": drive_id,
                "drive_name": drive_name,
                "file_id": folder_id,
                "name": folder_name,
                "size": 0,  # Folders have no size
                "modified": folder_item.get("lastModifiedDateTime"),
                "download_url": None,  # Folders can't be downloaded
                "mime_type": "application/vnd.folder",  # Custom MIME type for folders
                "full_path": full_path,
                "folder_path": parent_folder_path,
                "is_folder": True,  # Mark this as a folder entry
                # Project-specific metadata
                "project_id": project_metadata.get("project_id"),
                "project_folder": project_metadata.get("project_folder"),
                "document_type": "folder",
                "folder_category": project_metadata.get("folder_category"),
                "is_critical_for_search": project_metadata.get("is_critical_for_search", False)
            }
            
            return folder_entry
            
        except Exception as e:
            logger.error(f"Failed to create folder entry for folder '{folder_item.get('name', '')}'", error=str(e))
            return None

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
                    # Check if there's a sub-project folder (e.g., Projects/219/219200)
                    if i + 2 < len(path_parts):
                        sub_project_part = path_parts[i + 2]
                        if sub_project_part.isdigit() or any(char.isdigit() for char in sub_project_part):
                            # Use the more specific sub-project ID
                            metadata["project_id"] = sub_project_part
                            metadata["project_folder"] = f"{project_part}/{sub_project_part}"
                            folder_offset = 3  # Look at path_parts[i + 3] for document type
                        else:
                            # No sub-project, use main project
                            metadata["project_id"] = project_part
                            metadata["project_folder"] = project_part
                            folder_offset = 2  # Look at path_parts[i + 2] for document type
                    else:
                        # Only main project folder
                        metadata["project_id"] = project_part
                        metadata["project_folder"] = project_part
                        folder_offset = 2
                    
                    metadata["is_critical_for_search"] = True
                    
                    # Determine document type based on subsequent folder structure
                    if i + folder_offset < len(path_parts):
                        subfolder = path_parts[i + folder_offset].lower()
                        if "fees" in subfolder or "invoice" in subfolder:
                            metadata["document_type"] = "fees_invoices"
                            metadata["folder_category"] = "01_Fees_and_Invoices"
                        elif "email" in subfolder:
                            metadata["document_type"] = "emails"
                            metadata["folder_category"] = "02_Emails"
                        elif "admin" in subfolder:
                            metadata["document_type"] = "admin_documents"
                            metadata["folder_category"] = "01_Admin_Documents"
                        elif "quality" in subfolder or "assurance" in subfolder:
                            metadata["document_type"] = "quality_assurance"
                            metadata["folder_category"] = "02_Quality_Assurance"
                        elif "rfi" in subfolder:
                            metadata["document_type"] = "rfi"
                            metadata["folder_category"] = "03_RFI"
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

        return False  # Don't skip anything else - user wants ALL folders and files

    async def _get_project_folder_template(self, site_id: str, drive_id: str, current_project_id: str) -> List[str]:
        """
        Dynamically analyze other projects to determine what folder structure should exist.
        This creates a template based on the most common folders found across all projects.
        """
        try:
            print(f"🔍 DYNAMIC ANALYSIS: Analyzing other projects to create folder template for {current_project_id}")
            
            # Find the Projects folder
            projects_folder_id = await self._find_folder_in_root(site_id, drive_id, "Projects")
            if not projects_folder_id:
                print("⚠️ No Projects folder found, unable to create template")
                return []  # Return an empty list if no Projects folder is found

            # Get all project folders
            projects_response = await self._make_request(f"sites/{site_id}/drives/{drive_id}/items/{projects_folder_id}/children")
            project_folders = [item for item in projects_response.get("value", []) if "folder" in item]

            folder_frequency = {}
            projects_analyzed = 0

            print(f"📊 ANALYSIS: Found {len(project_folders)} projects to analyze")

            # Analyze up to 5 other projects to build folder template
            for project_item in project_folders[:5]:
                project_name = project_item.get("name", "")

                # Skip the current project
                if project_name == current_project_id:
                    continue

                try:
                    # Get folders in this project
                    project_response = await self._make_request(f"sites/{site_id}/drives/{drive_id}/items/{project_item['id']}/children")
                    project_subfolders = [item.get("name", "") for item in project_response.get("value", []) if "folder" in item]

                    print(f"📋 Project {project_name} has folders: {sorted(project_subfolders)}")

                    # Count frequency of each folder
                    for folder_name in project_subfolders:
                        if folder_name:  # Skip empty names
                            folder_frequency[folder_name] = folder_frequency.get(folder_name, 0) + 1

                    projects_analyzed += 1

                except Exception as e:
                    print(f"⚠️ Failed to analyze project {project_name}: {str(e)}")
                    continue

            if projects_analyzed == 0:
                print("⚠️ No projects could be analyzed, unable to create template")
                return []  # Return an empty list if no projects could be analyzed

            # Create template from folders that appear in at least 50% of projects
            min_frequency = max(1, projects_analyzed // 2)
            template_folders = [
                folder for folder, freq in folder_frequency.items() 
                if freq >= min_frequency
            ]

            # Sort template folders naturally
            template_folders.sort()

            print(f"📋 TEMPLATE CREATED: {len(template_folders)} folders found in {projects_analyzed} projects")
            print(f"📋 TEMPLATE FOLDERS: {template_folders}")

            return template_folders

        except Exception as e:
            print(f"❌ Error analyzing projects for template: {str(e)}")
            return []  # Return an empty list in case of error
        

async def get_graph_client() -> MicrosoftGraphClient:
    """Dependency injection for Microsoft Graph client."""
    return MicrosoftGraphClient()
