from azure.storage.blob import BlobServiceClient
from dtce_ai_bot.config.settings import get_settings
from dotenv import load_dotenv

load_dotenv()
settings = get_settings()

blob_service = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
container = blob_service.get_container_client("dtce-documents")

print("First 100 blobs:")
count = 0
for blob in container.list_blobs():
    print(f"  {blob.name}")
    count += 1
    if count >= 100:
        break
