# Templates Folder Sync - Safety Documentation

## Overview
This document explains the safety guarantees of syncing the Templates folder from SharePoint to Azure Blob Storage and Search Index.

## Source
- **SharePoint URL**: https://donthomson.sharepoint.com/sites/suitefiles/Templates/
- **Destination**: Azure Blob Storage `Templates/` folder
- **Purpose**: Make all DTCE template files searchable by the AI bot

## Safety Guarantees

### ✅ NO DELETIONS
- **The sync process NEVER deletes any files**
- It only adds new files or updates existing ones
- If a file is removed from SharePoint, it remains in blob storage
- This is by design to prevent accidental data loss

### ✅ PRESERVES STRUCTURE
- Maintains the exact folder hierarchy from SharePoint
- Template files keep their original paths
- Example: `Templates/Reports/PS1_Template.docx` stays as is

### ✅ NON-DESTRUCTIVE UPDATES
- Existing files are only overwritten if:
  - The SharePoint version is newer (based on modification date)
  - OR force sync is enabled
- Blob metadata is updated with each sync
- Original files are never corrupted

### ✅ ISOLATED SYNC
- Only affects the `Templates/` folder in blob storage
- Does NOT touch:
  - `Projects/` folder
  - `Engineering/` folder
  - `Policies/` folder
  - Any other existing folders

### ✅ INCREMENTAL SYNC
- By default, only syncs files that have changed
- Skips files that are already up-to-date
- Reduces sync time and resource usage

## How the Sync Works

### 1. Discovery Phase
```
SharePoint Templates/ → List all files → Compare with blob storage
```

### 2. Sync Phase
```
For each file:
  - Check if exists in blob storage
  - Check modification date
  - If new or modified → Download from SharePoint
  - Upload to blob storage with metadata
  - Extract text content
  - Index in Azure Search
```

### 3. Verification Phase
```
Query Azure Search for "template files" → Verify results
```

## Blob Storage Structure After Sync

```
azure-blob-storage/
└── dtce-documents/
    ├── Templates/              ← NEW: Templates from SharePoint
    │   ├── Reports/
    │   ├── Calculations/
    │   ├── Drawings/
    │   └── ... (all template files)
    ├── Projects/               ← UNCHANGED: Existing projects
    │   ├── 219/
    │   ├── 220/
    │   └── ...
    ├── Engineering/            ← UNCHANGED: Existing engineering docs
    └── Policies/               ← UNCHANGED: Existing policies
```

## Running the Sync

### Using the Script
```bash
cd /Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot
python scripts/sync_templates_folder.py
```

### Using the API Directly
```bash
curl -X POST "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/documents/sync-suitefiles?path=Templates&force=true"
```

### Using Python
```python
import requests

response = requests.post(
    "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/documents/sync-suitefiles",
    params={
        "path": "Templates",
        "force": True
    }
)

result = response.json()
print(f"Synced: {result['synced_count']} files")
print(f"Indexed: {result['ai_ready_count']} files")
```

## Code Safety Analysis

### DocumentSyncService Safety Features

#### 1. No Delete Operations
```python
# From document_sync_service.py
async def sync_documents(self, ...):
    # ONLY does: upload_blob(overwrite=True)
    # NEVER does: delete_blob() or delete_documents()
```

#### 2. Overwrite Only When Needed
```python
async def _should_skip_document(self, doc: Dict, blob_client, force_resync: bool):
    """Skip if file is already up-to-date"""
    if not force_resync:
        # Check modification dates
        if doc["modified"] <= blob_modified:
            return True  # Skip, already current
    return False
```

#### 3. Metadata Preservation
```python
metadata = {
    "source": sync_mode,
    "original_filename": doc["name"],
    "drive_name": doc["drive_name"],
    "full_path": doc.get("full_path", ""),
    # ... all metadata preserved
}
blob_client.upload_blob(file_content, overwrite=True, metadata=metadata)
```

## Testing the Templates

After syncing, test in Teams:

### General Template Queries
- "show me template files"
- "what templates do we have?"
- "list all templates"

### Specific Template Queries
- "find the PS1 template"
- "show me report templates"
- "where is the fee proposal template?"
- "do we have a structural calc template?"

### Template Type Queries
- "what templates are for drawings?"
- "show me calculation templates"
- "find email templates"

## Rollback (If Needed)

If something goes wrong, templates can be removed without affecting other folders:

```python
from azure.storage.blob import BlobServiceClient

# Connect to storage
storage_client = BlobServiceClient.from_connection_string(connection_string)
container_client = storage_client.get_container_client("dtce-documents")

# List Templates folder blobs only
blobs = container_client.list_blobs(name_starts_with="Templates/")

# Delete only Templates folder (if needed)
for blob in blobs:
    container_client.delete_blob(blob.name)
```

**Note**: This is ONLY for rollback. The sync itself never deletes.

## Intent Classification for Templates

The bot will recognize template queries through the intent detector:

```python
# From intent_detector_ai.py
if any(keyword in query_lower for keyword in ['template', 'form', 'spreadsheet']):
    intent = "Template_Document"
    filter = "folder eq 'Templates'"
```

## Conclusion

The Templates folder sync is:
- ✅ **Safe**: No deletions, no data loss
- ✅ **Isolated**: Only affects Templates folder
- ✅ **Reversible**: Can be rolled back if needed
- ✅ **Non-destructive**: Preserves existing structure
- ✅ **Incremental**: Only syncs changes

You can run it confidently without risk to existing data.
