"""
SuiteFiles URL utility for converting Azure blob URLs to SharePoint SuiteFiles links.
Follows SOLID principles by providing a single responsibility for URL conversion.
"""

import re
from typing import Optional
from urllib.parse import unquote, quote
import structlog

logger = structlog.get_logger(__name__)


class SuiteFilesUrlConverter:
    """Handles conversion of Azure blob URLs to SharePoint SuiteFiles URLs."""
    
    def __init__(self):
        # SharePoint site configuration
        self.sharepoint_base = "https://donthomson.sharepoint.com"
        self.site_path = "/sites/suitefiles"
        
    def convert_blob_to_suitefiles_url(self, blob_url: str, link_type: str = "file", folder_path: str = None, filename: str = None) -> Optional[str]:
        """
        Convert Azure blob URL to SharePoint SuiteFiles URL.
        
        Args:
            blob_url: Azure blob storage URL
            link_type: Type of link ('file' for direct file, 'folder' for folder view)
            folder_path: Optional folder path from search index (more accurate than blob URL path)
            filename: Optional filename from search index
            
        Returns:
            SharePoint SuiteFiles URL or None if conversion fails
        """
        if not blob_url:
            return None
            
        try:
            # If we have folder_path and filename from search index, use those (more accurate)
            if folder_path and filename:
                # Construct the SharePoint path from folder + filename
                if folder_path.endswith('/'):
                    clean_path = f"{folder_path}{filename}"
                else:
                    clean_path = f"{folder_path}/{filename}"
                logger.debug("Using folder_path + filename for SharePoint URL", 
                           folder_path=folder_path, filename=filename)
            else:
                # Fallback to extracting path from blob URL
                path_match = re.search(r'/(suitefiles|dtce-documents)/(.+)', blob_url, re.IGNORECASE)
                if not path_match:
                    logger.warning("No 'suitefiles' or 'dtce-documents' path found in blob URL", blob_url=blob_url)
                    return None
                    
                path_after_container = path_match.group(2)
                
                # Remove query parameters
                if "?" in path_after_container:
                    path_after_container = path_after_container.split("?")[0]
                    
                # URL decode the path
                clean_path = unquote(path_after_container)
                logger.debug("Using blob URL path for SharePoint URL", clean_path=clean_path)
            
            # Build SharePoint URL
            if link_type == "folder":
                # For folder view, remove the filename
                folder_path = "/".join(clean_path.split("/")[:-1])
                # URL encode the folder path for SharePoint
                encoded_folder_path = quote(folder_path, safe='/')
                sharepoint_url = f"{self.sharepoint_base}{self.site_path}/_layouts/15/onedrive.aspx?id=%2Fsites%2FSuiteFiles%2F{encoded_folder_path}&view=0"
            else:
                # For file viewer link - use SharePoint AppPages documents viewer format
                # This format works like: /sites/suitefiles/AppPages/documents.aspx#/path/to/file.pdf
                
                # URL encode the path components properly for SharePoint
                path_components = clean_path.split('/')
                encoded_components = [quote(component, safe='') for component in path_components]
                encoded_path = '/'.join(encoded_components)
                
                # Use the AppPages/documents.aspx format that opens files in browser
                sharepoint_url = f"{self.sharepoint_base}{self.site_path}/AppPages/documents.aspx#/{encoded_path}"
                
            logger.debug("Successfully converted blob URL to SuiteFiles URL", 
                        blob_url=blob_url, sharepoint_url=sharepoint_url)
            return sharepoint_url
            
        except Exception as e:
            logger.error("Failed to convert blob URL to SuiteFiles URL", 
                        blob_url=blob_url, error=str(e))
            return None
    
    def get_safe_suitefiles_url(self, blob_url: str, link_type: str = "file", folder_path: str = None, filename: str = None) -> Optional[str]:
        """
        Get SuiteFiles URL with fallback to original blob URL if conversion fails.
        
        Args:
            blob_url: Azure blob storage URL
            link_type: Type of link ('file' for direct file, 'folder' for folder view)
            folder_path: Optional folder path from search index
            filename: Optional filename from search index
            
        Returns:
            SharePoint SuiteFiles URL or original blob URL as fallback
        """
        if not blob_url:
            return None
            
        suitefiles_url = self.convert_blob_to_suitefiles_url(blob_url, link_type, folder_path, filename)
        
        if suitefiles_url:
            return suitefiles_url
        else:
            logger.warning("Using blob URL as fallback for SuiteFiles conversion", blob_url=blob_url)
            return blob_url
    
    def extract_project_info_from_url(self, blob_url: str) -> dict:
        """
        Extract project information from blob URL.
        
        Args:
            blob_url: Azure blob storage URL
            
        Returns:
            Dictionary with project information (project_number, year, etc.)
        """
        if not blob_url:
            return {}
            
        try:
            # Look for Projects folder pattern
            projects_match = re.search(r'/Projects?/(.+)', blob_url, re.IGNORECASE)
            if not projects_match:
                return {}
                
            path_after_projects = projects_match.group(1)
            
            # Remove query parameters and decode
            if "?" in path_after_projects:
                path_after_projects = path_after_projects.split("?")[0]
            path_after_projects = unquote(path_after_projects)
            
            # Split path segments
            path_segments = [seg for seg in path_after_projects.split('/') if seg]
            
            project_info = {}
            
            if len(path_segments) >= 2:
                # First segment is usually year folder (e.g., "225")
                year_folder = path_segments[0]
                project_folder = path_segments[1]
                
                # Map year folders to actual years
                year_mapping = {
                    "225": "2025", "224": "2024", "223": "2023",
                    "222": "2022", "221": "2021", "220": "2020"
                }
                
                project_info = {
                    "year_folder": year_folder,
                    "year": year_mapping.get(year_folder, ""),
                    "project_folder": project_folder,
                    "full_path": path_after_projects
                }
                
            return project_info
            
        except Exception as e:
            logger.error("Failed to extract project info from URL", 
                        blob_url=blob_url, error=str(e))
            return {}


# Singleton instance for easy import
suitefiles_converter = SuiteFilesUrlConverter()
