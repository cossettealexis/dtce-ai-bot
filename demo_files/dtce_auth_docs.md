# DTCE Authentication Service Documentation

## Overview
This document outlines the authentication service used across DTCE engineering projects.

## Database Configuration
We use PostgreSQL for user authentication with the following setup:

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Security Requirements
- All endpoints require JWT authentication
- Tokens expire after 24 hours
- Refresh tokens valid for 7 days
- Rate limiting: 100 requests per minute per user

## Deployment Guidelines
1. Deploy to staging first
2. Run integration tests
3. Require two approvals for production
4. Monitor for 24 hours after deployment

## Python Authentication Helper
```python
def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
```
