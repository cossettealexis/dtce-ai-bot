# Security Guide - DTCE AI Assistant

## Overview

This comprehensive security guide covers security architecture, authentication, authorization, data protection, compliance, and security best practices for the DTCE AI Assistant. The application handles sensitive engineering documents and client data, requiring robust security measures at all layers.

## Security Architecture

### Security Principles
- **Zero Trust Architecture**: Never trust, always verify
- **Defense in Depth**: Multiple layers of security controls
- **Principle of Least Privilege**: Minimal necessary access rights
- **Data Classification**: Appropriate protection based on data sensitivity
- **Secure by Default**: Security built into every component

### Security Layers
1. **Network Security**: Azure Virtual Networks, NSGs, Application Gateway
2. **Application Security**: Authentication, authorization, input validation
3. **Data Security**: Encryption at rest and in transit, data classification
4. **Infrastructure Security**: Azure security features, monitoring, logging
5. **Operational Security**: Security monitoring, incident response, compliance

## Authentication and Authorization

### 1. Azure Active Directory Integration

#### App Registration Configuration
```json
{
  "appId": "your-app-id",
  "displayName": "DTCE AI Assistant",
  "signInAudience": "AzureADMyOrg",
  "requiredResourceAccess": [
    {
      "resourceAppId": "00000003-0000-0000-c000-000000000000",
      "resourceAccess": [
        {
          "id": "75359482-378d-4052-8f01-80520e7db3cd",
          "type": "Role"
        },
        {
          "id": "Sites.Read.All",
          "type": "Role"
        }
      ]
    }
  ],
  "web": {
    "redirectUris": [
      "https://dtceai-backend.azurewebsites.net/auth/callback"
    ]
  }
}
```

#### Authentication Implementation
```python
# dtce_ai_bot/auth/azure_auth.py
from azure.identity import ClientSecretCredential
from azure.core.exceptions import ClientAuthenticationError
import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

class AzureAuthenticator:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
    
    async def get_access_token(self, scope: str = "https://graph.microsoft.com/.default"):
        """Get access token for Microsoft Graph API"""
        try:
            token = await self.credential.get_token(scope)
            return token.token
        except ClientAuthenticationError as e:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
    
    def verify_jwt_token(self, token: str) -> dict:
        """Verify JWT token from Azure AD"""
        try:
            # Decode without verification for getting header
            header = jwt.get_unverified_header(token)
            
            # Get public key from Azure AD
            public_key = self._get_public_key(header['kid'])
            
            # Verify and decode token
            payload = jwt.decode(
                token, 
                public_key, 
                algorithms=['RS256'],
                audience=self.client_id,
                issuer=f"https://sts.windows.net/{self.tenant_id}/"
            )
            return payload
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    def _get_public_key(self, kid: str):
        """Get public key from Azure AD for token verification"""
        # Implementation to fetch public key from Azure AD
        pass

# Authentication dependency
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """FastAPI dependency for getting current authenticated user"""
    authenticator = get_azure_authenticator()
    payload = authenticator.verify_jwt_token(credentials.credentials)
    return {
        "user_id": payload.get("sub"),
        "email": payload.get("preferred_username"),
        "name": payload.get("name"),
        "roles": payload.get("roles", [])
    }
```

### 2. Role-Based Access Control (RBAC)

#### Role Definitions
```python
# dtce_ai_bot/auth/roles.py
from enum import Enum
from typing import List

class UserRole(Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    PROJECT_MANAGER = "project_manager"
    VIEWER = "viewer"

class Permission(Enum):
    READ_DOCUMENTS = "read_documents"
    SYNC_DOCUMENTS = "sync_documents"
    MANAGE_USERS = "manage_users"
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_DATA = "export_data"

ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.READ_DOCUMENTS,
        Permission.SYNC_DOCUMENTS,
        Permission.MANAGE_USERS,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_DATA
    ],
    UserRole.ENGINEER: [
        Permission.READ_DOCUMENTS,
        Permission.SYNC_DOCUMENTS,
        Permission.VIEW_ANALYTICS
    ],
    UserRole.PROJECT_MANAGER: [
        Permission.READ_DOCUMENTS,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_DATA
    ],
    UserRole.VIEWER: [
        Permission.READ_DOCUMENTS
    ]
}

def has_permission(user_roles: List[str], required_permission: Permission) -> bool:
    """Check if user has required permission"""
    for role_str in user_roles:
        try:
            role = UserRole(role_str)
            if required_permission in ROLE_PERMISSIONS.get(role, []):
                return True
        except ValueError:
            continue
    return False

# Permission decorator
def require_permission(permission: Permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user from request context
            user = kwargs.get('current_user') or get_current_user_from_context()
            if not has_permission(user.get('roles', []), permission):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

#### API Endpoint Protection
```python
# dtce_ai_bot/api/documents.py
from dtce_ai_bot.auth.azure_auth import get_current_user
from dtce_ai_bot.auth.roles import require_permission, Permission

@router.post("/sync-suitefiles")
@require_permission(Permission.SYNC_DOCUMENTS)
async def sync_documents(
    current_user: dict = Depends(get_current_user),
    path: Optional[str] = None,
    force: bool = False
):
    """Sync SharePoint documents - requires sync permission"""
    # Log security event
    security_logger.info(f"Document sync initiated by user {current_user['user_id']}")
    
    # Implementation...
    pass

@router.get("/search")
@require_permission(Permission.READ_DOCUMENTS)
async def search_documents(
    current_user: dict = Depends(get_current_user),
    q: str = None
):
    """Search documents - requires read permission"""
    # Apply data filtering based on user role/permissions
    # Implementation...
    pass
```

### 3. Teams Bot Authentication

#### Bot Framework Authentication
```python
# dtce_ai_bot/bot/auth_config.py
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity

class AuthConfig:
    def __init__(self, app_id: str, app_password: str):
        self.app_id = app_id
        self.app_password = app_password
        
        self.settings = BotFrameworkAdapterSettings(
            app_id=app_id,
            app_password=app_password,
            # Security settings
            auth_configuration=self._get_auth_configuration()
        )
    
    def _get_auth_configuration(self):
        """Configure authentication for Teams bot"""
        return {
            "ClaimsValidator": self._validate_claims,
            "RequireEndorsements": True,
            "EnableSkillsValidation": True
        }
    
    def _validate_claims(self, claims: dict) -> bool:
        """Validate incoming bot claims"""
        # Ensure requests come from Microsoft Teams
        valid_issuers = [
            "https://api.botframework.com",
            "https://sts.windows.net/72f988bf-86f1-41af-91ab-2d7cd011db47/"
        ]
        
        issuer = claims.get("iss")
        if issuer not in valid_issuers:
            return False
        
        # Additional validation logic
        return True

# Bot activity validation
async def validate_activity(activity: Activity) -> bool:
    """Validate incoming bot activity"""
    # Check channel ID
    if activity.channel_id != "msteams":
        return False
    
    # Validate service URL
    if not activity.service_url.startswith("https://smba.trafficmanager.net/"):
        return False
    
    return True
```

## Data Protection

### 1. Encryption

#### Data at Rest
```python
# dtce_ai_bot/security/encryption.py
from cryptography.fernet import Fernet
from azure.storage.blob import BlobServiceClient
import os

class DataEncryption:
    def __init__(self):
        # Use Azure Key Vault for key management
        self.encryption_key = self._get_encryption_key()
        self.fernet = Fernet(self.encryption_key)
    
    def _get_encryption_key(self) -> bytes:
        """Get encryption key from Azure Key Vault"""
        # In production, retrieve from Azure Key Vault
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            # Generate new key (for development only)
            key = Fernet.generate_key()
        return key.encode() if isinstance(key, str) else key
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data before storage"""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data after retrieval"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

# Azure Storage encryption configuration
def configure_storage_encryption():
    """Configure Azure Storage with customer-managed keys"""
    blob_service_client = BlobServiceClient(
        account_url="https://dtceaistorage.blob.core.windows.net/",
        credential="your-credential",
        # Enable encryption
        require_encryption=True,
        key_encryption_key="your-key-vault-key"
    )
    return blob_service_client
```

#### Data in Transit
```python
# dtce_ai_bot/security/tls_config.py
import ssl
from fastapi import FastAPI
import uvicorn

def configure_tls(app: FastAPI):
    """Configure TLS/SSL for API endpoints"""
    
    # Enforce HTTPS
    @app.middleware("http")
    async def force_https(request, call_next):
        if request.url.scheme != "https" and not request.url.hostname.startswith("localhost"):
            # Redirect to HTTPS
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=301)
        
        response = await call_next(request)
        
        # Security headers
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response

# SSL context for production
def create_ssl_context():
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain("path/to/cert.pem", "path/to/key.pem")
    return context
```

### 2. Data Classification and Handling

```python
# dtce_ai_bot/security/data_classification.py
from enum import Enum
from typing import Dict, Any
import re

class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class DataClassifier:
    def __init__(self):
        self.classification_rules = {
            DataClassification.RESTRICTED: [
                r"social security number",
                r"credit card",
                r"password",
                r"api[_\s]?key"
            ],
            DataClassification.CONFIDENTIAL: [
                r"financial",
                r"contract",
                r"proprietary",
                r"client[_\s]?data"
            ],
            DataClassification.INTERNAL: [
                r"employee",
                r"internal[_\s]?process",
                r"business[_\s]?plan"
            ]
        }
    
    def classify_document(self, content: str, metadata: Dict[str, Any]) -> DataClassification:
        """Classify document based on content and metadata"""
        content_lower = content.lower()
        
        # Check for restricted content
        for pattern in self.classification_rules[DataClassification.RESTRICTED]:
            if re.search(pattern, content_lower):
                return DataClassification.RESTRICTED
        
        # Check for confidential content
        for pattern in self.classification_rules[DataClassification.CONFIDENTIAL]:
            if re.search(pattern, content_lower):
                return DataClassification.CONFIDENTIAL
        
        # Check metadata for classification hints
        if metadata.get("folder_path", "").lower().startswith("confidential"):
            return DataClassification.CONFIDENTIAL
        
        return DataClassification.INTERNAL
    
    def apply_data_handling_policy(self, classification: DataClassification) -> Dict[str, Any]:
        """Get data handling policy based on classification"""
        policies = {
            DataClassification.RESTRICTED: {
                "retention_days": 2555,  # 7 years
                "encryption_required": True,
                "access_logging": True,
                "export_allowed": False,
                "sharing_allowed": False
            },
            DataClassification.CONFIDENTIAL: {
                "retention_days": 1825,  # 5 years
                "encryption_required": True,
                "access_logging": True,
                "export_allowed": True,
                "sharing_allowed": False
            },
            DataClassification.INTERNAL: {
                "retention_days": 1095,  # 3 years
                "encryption_required": False,
                "access_logging": False,
                "export_allowed": True,
                "sharing_allowed": True
            }
        }
        return policies.get(classification, policies[DataClassification.INTERNAL])
```

### 3. Personal Data Protection (GDPR/Privacy)

```python
# dtce_ai_bot/security/privacy.py
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta

class PersonalDataDetector:
    def __init__(self):
        self.pii_patterns = {
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            "nz_ird": r"\b\d{2,3}[-\s]?\d{3}[-\s]?\d{3}\b",
            "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
        }
    
    def detect_pii(self, content: str) -> List[Dict[str, Any]]:
        """Detect personally identifiable information in content"""
        findings = []
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                findings.append({
                    "type": pii_type,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end()
                })
        
        return findings
    
    def anonymize_content(self, content: str) -> str:
        """Anonymize personal data in content"""
        anonymized = content
        
        for pii_type, pattern in self.pii_patterns.items():
            anonymized = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", anonymized, flags=re.IGNORECASE)
        
        return anonymized

class DataRetentionManager:
    def __init__(self):
        self.retention_policies = {
            "chat_sessions": timedelta(days=90),
            "document_metadata": timedelta(days=1825),  # 5 years
            "access_logs": timedelta(days=365),
            "audit_logs": timedelta(days=2555)  # 7 years
        }
    
    async def cleanup_expired_data(self):
        """Clean up data that has exceeded retention period"""
        current_time = datetime.utcnow()
        
        for data_type, retention_period in self.retention_policies.items():
            cutoff_date = current_time - retention_period
            await self._delete_data_before_date(data_type, cutoff_date)
    
    async def _delete_data_before_date(self, data_type: str, cutoff_date: datetime):
        """Delete data of specific type before cutoff date"""
        # Implementation depends on storage system
        pass
```

## Input Validation and Sanitization

### 1. API Input Validation

```python
# dtce_ai_bot/security/input_validation.py
from pydantic import BaseModel, validator, Field
from typing import Optional, List
import re
import html

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., regex=r"^[a-zA-Z0-9_-]{1,50}$")
    context: Optional[dict] = None
    
    @validator('message')
    def validate_message(cls, v):
        # Remove potentially dangerous content
        v = html.escape(v)  # Escape HTML
        v = re.sub(r'<script.*?</script>', '', v, flags=re.IGNORECASE | re.DOTALL)
        v = re.sub(r'javascript:', '', v, flags=re.IGNORECASE)
        return v
    
    @validator('context')
    def validate_context(cls, v):
        if v is None:
            return v
        
        # Limit context size and validate structure
        if len(str(v)) > 1000:
            raise ValueError("Context too large")
        
        allowed_keys = {'project_filter', 'document_types', 'date_range'}
        if not set(v.keys()).issubset(allowed_keys):
            raise ValueError("Invalid context keys")
        
        return v

class DocumentSyncRequest(BaseModel):
    path: Optional[str] = Field(None, regex=r"^[a-zA-Z0-9/_-]{0,200}$")
    force: bool = False
    
    @validator('path')
    def validate_path(cls, v):
        if v is None:
            return v
        
        # Prevent path traversal
        if '..' in v or v.startswith('/') or '\\' in v:
            raise ValueError("Invalid path format")
        
        # Sanitize path
        v = re.sub(r'[^a-zA-Z0-9/_-]', '', v)
        return v

# SQL injection prevention
class SafeQueryBuilder:
    def __init__(self):
        self.allowed_operators = ['=', '!=', '>', '<', '>=', '<=', 'LIKE', 'IN']
        self.allowed_columns = ['name', 'path', 'created_date', 'modified_date', 'size']
    
    def build_safe_query(self, filters: Dict[str, Any]) -> str:
        """Build safe SQL query with parameterized inputs"""
        conditions = []
        parameters = {}
        
        for column, value in filters.items():
            if column not in self.allowed_columns:
                raise ValueError(f"Column '{column}' not allowed")
            
            # Use parameterized queries
            param_name = f"param_{len(parameters)}"
            conditions.append(f"{column} = :{param_name}")
            parameters[param_name] = value
        
        query = "SELECT * FROM documents"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        return query, parameters
```

### 2. File Upload Security

```python
# dtce_ai_bot/security/file_validation.py
import magic
from typing import List, Tuple
import hashlib
import os

class FileValidator:
    def __init__(self):
        self.allowed_extensions = {'.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.md'}
        self.allowed_mime_types = {
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain',
            'text/markdown'
        }
        self.max_file_size = 100 * 1024 * 1024  # 100MB
    
    def validate_file(self, file_content: bytes, filename: str) -> Tuple[bool, List[str]]:
        """Validate uploaded file for security"""
        errors = []
        
        # Check file size
        if len(file_content) > self.max_file_size:
            errors.append(f"File size exceeds maximum allowed size of {self.max_file_size} bytes")
        
        # Check file extension
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in self.allowed_extensions:
            errors.append(f"File extension '{file_ext}' not allowed")
        
        # Check MIME type
        mime_type = magic.from_buffer(file_content, mime=True)
        if mime_type not in self.allowed_mime_types:
            errors.append(f"MIME type '{mime_type}' not allowed")
        
        # Check for malicious content patterns
        if self._contains_malicious_content(file_content):
            errors.append("File contains potentially malicious content")
        
        return len(errors) == 0, errors
    
    def _contains_malicious_content(self, content: bytes) -> bool:
        """Check for malicious content patterns"""
        malicious_patterns = [
            b'<script',
            b'javascript:',
            b'vbscript:',
            b'onload=',
            b'onerror='
        ]
        
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in malicious_patterns)
    
    def calculate_file_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(content).hexdigest()
```

## Security Monitoring and Logging

### 1. Security Event Logging

```python
# dtce_ai_bot/security/security_logger.py
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from azure.monitor.opentelemetry import configure_azure_monitor

class SecurityLogger:
    def __init__(self):
        # Configure Azure Monitor for centralized logging
        configure_azure_monitor()
        
        self.logger = logging.getLogger("security")
        self.logger.setLevel(logging.INFO)
        
        # Create security-specific handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def log_authentication_event(self, user_id: str, event_type: str, 
                                success: bool, ip_address: str, 
                                additional_data: Optional[Dict] = None):
        """Log authentication events"""
        event = {
            "event_type": "authentication",
            "sub_type": event_type,
            "user_id": user_id,
            "success": success,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat(),
            "additional_data": additional_data or {}
        }
        
        if success:
            self.logger.info(f"Authentication success: {json.dumps(event)}")
        else:
            self.logger.warning(f"Authentication failure: {json.dumps(event)}")
    
    def log_authorization_event(self, user_id: str, resource: str, 
                               action: str, granted: bool, 
                               ip_address: str):
        """Log authorization events"""
        event = {
            "event_type": "authorization",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "granted": granted,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if granted:
            self.logger.info(f"Authorization granted: {json.dumps(event)}")
        else:
            self.logger.warning(f"Authorization denied: {json.dumps(event)}")
    
    def log_data_access_event(self, user_id: str, document_id: str, 
                             action: str, ip_address: str,
                             classification: Optional[str] = None):
        """Log data access events"""
        event = {
            "event_type": "data_access",
            "user_id": user_id,
            "document_id": document_id,
            "action": action,
            "classification": classification,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"Data access: {json.dumps(event)}")
    
    def log_security_incident(self, incident_type: str, severity: str,
                             description: str, user_id: Optional[str] = None,
                             ip_address: Optional[str] = None):
        """Log security incidents"""
        event = {
            "event_type": "security_incident",
            "incident_type": incident_type,
            "severity": severity,
            "description": description,
            "user_id": user_id,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if severity in ["high", "critical"]:
            self.logger.error(f"Security incident: {json.dumps(event)}")
        else:
            self.logger.warning(f"Security incident: {json.dumps(event)}")

# Singleton instance
security_logger = SecurityLogger()
```

### 2. Anomaly Detection

```python
# dtce_ai_bot/security/anomaly_detection.py
from typing import Dict, List, Any
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict, deque

class AnomalyDetector:
    def __init__(self):
        self.user_activity = defaultdict(lambda: deque(maxlen=100))
        self.thresholds = {
            "login_attempts_per_hour": 10,
            "api_calls_per_minute": 100,
            "failed_auth_attempts": 5,
            "data_download_volume_mb": 1000
        }
    
    def track_user_activity(self, user_id: str, activity_type: str, 
                           timestamp: datetime, metadata: Dict[str, Any]):
        """Track user activity for anomaly detection"""
        activity = {
            "type": activity_type,
            "timestamp": timestamp,
            "metadata": metadata
        }
        
        self.user_activity[user_id].append(activity)
        
        # Check for anomalies
        anomalies = self._detect_anomalies(user_id)
        if anomalies:
            self._handle_anomalies(user_id, anomalies)
    
    def _detect_anomalies(self, user_id: str) -> List[Dict[str, Any]]:
        """Detect anomalous behavior patterns"""
        activities = list(self.user_activity[user_id])
        anomalies = []
        
        # Check for rapid login attempts
        recent_logins = [a for a in activities 
                        if a["type"] == "login" 
                        and a["timestamp"] > datetime.utcnow() - timedelta(hours=1)]
        
        if len(recent_logins) > self.thresholds["login_attempts_per_hour"]:
            anomalies.append({
                "type": "excessive_login_attempts",
                "count": len(recent_logins),
                "threshold": self.thresholds["login_attempts_per_hour"]
            })
        
        # Check for failed authentication attempts
        recent_failures = [a for a in activities 
                          if a["type"] == "auth_failure" 
                          and a["timestamp"] > datetime.utcnow() - timedelta(minutes=30)]
        
        if len(recent_failures) > self.thresholds["failed_auth_attempts"]:
            anomalies.append({
                "type": "excessive_auth_failures",
                "count": len(recent_failures),
                "threshold": self.thresholds["failed_auth_attempts"]
            })
        
        # Check for unusual API usage
        recent_api_calls = [a for a in activities 
                           if a["type"] == "api_call" 
                           and a["timestamp"] > datetime.utcnow() - timedelta(minutes=1)]
        
        if len(recent_api_calls) > self.thresholds["api_calls_per_minute"]:
            anomalies.append({
                "type": "excessive_api_usage",
                "count": len(recent_api_calls),
                "threshold": self.thresholds["api_calls_per_minute"]
            })
        
        return anomalies
    
    def _handle_anomalies(self, user_id: str, anomalies: List[Dict[str, Any]]):
        """Handle detected anomalies"""
        for anomaly in anomalies:
            security_logger.log_security_incident(
                incident_type=anomaly["type"],
                severity="high",
                description=f"Anomalous behavior detected for user {user_id}: {anomaly}",
                user_id=user_id
            )
            
            # Implement response actions
            if anomaly["type"] == "excessive_auth_failures":
                self._trigger_account_lockout(user_id)
            elif anomaly["type"] == "excessive_api_usage":
                self._trigger_rate_limiting(user_id)
    
    def _trigger_account_lockout(self, user_id: str):
        """Trigger temporary account lockout"""
        # Implementation for account lockout
        pass
    
    def _trigger_rate_limiting(self, user_id: str):
        """Trigger rate limiting for user"""
        # Implementation for rate limiting
        pass
```

## Security Configuration Management

### 1. Azure Key Vault Integration

```python
# dtce_ai_bot/security/key_vault.py
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from typing import Optional
import os

class KeyVaultManager:
    def __init__(self, vault_url: str):
        self.vault_url = vault_url
        self.credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=vault_url, credential=self.credential)
    
    async def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve secret from Azure Key Vault"""
        try:
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            security_logger.log_security_incident(
                incident_type="key_vault_access_failure",
                severity="medium",
                description=f"Failed to retrieve secret '{secret_name}': {str(e)}"
            )
            return None
    
    async def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """Store secret in Azure Key Vault"""
        try:
            self.client.set_secret(secret_name, secret_value)
            return True
        except Exception as e:
            security_logger.log_security_incident(
                incident_type="key_vault_write_failure",
                severity="medium",
                description=f"Failed to store secret '{secret_name}': {str(e)}"
            )
            return False
    
    async def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        """Rotate secret with new value"""
        # Store new version
        success = await self.set_secret(secret_name, new_value)
        if success:
            security_logger.log_security_incident(
                incident_type="secret_rotation",
                severity="info",
                description=f"Secret '{secret_name}' rotated successfully"
            )
        return success

# Configuration management
class SecureConfig:
    def __init__(self):
        self.kv_manager = KeyVaultManager(os.getenv("AZURE_KEY_VAULT_URL"))
    
    async def get_database_connection_string(self) -> str:
        return await self.kv_manager.get_secret("database-connection-string")
    
    async def get_openai_api_key(self) -> str:
        return await self.kv_manager.get_secret("openai-api-key")
    
    async def get_microsoft_client_secret(self) -> str:
        return await self.kv_manager.get_secret("microsoft-client-secret")
```

### 2. Network Security Configuration

```python
# dtce_ai_bot/security/network_security.py
from fastapi import Request, HTTPException
from typing import List, Set
import ipaddress

class NetworkSecurityManager:
    def __init__(self):
        # Define allowed IP ranges
        self.allowed_ip_ranges = [
            ipaddress.IPv4Network("10.0.0.0/8"),  # Internal network
            ipaddress.IPv4Network("172.16.0.0/12"),  # Internal network
            ipaddress.IPv4Network("192.168.0.0/16"),  # Internal network
            # Add Teams IP ranges
            ipaddress.IPv4Network("52.112.0.0/14"),
            ipaddress.IPv4Network("52.120.0.0/14")
        ]
        
        # Blocked IP addresses
        self.blocked_ips: Set[str] = set()
        
        # Rate limiting
        self.rate_limits = {
            "default": 100,  # requests per minute
            "auth": 10,      # auth requests per minute
            "sync": 5        # sync requests per hour
        }
    
    def validate_ip_address(self, ip_address: str) -> bool:
        """Validate if IP address is allowed"""
        if ip_address in self.blocked_ips:
            return False
        
        try:
            ip = ipaddress.IPv4Address(ip_address)
            
            # Check if IP is in allowed ranges
            for allowed_range in self.allowed_ip_ranges:
                if ip in allowed_range:
                    return True
            
            # For development, allow localhost
            if ip.is_loopback:
                return True
            
            return False
        except ipaddress.AddressValueError:
            return False
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded IP (behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client host
        return request.client.host if request.client else "unknown"
    
    def add_blocked_ip(self, ip_address: str, reason: str):
        """Add IP address to block list"""
        self.blocked_ips.add(ip_address)
        security_logger.log_security_incident(
            incident_type="ip_blocked",
            severity="medium",
            description=f"IP {ip_address} blocked: {reason}"
        )

# Middleware for network security
async def network_security_middleware(request: Request, call_next):
    """Network security middleware"""
    security_manager = NetworkSecurityManager()
    client_ip = security_manager.get_client_ip(request)
    
    # Validate IP address
    if not security_manager.validate_ip_address(client_ip):
        security_logger.log_security_incident(
            incident_type="blocked_ip_access_attempt",
            severity="high",
            description=f"Access attempt from blocked IP: {client_ip}",
            ip_address=client_ip
        )
        raise HTTPException(status_code=403, detail="Access denied")
    
    response = await call_next(request)
    return response
```

## Incident Response

### 1. Security Incident Response Plan

```python
# dtce_ai_bot/security/incident_response.py
from enum import Enum
from typing import List, Dict, Any
from datetime import datetime
import asyncio

class IncidentSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentType(Enum):
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_BREACH = "data_breach"
    AUTHENTICATION_BYPASS = "authentication_bypass"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    MALWARE_DETECTION = "malware_detection"
    DDOS_ATTACK = "ddos_attack"

class SecurityIncident:
    def __init__(self, incident_type: IncidentType, severity: IncidentSeverity,
                 description: str, affected_resources: List[str] = None):
        self.id = self._generate_incident_id()
        self.incident_type = incident_type
        self.severity = severity
        self.description = description
        self.affected_resources = affected_resources or []
        self.timestamp = datetime.utcnow()
        self.status = "open"
        self.response_actions = []

class IncidentResponseManager:
    def __init__(self):
        self.active_incidents: Dict[str, SecurityIncident] = {}
        self.response_procedures = {
            IncidentType.UNAUTHORIZED_ACCESS: self._handle_unauthorized_access,
            IncidentType.DATA_BREACH: self._handle_data_breach,
            IncidentType.AUTHENTICATION_BYPASS: self._handle_auth_bypass,
            IncidentType.PRIVILEGE_ESCALATION: self._handle_privilege_escalation,
            IncidentType.MALWARE_DETECTION: self._handle_malware_detection,
            IncidentType.DDOS_ATTACK: self._handle_ddos_attack
        }
    
    async def handle_incident(self, incident: SecurityIncident):
        """Handle security incident based on type and severity"""
        self.active_incidents[incident.id] = incident
        
        # Log incident
        security_logger.log_security_incident(
            incident_type=incident.incident_type.value,
            severity=incident.severity.value,
            description=incident.description
        )
        
        # Execute response procedure
        if incident.incident_type in self.response_procedures:
            await self.response_procedures[incident.incident_type](incident)
        
        # Notify security team for high/critical incidents
        if incident.severity in [IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]:
            await self._notify_security_team(incident)
    
    async def _handle_unauthorized_access(self, incident: SecurityIncident):
        """Handle unauthorized access attempts"""
        actions = [
            "Block source IP address",
            "Review access logs",
            "Check for privilege escalation",
            "Verify user account integrity"
        ]
        
        for action in actions:
            incident.response_actions.append({
                "action": action,
                "timestamp": datetime.utcnow(),
                "status": "pending"
            })
        
        # Automatic response actions
        if "user_id" in incident.description:
            user_id = self._extract_user_id(incident.description)
            await self._suspend_user_account(user_id)
    
    async def _handle_data_breach(self, incident: SecurityIncident):
        """Handle potential data breach"""
        actions = [
            "Identify compromised data",
            "Assess scope of breach",
            "Contain the breach",
            "Notify stakeholders",
            "Prepare regulatory notifications"
        ]
        
        # Critical severity - immediate response
        if incident.severity == IncidentSeverity.CRITICAL:
            await self._emergency_system_isolation()
    
    async def _notify_security_team(self, incident: SecurityIncident):
        """Notify security team of high/critical incidents"""
        # Implementation would integrate with notification systems
        # (email, Slack, Teams, PagerDuty, etc.)
        pass
    
    async def _emergency_system_isolation(self):
        """Emergency system isolation for critical incidents"""
        # Implementation for emergency response
        # - Disable external access
        # - Stop non-essential services
        # - Preserve evidence
        pass
```

## Compliance and Auditing

### 1. Compliance Framework

```python
# dtce_ai_bot/security/compliance.py
from typing import Dict, List, Any
from datetime import datetime, timedelta
import json

class ComplianceFramework:
    def __init__(self):
        self.standards = {
            "GDPR": {
                "data_protection": True,
                "consent_required": True,
                "data_retention_limits": True,
                "breach_notification": "72_hours"
            },
            "SOC2": {
                "security_controls": True,
                "availability_monitoring": True,
                "processing_integrity": True,
                "confidentiality": True
            },
            "ISO27001": {
                "risk_management": True,
                "security_policies": True,
                "incident_management": True,
                "business_continuity": True
            }
        }
    
    def generate_compliance_report(self, standard: str) -> Dict[str, Any]:
        """Generate compliance report for specific standard"""
        if standard not in self.standards:
            raise ValueError(f"Unknown compliance standard: {standard}")
        
        report = {
            "standard": standard,
            "generated_date": datetime.utcnow().isoformat(),
            "compliance_status": {},
            "findings": [],
            "recommendations": []
        }
        
        if standard == "GDPR":
            report.update(self._assess_gdpr_compliance())
        elif standard == "SOC2":
            report.update(self._assess_soc2_compliance())
        elif standard == "ISO27001":
            report.update(self._assess_iso27001_compliance())
        
        return report
    
    def _assess_gdpr_compliance(self) -> Dict[str, Any]:
        """Assess GDPR compliance"""
        findings = []
        
        # Check data processing records
        if not self._verify_data_processing_records():
            findings.append({
                "requirement": "Article 30 - Records of processing",
                "status": "non_compliant",
                "description": "Data processing records incomplete"
            })
        
        # Check consent mechanisms
        if not self._verify_consent_mechanisms():
            findings.append({
                "requirement": "Article 7 - Consent",
                "status": "non_compliant",
                "description": "Consent mechanisms not properly implemented"
            })
        
        return {"gdpr_findings": findings}
    
    def _verify_data_processing_records(self) -> bool:
        """Verify data processing records are maintained"""
        # Implementation to check processing records
        return True
    
    def _verify_consent_mechanisms(self) -> bool:
        """Verify consent mechanisms are in place"""
        # Implementation to check consent mechanisms
        return True

class AuditManager:
    def __init__(self):
        self.audit_logs = []
    
    def log_audit_event(self, event_type: str, user_id: str, 
                       resource: str, action: str, result: str,
                       additional_data: Dict[str, Any] = None):
        """Log audit event"""
        audit_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "result": result,
            "additional_data": additional_data or {},
            "source_ip": self._get_source_ip(),
            "user_agent": self._get_user_agent()
        }
        
        self.audit_logs.append(audit_event)
        
        # Store in persistent audit log
        self._store_audit_event(audit_event)
    
    def generate_audit_report(self, start_date: datetime, 
                             end_date: datetime) -> Dict[str, Any]:
        """Generate audit report for specified period"""
        filtered_logs = [
            log for log in self.audit_logs
            if start_date <= datetime.fromisoformat(log["timestamp"]) <= end_date
        ]
        
        report = {
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_events": len(filtered_logs),
            "event_summary": self._summarize_events(filtered_logs),
            "security_events": self._filter_security_events(filtered_logs),
            "user_activity": self._summarize_user_activity(filtered_logs)
        }
        
        return report
    
    def _store_audit_event(self, event: Dict[str, Any]):
        """Store audit event in persistent storage"""
        # Implementation for persistent audit log storage
        pass
```

## Security Best Practices

### 1. Secure Development Guidelines

```python
# Security checklist for development team
SECURITY_CHECKLIST = {
    "authentication": [
        "Use Azure AD for authentication",
        "Implement MFA where possible",
        "Validate all tokens properly",
        "Handle authentication errors securely"
    ],
    "authorization": [
        "Implement role-based access control",
        "Follow principle of least privilege",
        "Validate permissions on every request",
        "Log authorization decisions"
    ],
    "input_validation": [
        "Validate all user inputs",
        "Use parameterized queries",
        "Sanitize output data",
        "Implement rate limiting"
    ],
    "data_protection": [
        "Encrypt sensitive data at rest",
        "Use TLS for data in transit",
        "Implement proper key management",
        "Classify and handle data appropriately"
    ],
    "error_handling": [
        "Don't expose sensitive information in errors",
        "Log errors securely",
        "Implement proper exception handling",
        "Use generic error messages for users"
    ],
    "logging_monitoring": [
        "Log security events",
        "Monitor for anomalies",
        "Implement alerting",
        "Retain logs appropriately"
    ]
}
```

### 2. Security Testing Integration

```python
# tests/security/test_security.py
import pytest
from fastapi.testclient import TestClient
from dtce_ai_bot.main import app

class TestSecurity:
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_sql_injection_protection(self, client):
        """Test protection against SQL injection"""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "1' UNION SELECT * FROM users--"
        ]
        
        for malicious_input in malicious_inputs:
            response = client.post("/chat", json={
                "message": malicious_input,
                "session_id": "test"
            })
            # Should not crash and should handle safely
            assert response.status_code in [200, 400, 422]
    
    def test_xss_protection(self, client):
        """Test protection against XSS attacks"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>"
        ]
        
        for payload in xss_payloads:
            response = client.post("/chat", json={
                "message": payload,
                "session_id": "test"
            })
            
            # Response should not contain executable script
            if response.status_code == 200:
                assert "<script>" not in response.text
                assert "javascript:" not in response.text
    
    def test_path_traversal_protection(self, client):
        """Test protection against path traversal"""
        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f"
        ]
        
        for attempt in traversal_attempts:
            response = client.post(f"/documents/sync-suitefiles?path={attempt}")
            # Should reject malicious paths
            assert response.status_code in [400, 422]
```

This comprehensive security guide provides a robust foundation for securing the DTCE AI Assistant across all layers, from authentication and data protection to incident response and compliance. Regular security reviews and updates to these measures ensure ongoing protection against evolving threats.
