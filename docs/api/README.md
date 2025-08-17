# API Documentation

This directory contains comprehensive API documentation for the DTCE AI Bot backend service.

## Available Documentation

### Endpoint References
- [Document Sync API](./document-sync.md) - Document synchronization endpoints and operations
- [Chat API](./chat.md) - Chat and conversation management endpoints
- [Health Check API](./health.md) - System health and monitoring endpoints

### API Standards
- [Authentication](./authentication.md) - API authentication and authorization
- [Error Handling](./error-handling.md) - Standard error responses and codes
- [Rate Limiting](./rate-limiting.md) - API rate limits and usage guidelines

## Quick Reference

### Base URL
```
https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net
```

### Core Endpoints
- `GET /` - Health check and API information
- `POST /sync-suitefiles-async` - Asynchronous document synchronization
- `POST /chat` - Process chat messages and queries
- `GET /docs` - Interactive API documentation (Swagger/OpenAPI)

### Authentication
All API endpoints require proper authentication headers. See [Authentication documentation](./authentication.md) for details.

## Response Formats

All API responses follow a consistent JSON structure:

```json
{
  "status": "success|error",
  "message": "Human readable message",
  "data": {},
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Getting Started

1. Review the [Setup Guide](../SETUP.md) for environment configuration
2. Check the [Authentication documentation](./authentication.md) for API access
3. Use the interactive documentation at `/docs` for testing endpoints
4. Follow the [Development Guide](../DEVELOPMENT.md) for local development

For more information, see the main [README](../../README.md) in the project root.
