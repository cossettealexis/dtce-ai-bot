# Document Synchronization API

The Document Sync API provides endpoints for synchronizing documents from Microsoft SharePoint and OneDrive with the DTCE AI Bot knowledge base.

## Endpoints

### Asynchronous Document Sync

**POST** `/sync-suitefiles-async`

Initiates asynchronous synchronization of documents from specified SharePoint/OneDrive locations.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `force` | boolean | No | `false` | Force re-sync all files even if they appear up-to-date |

#### Request Example

```bash
curl -X POST "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/sync-suitefiles-async?force=true" \
  -H "Authorization: Bearer your-token-here" \
  -H "Content-Type: application/json"
```

#### Response

**Success Response (202 Accepted)**
```json
{
  "status": "success",
  "message": "Document synchronization started",
  "data": {
    "task_id": "sync-task-12345",
    "started_at": "2024-01-01T10:00:00Z",
    "force_sync": true
  },
  "timestamp": "2024-01-01T10:00:00Z"
}
```

**Error Response (400 Bad Request)**
```json
{
  "status": "error",
  "message": "Invalid synchronization parameters",
  "error_code": "SYNC_INVALID_PARAMS",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

## Force Sync Behavior

When `force=true` is specified:

- **Bypasses modification date checks** - Files are processed regardless of last modified time
- **Re-processes all documents** - Documents that were previously skipped are included
- **Updates existing knowledge base entries** - Existing documents are re-analyzed and updated
- **Comprehensive sync** - All configured SharePoint/OneDrive locations are processed

### Use Cases for Force Sync

1. **Initial Setup** - When setting up the bot for the first time
2. **Configuration Changes** - After modifying sync settings or document processing rules
3. **Troubleshooting** - When documents appear missing from the knowledge base
4. **Manual Refresh** - Periodic full refresh to ensure data integrity

## Sync Process Flow

1. **Authentication** - Verify SharePoint/OneDrive access credentials
2. **Discovery** - Scan configured locations for documents
3. **Filtering** - Apply file type and size filters
4. **Processing** - Extract text content and metadata from documents
5. **Knowledge Base Update** - Store processed content in the vector database
6. **Completion** - Return sync status and statistics

## Supported File Types

- **Microsoft Office**: .docx, .xlsx, .pptx
- **PDF Documents**: .pdf
- **Text Files**: .txt, .md
- **Images with Text**: .png, .jpg (OCR processing)

## Configuration

Document sync behavior is controlled by environment variables:

```env
# SharePoint/OneDrive Configuration
SHAREPOINT_SITE_URL=https://your-tenant.sharepoint.com/sites/your-site
SHAREPOINT_CLIENT_ID=your-client-id
SHAREPOINT_CLIENT_SECRET=your-client-secret

# Sync Settings
MAX_FILE_SIZE_MB=50
SYNC_BATCH_SIZE=10
RETRY_ATTEMPTS=3
```

## Error Handling

Common error scenarios and their handling:

### Authentication Errors
- **401 Unauthorized**: Check SharePoint credentials
- **403 Forbidden**: Verify permissions to access documents

### Processing Errors
- **File Too Large**: Files exceeding size limits are skipped
- **Unsupported Format**: Unsupported file types are logged and skipped
- **Corruption**: Corrupted files are marked as failed

### Rate Limiting
- **429 Too Many Requests**: Automatic retry with exponential backoff
- **Throttling**: Respect SharePoint API rate limits

## Monitoring and Logging

Sync operations are logged with the following information:

- **Start/End Times**: Track sync duration
- **File Counts**: Number of files processed, skipped, and failed
- **Error Details**: Specific error messages for failed operations
- **Performance Metrics**: Processing speed and resource usage

## Best Practices

1. **Regular Sync**: Schedule regular syncs to keep content up-to-date
2. **Incremental Sync**: Use normal sync for routine updates, reserve force sync for special cases
3. **Monitor Logs**: Review sync logs regularly for errors or performance issues
4. **Test Configuration**: Validate SharePoint permissions and connectivity before production use

## Troubleshooting

### "No documents found to sync"

This error typically indicates:

1. **Permissions Issue**: Bot doesn't have access to the specified SharePoint location
2. **Configuration Error**: Incorrect SharePoint site URL or path
3. **Empty Location**: The specified folder contains no supported documents

**Solution**: Use `force=true` parameter to bypass caching and retry sync operations.

### Slow Sync Performance

To improve sync performance:

1. **Increase Batch Size**: Adjust `SYNC_BATCH_SIZE` environment variable
2. **Parallel Processing**: Enable concurrent document processing
3. **Filter File Types**: Restrict sync to essential document types only

For more troubleshooting information, see the [Setup Guide](../SETUP.md#troubleshooting).
