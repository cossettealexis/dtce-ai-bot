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
    microsoft_app_id: str
    microsoft_app_password: str
    microsoft_app_tenant_id: str
    
    # Microsoft Graph API settings
    microsoft_client_id: str
    microsoft_tenant_id: str
    microsoft_client_secret: str
    sharepoint_site_id: str
    
    # Azure Storage settings
    azure_storage_connection_string: str
    azure_storage_container_name: str = "dtce-documents"
    
    # Azure Cognitive Search settings
    azure_search_service_name: str
    azure_search_admin_key: str
    azure_search_index_name: str = "dtce-documents-index"
    
    # Azure OpenAI settings
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment_name: str = "gpt-4"
    azure_openai_api_version: str = "2024-02-01"
    
    # Processing settings
    max_file_size_mb: int = 10
    supported_file_types: List[str] = [".pdf", ".docx", ".txt", ".md", ".py", ".js", ".ts"]
    max_concurrent_processing: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
