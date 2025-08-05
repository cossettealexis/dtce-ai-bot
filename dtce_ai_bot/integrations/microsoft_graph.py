"""
Microsoft Graph API integration for Suitefiles/SharePoint document access.
Implements authentication and file retrieval from SharePoint sites.
"""

import os
from typing import List, Dict, Any, Optional
import asyncio
import aiohttp
import structlog
from azure.identity.aio import ClientSecretCredential
from ..config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class MicrosoftGraphClient:
    """Client for Microsoft Graph API to access SharePoint/Suitefiles."""
    
    def __init__(self):
        self.tenant_id = settings.MICROSOFT_TENANT_ID
        self.client_id = settings.MICROSOFT_CLIENT_ID
        self.client_secret = settings.MICROSOFT_CLIENT_SECRET
        self.base_url = "https://graph.microsoft.com/v1.0"
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
        
        token = await self._credential.get_token("https://graph.microsoft.com/.default")
        return token.token
    
    async def _make_request(self, endpoint: str, method: str = "GET") -> Dict[str, Any]:
        """Make authenticated request to Microsoft Graph API."""
        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/{endpoint}"
        
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
    
    async def get_files_in_drive(self, site_id: str, drive_id: str, folder_path: str = "") -> List[Dict[str, Any]]:
        """Get files from a specific drive/document library."""
        try:
            if folder_path:
                endpoint = f"sites/{site_id}/drives/{drive_id}/root:/{folder_path}:/children"
            else:
                endpoint = f"sites/{site_id}/drives/{drive_id}/root/children"
            
            logger.info("Fetching files from drive", site_id=site_id, drive_id=drive_id, folder_path=folder_path)
            response = await self._make_request(endpoint)
            items = response.get("value", [])
            
            # Filter to only files (not folders)
            files = [item for item in items if "file" in item]
            logger.info("Retrieved files", count=len(files), drive_id=drive_id)
            return files
        except Exception as e:
            logger.error("Failed to get files from drive", drive_id=drive_id, error=str(e))
            raise
    
    async def download_file(self, site_id: str, drive_id: str, file_id: str) -> bytes:
        """Download file content from SharePoint."""
        try:
            endpoint = f"sites/{site_id}/drives/{drive_id}/items/{file_id}/content"
            logger.info("Downloading file", file_id=file_id)
            
            access_token = await self._get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            url = f"{self.base_url}/{endpoint}"
            
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
        Main method to sync documents from Suitefiles.
        This is what gets called to pull files from SharePoint/Suitefiles.
        """
        try:
            logger.info("Starting Suitefiles document sync")
            
            # Find the Suitefiles site (adjust name as needed)
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
                
                logger.info("Processing drive", drive_id=drive_id, name=drive_name)
                
                # Get files from this drive
                files = await self.get_files_in_drive(site_id, drive_id)
                
                for file in files:
                    # Filter for document types we can process
                    file_name = file.get("name", "")
                    if any(file_name.lower().endswith(ext) for ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.md']):
                        documents.append({
                            "site_id": site_id,
                            "drive_id": drive_id,
                            "file_id": file["id"],
                            "name": file_name,
                            "size": file.get("size", 0),
                            "modified": file.get("lastModifiedDateTime"),
                            "download_url": file.get("@microsoft.graph.downloadUrl"),
                            "drive_name": drive_name,
                            "mime_type": file.get("file", {}).get("mimeType", "")
                        })
            
            logger.info("Suitefiles sync completed", total_documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to sync Suitefiles documents", error=str(e))
            raise


async def get_graph_client() -> MicrosoftGraphClient:
    """Dependency injection for Microsoft Graph client."""
    return MicrosoftGraphClient()
