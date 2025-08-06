"""
Application settings and configuration.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # Application settings
    app_name: str = "DTCE AI Assistant"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    environment: str = "development"
    
    # FastAPI settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    cors_origins: List[str] = ["*"]
    
    # Microsoft Bot Framework settings
    microsoft_app_id: str = ""
    microsoft_app_password: str = ""
    microsoft_app_tenant_id: str = ""
    microsoft_app_type: str = "MultiTenant"
    
    # Microsoft Graph API settings
    microsoft_client_id: str = ""
    microsoft_tenant_id: str = ""
    microsoft_client_secret: str = ""
    sharepoint_site_id: str = ""
    sharepoint_scopes: str = "Sites.Read.All,Files.Read.All"
    
    @property
    def MICROSOFT_CLIENT_ID(self) -> str:
        return self.microsoft_client_id
    
    @property
    def MICROSOFT_TENANT_ID(self) -> str:
        return self.microsoft_tenant_id
    
    @property
    def MICROSOFT_CLIENT_SECRET(self) -> str:
        return self.microsoft_client_secret
    
    @property
    def SHAREPOINT_SITE_ID(self) -> str:
        return self.sharepoint_site_id
    
    @property
    def OPENAI_API_KEY(self) -> str:
        return self.openai_api_key or self.azure_openai_api_key
    
    @property
    def AZURE_STORAGE_CONTAINER(self) -> str:
        return self.azure_storage_container
    
    # Azure Storage settings
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = "dtce-documents"
    
    # Azure Cognitive Search settings
    azure_search_service_name: str = ""
    azure_search_admin_key: str = ""
    azure_search_index_name: str = "dtce-documents-index"
    
    # Azure OpenAI settings
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment_name: str = "gpt-4"
    azure_openai_api_version: str = "2024-02-01"
    
    # OpenAI settings (alternative to Azure OpenAI)
    openai_api_key: str = ""
    openai_model_name: str = "gpt-4-turbo-preview"
    openai_max_tokens: int = 500
    openai_temperature: float = 0.1
    
    # Auto-update settings
    auto_sync_interval_hours: int = 1
    change_detection_enabled: bool = True
    real_time_indexing: bool = True
    
    # Azure Form Recognizer settings
    azure_form_recognizer_endpoint: str = ""
    azure_form_recognizer_key: str = ""
    
    # Microsoft Graph API URLs (centralized configuration)
    microsoft_graph_base_url: str = "https://graph.microsoft.com/v1.0"
    microsoft_login_authority_base: str = "https://login.microsoftonline.com"
    microsoft_graph_scope: str = "https://graph.microsoft.com/.default"
    
    # Azure Search URL template (centralized configuration)
    azure_search_base_url: str = "https://{service_name}.search.windows.net"
    
    # Storage container names
    azure_storage_container: str = "dtce-documents"
    
    # Processing settings
    max_file_size_mb: int = 10
    supported_file_types: List[str] = [".pdf", ".docx", ".txt", ".md", ".py", ".js", ".ts"]
    max_concurrent_processing: int = 5
    
    # Folder exclusion settings
    excluded_folders: List[str] = [
        "09_Photos", "Photos", "Christmas", "Awards", "Past events", 
        "Company Culture", "Workplace Essentials", "Trash", "00_Superseded",
        "0_SS", "00_SS", "Superseded", "Archive", "0_Archive"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
