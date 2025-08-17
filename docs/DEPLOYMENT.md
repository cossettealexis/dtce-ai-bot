# DTCE AI Assistant - Deployment Guide

## Production Deployment

### Prerequisites
- Azure subscription with appropriate permissions
- GitHub repository with the code
- Domain name for the application (optional but recommended)

### Azure Resource Setup

#### 1. Create Resource Group
```bash
az group create --name dtce-ai-prod --location eastus
```

#### 2. Create App Service Plan
```bash
az appservice plan create \
    --name dtce-prod-plan \
    --resource-group dtce-ai-prod \
    --sku B1 \
    --is-linux
```

#### 3. Create Web App
```bash
az webapp create \
    --resource-group dtce-ai-prod \
    --plan dtce-prod-plan \
    --name dtce-ai-assistant-prod \
    --runtime "PYTHON|3.9" \
    --deployment-source-url https://github.com/your-username/dtce-ai-bot \
    --deployment-source-branch main
```

#### 4. Configure Application Settings
```bash
# Create appsettings.json with production values
az webapp config appsettings set \
    --name dtce-ai-assistant-prod \
    --resource-group dtce-ai-prod \
    --settings @appsettings.prod.json
```

### Environment Configuration

#### Production Environment Variables
Create `appsettings.prod.json`:
```json
{
  "AZURE_STORAGE_ACCOUNT_NAME": "your-prod-storage",
  "AZURE_STORAGE_ACCOUNT_KEY": "your-storage-key",
  "AZURE_FORM_RECOGNIZER_ENDPOINT": "https://your-form-recognizer.cognitiveservices.azure.com/",
  "AZURE_FORM_RECOGNIZER_KEY": "your-form-recognizer-key",
  "MICROSOFT_APP_ID": "your-app-id",
  "MICROSOFT_APP_PASSWORD": "your-app-password",
  "SHAREPOINT_TENANT_ID": "your-tenant-id",
  "SHAREPOINT_CLIENT_ID": "your-client-id",
  "SHAREPOINT_CLIENT_SECRET": "your-client-secret",
  "SHAREPOINT_SITE_URL": "https://yourtenant.sharepoint.com/sites/yoursite",
  "FLASK_ENV": "production",
  "FLASK_DEBUG": "False"
}
```

### CI/CD Pipeline

#### GitHub Actions Workflow
Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy to Azure

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        python -m pytest tests/ -v
    
    - name: Deploy to Azure Web App
      uses: azure/webapps-deploy@v2
      with:
        app-name: 'dtce-ai-assistant-prod'
        publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

### Database Setup (if needed)

#### Azure SQL Database
```bash
# Create SQL Server
az sql server create \
    --name dtce-sql-server \
    --resource-group dtce-ai-prod \
    --location eastus \
    --admin-user sqladmin \
    --admin-password YourPassword123!

# Create Database
az sql db create \
    --resource-group dtce-ai-prod \
    --server dtce-sql-server \
    --name dtce-database \
    --service-objective Basic
```

### SSL/TLS Configuration

#### Custom Domain and SSL
```bash
# Add custom domain
az webapp config hostname add \
    --webapp-name dtce-ai-assistant-prod \
    --resource-group dtce-ai-prod \
    --hostname yourdomain.com

# Enable HTTPS
az webapp update \
    --name dtce-ai-assistant-prod \
    --resource-group dtce-ai-prod \
    --https-only true
```

### Monitoring and Logging

#### Application Insights
```bash
# Create Application Insights
az monitor app-insights component create \
    --app dtce-ai-insights \
    --location eastus \
    --resource-group dtce-ai-prod \
    --application-type web

# Get instrumentation key
az monitor app-insights component show \
    --app dtce-ai-insights \
    --resource-group dtce-ai-prod \
    --query instrumentationKey
```

#### Log Analytics
```bash
# Create Log Analytics Workspace
az monitor log-analytics workspace create \
    --resource-group dtce-ai-prod \
    --workspace-name dtce-logs
```

### Security Configuration

#### Key Vault Setup
```bash
# Create Key Vault
az keyvault create \
    --name dtce-keyvault \
    --resource-group dtce-ai-prod \
    --location eastus

# Add secrets
az keyvault secret set \
    --vault-name dtce-keyvault \
    --name "storage-key" \
    --value "your-storage-key"
```

#### Managed Identity
```bash
# Enable system-assigned managed identity
az webapp identity assign \
    --name dtce-ai-assistant-prod \
    --resource-group dtce-ai-prod

# Grant Key Vault access
az keyvault set-policy \
    --name dtce-keyvault \
    --object-id <identity-principal-id> \
    --secret-permissions get list
```

### Scaling Configuration

#### Auto-scaling Rules
```bash
# Create auto-scale profile
az monitor autoscale create \
    --resource-group dtce-ai-prod \
    --resource dtce-ai-assistant-prod \
    --resource-type Microsoft.Web/serverfarms \
    --name dtce-autoscale \
    --min-count 1 \
    --max-count 5 \
    --count 2

# Add scale-out rule
az monitor autoscale rule create \
    --resource-group dtce-ai-prod \
    --autoscale-name dtce-autoscale \
    --condition "Percentage CPU > 70 avg 5m" \
    --scale out 1
```

### Backup and Disaster Recovery

#### Database Backup
```bash
# Configure automated backups
az sql db update \
    --resource-group dtce-ai-prod \
    --server dtce-sql-server \
    --name dtce-database \
    --backup-storage-redundancy Geo
```

#### Storage Backup
```bash
# Enable blob versioning
az storage account blob-service-properties update \
    --account-name your-prod-storage \
    --enable-versioning true

# Configure lifecycle management
az storage account management-policy create \
    --account-name your-prod-storage \
    --policy @lifecycle-policy.json
```

### Health Checks and Monitoring

#### Health Check Endpoint
Add to your Flask app:
```python
@app.route('/health')
def health_check():
    try:
        # Test database connection
        # Test storage connection
        # Test external APIs
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': os.getenv('APP_VERSION', '1.0.0')
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }, 503
```

#### Monitoring Alerts
```bash
# Create metric alert
az monitor metrics alert create \
    --name "High CPU Usage" \
    --resource-group dtce-ai-prod \
    --scopes /subscriptions/{subscription}/resourceGroups/dtce-ai-prod/providers/Microsoft.Web/sites/dtce-ai-assistant-prod \
    --condition "avg Percentage CPU > 80" \
    --description "Alert when CPU usage is high"
```

### Performance Optimization

#### CDN Configuration
```bash
# Create CDN profile
az cdn profile create \
    --resource-group dtce-ai-prod \
    --name dtce-cdn \
    --sku Standard_Microsoft

# Create CDN endpoint
az cdn endpoint create \
    --resource-group dtce-ai-prod \
    --profile-name dtce-cdn \
    --name dtce-endpoint \
    --origin yourdomain.com
```

#### Caching Strategy
Configure Redis Cache:
```bash
# Create Redis Cache
az redis create \
    --location eastus \
    --name dtce-redis \
    --resource-group dtce-ai-prod \
    --sku Basic \
    --vm-size c0
```

### Teams App Deployment

#### Teams App Package
1. Update `manifest.json` with production URLs
2. Create app package with updated manifest
3. Submit to Teams App Store or deploy to organization

#### Bot Registration
```bash
# Update bot endpoint
az bot update \
    --name dtce-ai-bot \
    --resource-group dtce-ai-prod \
    --endpoint https://dtce-ai-assistant-prod.azurewebsites.net/api/messages
```

### Post-Deployment Checklist

#### Verification Steps
- [ ] Application loads successfully
- [ ] Health check endpoint responds
- [ ] Document upload works
- [ ] SharePoint sync functions
- [ ] Teams bot responds
- [ ] SSL certificate valid
- [ ] Monitoring alerts configured
- [ ] Backup policies active

#### Performance Testing
```bash
# Load testing with Apache Bench
ab -n 1000 -c 10 https://your-production-url.com/health

# Monitor application during load test
az monitor metrics list \
    --resource /subscriptions/{subscription}/resourceGroups/dtce-ai-prod/providers/Microsoft.Web/sites/dtce-ai-assistant-prod \
    --metric "CpuPercentage,MemoryPercentage"
```

### Troubleshooting

#### Common Production Issues
1. **Application won't start**
   - Check application logs: `az webapp log tail`
   - Verify environment variables
   - Check Python version compatibility

2. **Performance issues**
   - Monitor Application Insights
   - Check database query performance
   - Review storage access patterns

3. **Authentication failures**
   - Verify certificates and secrets
   - Check Key Vault permissions
   - Validate Azure AD configuration

#### Log Analysis
```bash
# Download logs
az webapp log download \
    --name dtce-ai-assistant-prod \
    --resource-group dtce-ai-prod

# Stream live logs
az webapp log tail \
    --name dtce-ai-assistant-prod \
    --resource-group dtce-ai-prod
```

### Maintenance

#### Regular Tasks
- Monitor costs and optimize resources
- Update dependencies and security patches
- Review and rotate secrets
- Backup critical data
- Performance monitoring and optimization

#### Updates and Rollbacks
```bash
# Deploy specific version
az webapp deployment source sync \
    --name dtce-ai-assistant-prod \
    --resource-group dtce-ai-prod

# Rollback if needed
az webapp deployment slot swap \
    --name dtce-ai-assistant-prod \
    --resource-group dtce-ai-prod \
    --slot staging \
    --target-slot production
```

For development deployment, see [DEVELOPMENT.md](DEVELOPMENT.md).
