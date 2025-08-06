import requests
import asyncio
from typing import List, Dict, Any, Optional
from msal import PublicClientApplication, ConfidentialClientApplication
import structlog
from datetime import datetime, timezone

from ...config.settings import Settings
from ...models.documents import DocumentMetadata, DocumentType

logger = structlog.get_logger(__name__)


class SharePointClient:
    """Client for interacting with SharePoint via Microsoft Graph API."""
    
    def __init__(self):
        self.settings = Settings()
        self.client_id = self.settings.microsoft_client_id
        self.tenant_id = self.settings.microsoft_tenant_id
        self.client_secret = self.settings.microsoft_client_secret
        self.site_id = self.settings.sharepoint_site_id
        self.scopes = self.settings.sharepoint_scopes
        
        # Centralized URL configuration
        self.graph_base_url = self.settings.microsoft_graph_base_url
        self.authority = f"{self.settings.microsoft_login_authority_base}/{self.tenant_id}"
        self.graph_scope = self.settings.microsoft_graph_scope
        
        self.access_token = None
        self.token_expires_at = None
        
        # Use client credentials flow if client secret is provided, otherwise device flow
        if self.client_secret:
            self.app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=self.authority
            )
        else:
            self.app = PublicClientApplication(
                client_id=self.client_id,
                authority=self.authority
            )
    
    async def authenticate(self) -> bool:
        """Authenticate with Microsoft Graph API."""
        try:
            if self.client_secret:
                # Client credentials flow (for production)
                result = self.app.acquire_token_for_client(scopes=[self.graph_scope])
            else:
                # Device flow (for development/testing)
                accounts = self.app.get_accounts()
                if accounts:
                    result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
                
                if not result:
                    flow = self.app.initiate_device_flow(scopes=self.scopes)
                    logger.info("Device flow authentication required", message=flow.get("message"))
                    result = self.app.acquire_token_by_device_flow(flow)
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                # Set expiration (default to 1 hour if not provided)
                expires_in = result.get("expires_in", 3600)
                self.token_expires_at = datetime.now(timezone.utc).timestamp() + expires_in
                logger.info("Successfully authenticated with Microsoft Graph API")
                return True
            else:
                logger.error("Authentication failed", error=result.get("error_description"))
                return False
                
        except Exception as e:
            logger.error("Authentication error", error=str(e))
            return False
    
    def _is_token_valid(self) -> bool:
        """Check if the current access token is still valid."""
        if not self.access_token or not self.token_expires_at:
            return False
        
        # Consider token expired if it expires in the next 5 minutes
        current_time = datetime.now(timezone.utc).timestamp()
        return current_time < (self.token_expires_at - 300)
    
    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token."""
        if not self._is_token_valid():
            return await self.authenticate()
        return True
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def list_folder_contents(self, folder_path: str) -> List[Dict[str, Any]]:
        """List contents of a specific folder in SharePoint."""
        if not await self._ensure_authenticated():
            raise Exception("Failed to authenticate with SharePoint")
        
        # Construct the Graph API URL using centralized base URL
        url = f"{self.graph_base_url}/sites/{self.site_id}/drive/root:/{folder_path}:/children"
        
        headers = self._get_headers()
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get("value", [])
            
        except requests.exceptions.RequestException as e:
            logger.error("Failed to list folder contents", folder=folder_path, error=str(e))
            raise
    
    async def get_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific file."""
        if not await self._ensure_authenticated():
            raise Exception("Failed to authenticate with SharePoint")
        
        url = f"{self.graph_base_url}/sites/{self.site_id}/drive/root:/{file_path}"
        headers = self._get_headers()
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error("Failed to get file metadata", file=file_path, error=str(e))
            return None
    
    async def download_file_content(self, download_url: str) -> Optional[bytes]:
        """Download file content from SharePoint."""
        if not await self._ensure_authenticated():
            raise Exception("Failed to authenticate with SharePoint")
        
        headers = self._get_headers()
        
        try:
            response = requests.get(download_url, headers=headers)
            response.raise_for_status()
            return response.content
            
        except requests.exceptions.RequestException as e:
            logger.error("Failed to download file", url=download_url, error=str(e))
            return None
    
    def _extract_project_id(self, folder_path: str) -> Optional[str]:
        """Extract project ID from folder path."""
        # Look for project numbers (219, 220, etc.) in the path
        import re
        match = re.search(r'/Projects?/(\d+)', folder_path, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _determine_document_type(self, folder_path: str) -> DocumentType:
        """Determine document type based on folder path."""
        path_lower = folder_path.lower()
        
        if "01_fees" in path_lower or "invoice" in path_lower:
            return DocumentType.FEES_INVOICES
        elif "02_email" in path_lower:
            return DocumentType.EMAILS
        elif "03_for_internal" in path_lower or "internal_review" in path_lower:
            return DocumentType.INTERNAL_REVIEW
        elif "04_received" in path_lower:
            return DocumentType.RECEIVED
        elif "05_issued" in path_lower:
            return DocumentType.ISSUED
        elif "06_calculation" in path_lower:
            return DocumentType.CALCULATIONS
        elif "07_drawing" in path_lower:
            return DocumentType.DRAWINGS
        elif "08_report" in path_lower or "specification" in path_lower:
            return DocumentType.REPORTS_SPECS
        elif "09_photo" in path_lower:
            return DocumentType.PHOTOS
        elif "10_site" in path_lower or "meeting" in path_lower:
            return DocumentType.SITE_NOTES
        elif "engineering" in path_lower:
            return DocumentType.ENGINEERING
        else:
            return DocumentType.OTHER
    
    def _convert_to_document_metadata(self, file_data: Dict[str, Any], folder_path: str) -> DocumentMetadata:
        """Convert SharePoint file data to DocumentMetadata."""
        
        # Extract basic file information
        file_name = file_data.get("name", "")
        file_size = file_data.get("size", 0)
        
        # Parse dates
        modified_date = datetime.fromisoformat(
            file_data.get("lastModifiedDateTime", "").replace("Z", "+00:00")
        )
        created_date = None
        if "createdDateTime" in file_data:
            created_date = datetime.fromisoformat(
                file_data["createdDateTime"].replace("Z", "+00:00")
            )
        
        # Get file extension
        file_type = ""
        if "." in file_name:
            file_type = "." + file_name.split(".")[-1].lower()
        
        # Construct full path
        full_path = f"{folder_path}/{file_name}" if folder_path else file_name
        
        # Get download URL
        download_url = file_data.get("@microsoft.graph.downloadUrl")
        sharepoint_url = file_data.get("webUrl", "")
        
        return DocumentMetadata(
            file_id=file_data.get("id", ""),
            file_name=file_name,
            file_path=full_path,
            file_size=file_size,
            file_type=file_type,
            modified_date=modified_date,
            created_date=created_date,
            sharepoint_url=sharepoint_url,
            download_url=download_url,
            project_id=self._extract_project_id(full_path),
            document_type=self._determine_document_type(full_path),
            folder_path=folder_path
        )
    
    async def scan_engineering_folders(self) -> List[DocumentMetadata]:
        """Scan all Engineering and Projects folders for documents."""
        all_documents = []
        
        for target_folder in self.settings.target_folders:
            logger.info("Scanning folder", folder=target_folder)
            
            try:
                if target_folder.lower() == "projects":
                    # Scan each project folder individually
                    projects_content = await self.list_folder_contents("Projects")
                    
                    for item in projects_content:
                        if item.get("folder") and item["name"].isdigit():
                            project_number = item["name"]
                            logger.info("Scanning project", project=project_number)
                            
                            project_docs = await self._scan_project_folder(f"Projects/{project_number}")
                            all_documents.extend(project_docs)
                else:
                    # Scan Engineering folder
                    engineering_docs = await self._scan_folder_recursively(target_folder)
                    all_documents.extend(engineering_docs)
                    
            except Exception as e:
                logger.error("Failed to scan folder", folder=target_folder, error=str(e))
        
        logger.info("Completed folder scan", total_documents=len(all_documents))
        return all_documents
    
    async def _scan_project_folder(self, project_path: str) -> List[DocumentMetadata]:
        """Scan a specific project folder, excluding photos."""
        documents = []
        
        try:
            project_contents = await self.list_folder_contents(project_path)
            
            for item in project_contents:
                folder_name = item.get("name", "")
                
                # Skip photos folder
                if any(excluded in folder_name for excluded in self.settings.excluded_folders):
                    logger.debug("Skipping excluded folder", folder=folder_name)
                    continue
                
                if item.get("folder"):
                    # Recursively scan subfolder
                    subfolder_path = f"{project_path}/{folder_name}"
                    subfolder_docs = await self._scan_folder_recursively(subfolder_path)
                    documents.extend(subfolder_docs)
                else:
                    # Process file if it's a supported type
                    if self._is_supported_file(item):
                        doc_metadata = self._convert_to_document_metadata(item, project_path)
                        documents.append(doc_metadata)
        
        except Exception as e:
            logger.error("Failed to scan project folder", project=project_path, error=str(e))
        
        return documents
    
    async def _scan_folder_recursively(self, folder_path: str) -> List[DocumentMetadata]:
        """Recursively scan a folder for documents."""
        documents = []
        
        try:
            folder_contents = await self.list_folder_contents(folder_path)
            
            for item in folder_contents:
                if item.get("folder"):
                    # Recursively scan subfolder
                    subfolder_name = item.get("name", "")
                    subfolder_path = f"{folder_path}/{subfolder_name}"
                    
                    # Skip excluded folders
                    if any(excluded in subfolder_name for excluded in self.settings.excluded_folders):
                        continue
                    
                    subfolder_docs = await self._scan_folder_recursively(subfolder_path)
                    documents.extend(subfolder_docs)
                else:
                    # Process file if supported
                    if self._is_supported_file(item):
                        doc_metadata = self._convert_to_document_metadata(item, folder_path)
                        documents.append(doc_metadata)
        
        except Exception as e:
            logger.error("Failed to scan folder recursively", folder=folder_path, error=str(e))
        
        return documents
    
    def _is_supported_file(self, file_data: Dict[str, Any]) -> bool:
        """Check if file is a supported type and size."""
        file_name = file_data.get("name", "")
        file_size = file_data.get("size", 0)
        
        # Check file extension
        if not any(file_name.lower().endswith(ext) for ext in self.settings.supported_file_types):
            return False
        
        # Check file size (convert MB to bytes)
        max_size_bytes = self.settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            logger.warning("File too large, skipping", file=file_name, size_mb=file_size/1024/1024)
            return False
        
        return True
