"""
Azure Storage dependency injection for FastAPI.
"""

from datetime import datetime, timedelta

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

from ..config.settings import get_settings


def get_storage_client() -> BlobServiceClient:
    """Get Azure Blob Storage client."""
    settings = get_settings()
    return BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)


def get_blob_sas_url(
    storage_client: BlobServiceClient, container_name: str, blob_name: str
) -> str:
    """Generate a SAS URL for a specific blob."""
    try:
        # The account key is not directly exposed on the client, but we can get it from the credential object
        # This assumes the client was created with a connection string or account key.
        account_key = storage_client.credential.account_key
        if not account_key:
            raise ValueError("BlobServiceClient was not initialized with an account key.")

        sas_token = generate_blob_sas(
            account_name=storage_client.account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1),  # Token is valid for 1 hour
        )

        url = f"https://{storage_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
        return url
    except Exception as e:
        print(f"Error generating SAS URL for {blob_name}: {e}")
        return ""
