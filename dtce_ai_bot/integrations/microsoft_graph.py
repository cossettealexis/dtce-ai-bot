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
        Sync documents from Suitefiles with folder-by-folder processing.
        
        Args:
            folders: List of specific folders to sync (e.g., ["Projects", "Engineering"])
            subfolder_filter: Optional specific subfolder name (e.g., "219" for any folder's subfolder)
        
        Returns:
            List of document dictionaries with metadata
        """
        try:
            sync_mode = f"targeted ({', '.join(folders)})" if folders else "comprehensive"
            logger.info(f"Starting {sync_mode} Suitefiles document sync with level-by-level traversal")
            
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
                        
                logger.info(f"Processing drive for level-by-level scan", drive_id=drive_id, name=drive_name)
                
                try:
                    if folders:
                        # Process each specified folder one by one, completely
                        for target_folder_name in folders:
                            logger.info(f"Processing target folder: '{target_folder_name}'")
                            
                            if target_folder_name.lower() == "projects":
                                # Special handling for Projects - process each project folder completely
                                await self._process_projects_folder_by_folder(site_id, drive_id, documents, subfolder_filter, drive_name)
                            else:
                                # Find and process other folders
                                target_folder_id = await self._find_folder_in_root(site_id, drive_id, target_folder_name)
                                
                                if target_folder_id:
                                    logger.info(f"Processing '{target_folder_name}' completely...")
                                    folder_documents = await self._process_folder_completely_recursive(
                                        site_id, drive_id, target_folder_id, target_folder_name,
                                        subfolder_filter, 0, 500, drive_name
                                    )
                                    documents.extend(folder_documents)
                                    logger.info(f"Completed '{target_folder_name}' - Got {len(folder_documents)} documents")
                                else:
                                    logger.warning(f"Target folder '{target_folder_name}' not found in drive {drive_name}")
                    else:
                        # Comprehensive scan - process all root folders completely
                        logger.info(f"Starting comprehensive scan of all folders in drive '{drive_name}'")
                        folder_documents = await self._process_all_folders_completely(
                            site_id, drive_id, subfolder_filter
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
            
            # CHECK FOR PLACEHOLDER CREATION - Do this BEFORE processing subfolders
            documents = []
            print(f"🔍 PLACEHOLDER CHECK: path='{path}' == 'Projects/219/219200': {path == 'Projects/219/219200'}")
            if path == "Projects/219/219200":  # Only for the main project folder
                print(f"🎯 MAIN FOLDER DETECTED: Creating placeholders for missing standard folders")
                
                # Get the existing folder items in this directory
                endpoint = f"sites/{site_id}/drives/{drive_id}/items/{current_folder_id}/children"
                response = await self._make_request(endpoint)
                
                existing_items = response.get("value", [])
                existing_folder_names = {item.get("name", "") for item in existing_items if "folder" in item}
                
                print(f"📊 EXISTING PROJECT FOLDERS: {sorted(existing_folder_names)}")
                
                standard_folders = [
                    "01 Admin Documents", "02 Emails", "03 Phone Records", 
                    "04 Received", "05 Issued", "06 Calculations", 
                    "07 Drawings", "08 Reports & Specifications", "09 Photos", "10 Site Visits"
                ]
                
                for standard_folder in standard_folders:
                    if standard_folder not in existing_folder_names:
                        print(f"📁 MISSING: Creating placeholder for '{standard_folder}' (not in SharePoint)")
                        # Create a placeholder folder entry for missing standard folders
                        placeholder_entry = {
                            "type": "folder",
                            "name": standard_folder,
                            "full_path": f"{path}/{standard_folder}",
                            "folder_path": path,
                            "project_id": "219200",
                            "folder_category": f"Standard_{standard_folder.split()[0]}",
                            "last_modified": "2025-08-10T18:30:00Z",
                            "child_count": 0,
                            "is_folder": True,
                            "is_placeholder": True,
                            "site_id": site_id,
                            "drive_id": drive_id,
                            "drive_name": drive_name
                        }
                        documents.append(placeholder_entry)
                        print(f"📁 DEBUG: Created PLACEHOLDER folder entry for '{path}/{standard_folder}'")
                        
                print(f"✅ PLACEHOLDER CHECK COMPLETE: Created {len(documents)} placeholder folders")
            
            # Now process the actual folder contents
            folder_documents = await self._process_folder_completely_recursive(
                site_id, drive_id, current_folder_id, path, None, 0, max_documents=200, drive_name=drive_name
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

    async def _process_single_project_completely(self, site_id: str, drive_id: str, 
                                               projects_folder_id: str, project_folder_name: str,
                                               subfolder_filter: str = None, drive_name: str = "Unknown") -> List[Dict[str, Any]]:
        """
        Process ONE project folder completely to the very bottom before moving to next.
        This processes the entire project folder tree completely.
        """
        documents = []
        
        try:
            logger.info(f"Starting COMPLETE processing of project '{project_folder_name}'")
            
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
            
            # Process this ONE project completely - go to the very bottom
            project_path = f"Projects/{project_folder_name}"
            project_docs = await self._process_folder_completely_recursive(
                site_id, drive_id, project_folder_id, project_path, subfolder_filter, 0, 500, drive_name
            )
            
            documents.extend(project_docs)
            
            logger.info(f"COMPLETED project '{project_folder_name}' - Total documents: {len(project_docs)}")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to process project '{project_folder_name}' completely", error=str(e))
            return documents

    async def _process_folder_completely_recursive(self, site_id: str, drive_id: str, folder_id: str,
                                                  folder_path: str, subfolder_filter: str = None, 
                                                  depth: int = 0, max_documents: int = 500, drive_name: str = "Unknown") -> List[Dict[str, Any]]:
        """
        Process a folder completely and recursively with limits to prevent timeouts.
        This processes files and subfolders but stops at reasonable limits.
        """
        documents = []
        
        try:
            indent = "  " * depth
            logger.info(f"{indent}Processing folder: {folder_path} (depth {depth}, max_docs: {max_documents})")
            
            # Stop if we have enough documents or are too deep
            if len(documents) >= max_documents or depth > 8:
                logger.info(f"{indent}Stopping - reached limits (docs: {len(documents)}, depth: {depth})")
                return documents
            
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
            
            # CREATE FOLDER ENTRIES for all subfolders (even empty ones)
            for subfolder_item in subfolders_in_folder:
                subfolder_name = subfolder_item.get("name", "")
                subfolder_path = f"{folder_path}/{subfolder_name}"
                
                # Skip problematic folders only
                if self._should_skip_folder(subfolder_path, subfolder_name):
                    continue
                    
                # Create a folder entry so it appears in blob storage
                folder_entry = await self._create_folder_entry(
                    site_id, drive_id, subfolder_item, folder_path, drive_name
                )
                if folder_entry:
                    documents.append(folder_entry)
                    print(f"📁 DEBUG: Created folder entry for '{subfolder_path}'")
            
            # Process files first (they're most important)
            for file_item in files_in_folder:
                if len(documents) >= max_documents:
                    logger.info(f"{indent}Reached document limit, stopping file processing")
                    break
                    
                document = await self._create_document_entry(
                    site_id, drive_id, file_item, folder_path, subfolder_filter, drive_name
                )
                if document:
                    documents.append(document)
            
            logger.info(f"{indent}Processed {len(files_in_folder)} files in {folder_path}")
            
            # Process subfolders (limit to prevent endless traversal)
            processed_subfolders = 0
            max_subfolders = 20  # Limit subfolders per level
            
            for subfolder_item in subfolders_in_folder:
                if len(documents) >= max_documents or processed_subfolders >= max_subfolders:
                    logger.info(f"{indent}Stopping subfolder processing - limits reached")
                    break
                    
                subfolder_name = subfolder_item.get("name", "")
                subfolder_path = f"{folder_path}/{subfolder_name}"
                
                # Skip problematic folders only
                if self._should_skip_folder(subfolder_path, subfolder_name):
                    logger.info(f"{indent}Skipping problematic folder: {subfolder_path}")
                    continue
                
                logger.info(f"{indent}Going deeper into: {subfolder_name}")
                
                # Recursively process this subfolder with remaining document budget
                remaining_docs = max_documents - len(documents)
                subfolder_docs = await self._process_folder_completely_recursive(
                    site_id, drive_id, subfolder_item["id"], subfolder_path,
                    subfolder_filter, depth + 1, remaining_docs, drive_name
                )
                
                documents.extend(subfolder_docs)
                processed_subfolders += 1
                logger.info(f"{indent}Completed subfolder '{subfolder_name}' - got {len(subfolder_docs)} documents")
            
            logger.info(f"{indent}COMPLETED {folder_path} - Total: {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to process folder {folder_path} completely", error=str(e))
            return documents

    async def _process_projects_folder_by_folder(self, site_id: str, drive_id: str, 
                                               documents: List[Dict], subfolder_filter: str = None, drive_name: str = "Unknown"):
        """
        Process Projects folder by going through each project folder completely.
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
                    site_id, drive_id, projects_folder_id, project_name, subfolder_filter, drive_name
                )
                
                documents.extend(project_docs)
                
                logger.info(f"COMPLETED project '{project_name}' - Got {len(project_docs)} documents. Total so far: {len(documents)}")
            
        except Exception as e:
            logger.error("Failed to process Projects folder by folder", error=str(e))

    async def _process_all_folders_completely(self, site_id: str, drive_id: str,
                                            subfolder_filter: str = None, drive_name: str = "Unknown") -> List[Dict[str, Any]]:
        """Process all root folders completely - each folder to the very bottom."""
        documents = []
        
        try:
            # Get all root folders
            root_response = await self._make_request(f"sites/{site_id}/drives/{drive_id}/root/children")
            root_items = root_response.get("value", [])
            
            root_folders = [item for item in root_items if "folder" in item]
            logger.info(f"Found {len(root_folders)} root folders to process completely")
            
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
                    subfolder_filter, 0, 500, drive_name
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
        Support ALL files - no filtering based on content or file type.
        User wants all files to be included in the system.
        """
        # Include ALL files - no restrictions
        return True
    
    def _is_photos_folder(self, full_path: str) -> bool:
        """
        Support ALL files including photos - user wants everything.
        """
        return False  # Don't skip any folders, include photos too


async def get_graph_client() -> MicrosoftGraphClient:
    """Dependency injection for Microsoft Graph client."""
    return MicrosoftGraphClient()
