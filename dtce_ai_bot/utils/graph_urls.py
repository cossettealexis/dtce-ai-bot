"""
URL builder for Microsoft Graph API and Azure service endpoints.
Centralizes all URL construction to make changes easier.
"""

from typing import Optional
from ..config.settings import get_settings

class UrlBuilder:
    """Helper class to build service URLs centrally."""
    
    def __init__(self):
        self.settings = get_settings()
    
    # Microsoft Graph URLs
    def graph_base_url(self) -> str:
        """Get Microsoft Graph base URL."""
        return self.settings.microsoft_graph_base_url
    
    def sites_url(self) -> str:
        """Get URL for listing sites."""
        return f"{self.graph_base_url()}/sites"
    
    def site_drives_url(self, site_id: str) -> str:
        """Get URL for listing drives in a site."""
        return f"{self.graph_base_url()}/sites/{site_id}/drives"
    
    def drive_root_children_url(self, site_id: str, drive_id: str) -> str:
        """Get URL for listing root children in a drive."""
        return f"{self.graph_base_url()}/sites/{site_id}/drives/{drive_id}/root/children"
    
    def drive_folder_children_url(self, site_id: str, drive_id: str, folder_path: str) -> str:
        """Get URL for listing children in a specific folder."""
        return f"{self.graph_base_url()}/sites/{site_id}/drives/{drive_id}/root:/{folder_path}:/children"
    
    def drive_file_content_url(self, site_id: str, drive_id: str, file_id: str) -> str:
        """Get URL for downloading file content."""
        return f"{self.graph_base_url()}/sites/{site_id}/drives/{drive_id}/items/{file_id}/content"
    
    def file_metadata_url(self, site_id: str, file_path: str) -> str:
        """Get URL for file metadata."""
        return f"{self.graph_base_url()}/sites/{site_id}/drive/root:/{file_path}"
    
    def search_sites_url(self, site_name: str) -> str:
        """Get URL for searching sites by name."""
        return f"{self.graph_base_url()}/sites?$filter=displayName eq '{site_name}'"
    
    def authority_url(self, tenant_id: str) -> str:
        """Get Microsoft login authority URL."""
        return f"{self.settings.microsoft_login_authority_base}/{tenant_id}"
    
    def graph_scope(self) -> str:
        """Get the default Graph API scope."""
        return self.settings.microsoft_graph_scope
    
    # Azure Search URLs
    def azure_search_endpoint(self, service_name: Optional[str] = None) -> str:
        """Get Azure Search endpoint URL."""
        service = service_name or self.settings.azure_search_service_name
        return self.settings.azure_search_base_url.format(service_name=service)


# Create singleton instances for easy import
urls = UrlBuilder()
graph_urls = urls  # Backward compatibility alias
