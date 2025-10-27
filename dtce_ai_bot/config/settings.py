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

    # Azure Search settings
    azure_search_service_endpoint: str = ""
    azure_search_service_name: str = ""
    azure_search_index_name: str = ""
    azure_search_api_key: str = ""
    azure_search_admin_key: str = ""

    # Azure OpenAI settings
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment_name: str = ""
    
    # Bot Framework settings (Microsoft App registration)
    microsoft_app_id: str = ""
    microsoft_app_password: str = ""  
    microsoft_app_tenant_id: str = ""
    microsoft_app_type: str = "SingleTenant"
    
    # Azure Bot Service uses different naming convention
    MicrosoftAppId: str = ""
    MicrosoftAppPassword: str = ""
    MicrosoftAppTenantId: str = ""
    MicrosoftAppType: str = "SingleTenant"
    
    @property
    def effective_app_id(self) -> str:
        """Get the Microsoft App ID from either naming convention."""
        return self.MicrosoftAppId or self.microsoft_app_id
    
    @property
    def effective_app_password(self) -> str:
        """Get the Microsoft App Password from either naming convention."""
        return self.MicrosoftAppPassword or self.microsoft_app_password
    
    @property
    def effective_app_tenant_id(self) -> str:
        """Get the Microsoft App Tenant ID from either naming convention."""
        return self.MicrosoftAppTenantId or self.microsoft_app_tenant_id
    
    @property
    def effective_app_type(self) -> str:
        """Get the Microsoft App Type from either naming convention."""
        return self.MicrosoftAppType or self.microsoft_app_type
    
    # DirectLine settings
    directline_secret: str = ""
    
    # Microsoft Graph API settings
    microsoft_client_id: str = ""
    microsoft_tenant_id: str = ""
    microsoft_client_secret: str = ""
    sharepoint_site_id: str = ""
    sharepoint_site_url: str = "https://donthomson.sharepoint.com/sites/suitefiles"
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
    def SHAREPOINT_SITE_URL(self) -> str:
        return self.sharepoint_site_url
    
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
    azure_search_service_endpoint: str = ""
    azure_search_index_name: str = "dtce-documents-index"
    azure_search_api_key: str = ""
    azure_search_api_version: str = "2023-11-01"
    
    # Azure OpenAI settings
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2023-12-01-preview"
    azure_openai_deployment_name: str = "gpt-4"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_embedding_model: str = "text-embedding-3-small"
    
    # Fallback OpenAI settings
    openai_api_key: str = ""
    
    # Document Intelligence settings
    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached instance of the application settings."""
    return Settings()
