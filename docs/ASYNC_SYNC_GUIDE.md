# 🚀 Async Sync Job Usage Guide

## Problem Solved
**Manual sync timeout issue fixed!** No more 504 Gateway Timeout errors when syncing large document sets.

## How It Works

### 🎯 **Start Sync Job** (Returns Immediately)
```bash
curl -X POST "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/documents/sync-async/start" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "Projects/219",
    "description": "Sync project 219 documents"
  }'
```

**Response:**
```json
{
  "status": "success",
  "job_id": "abc-123-def",
  "job_status": "running",
  "description": "Sync project 219 documents",
  "monitor_url": "/documents/sync-async/status/abc-123-def"
}
```

### 📊 **Monitor Progress** (No Timeout)
```bash
curl "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/documents/sync-async/status/abc-123-def"
```

**Response:**
```json
{
  "status": "success",
  "job_status": "running",
  "progress": {
    "percentage": 45.2,
    "processed_files": 226,
    "total_files": 500,
    "current_file": "project_report.pdf",
    "estimated_remaining_minutes": 12.5
  },
  "recent_logs": [
    "Found 500 documents to process",
    "Processed 200/500 files",
    "Processed 220/500 files"
  ]
}
```

## 📋 **Usage Examples**

### **Full Sync** (All Documents)
```bash
curl -X POST ".../sync-async/start" \
  -H "Content-Type: application/json" \
  -d '{"description": "Full document sync"}'
```

### **Project-Specific Sync**
```bash
curl -X POST ".../sync-async/start" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "Projects/219",
    "description": "Project 219 sync"
  }'
```

### **Engineering Documents Only**
```bash
curl -X POST ".../sync-async/start" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "Engineering",
    "description": "Engineering docs sync"
  }'
```

## 🎛️ **Management Commands**

### **List All Jobs**
```bash
curl "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/documents/sync-async/jobs"
```

### **Cancel Running Job**
```bash
curl -X POST "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/documents/sync-async/cancel/abc-123-def"
```

## 🔍 **Job Status Values**

- **`pending`** - Job created, waiting to start
- **`running`** - Currently processing documents
- **`completed`** - Successfully finished
- **`failed`** - Error occurred during processing
- **`cancelled`** - Manually cancelled

## ⚡ **Benefits**

1. **✅ No Timeout Issues** - Start sync and monitor progress separately
2. **📊 Real-time Progress** - See exactly what's happening
3. **🔄 Background Processing** - Doesn't block other operations
4. **📝 Detailed Logging** - Track what files are being processed
5. **⏱️ Time Estimates** - Know how long remaining
6. **🛑 Cancellation Support** - Stop long-running jobs if needed

## 🎯 **Perfect for Your Workflow**

- **Manual Sync**: Start job when you need fresh documents
- **Progress Monitoring**: Check progress anytime without timeout
- **Periodic Maintenance**: Set up scheduled jobs for regular updates
- **Troubleshooting**: Detailed logs help identify any issues

**No more waiting for timeouts - start your sync and monitor it safely!** 🚀
