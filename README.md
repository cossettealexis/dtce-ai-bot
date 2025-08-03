# DTCE AI Assistant - Microsoft Teams Bot

An AI-powered Microsoft Teams bot for searching DTCE engineering project files stored in SharePoint/Suitefiles. This Teams bot allo## 🤖 Using the Teams Bot

### **In Personal Chat:**
- Start a direct message with "DTCE AI Assistant"
- Ask questions like: *"Show me seismic retrofits from 2024"*
- Use commands: `/help`, `/projects`, `/health`

### **In Team Channels:**
- @mention the bot: *"@DTCE AI Assistant find bridge projects"*
- Bot responds with adaptive cards showing results
- Team members can see and benefit from shared queries

### **Available Commands:**
- `/help` - Show available commands and examples
- `/projects` - List all available projects  
- `/health` - Check system status
- Natural language queries work without commandsrs to query their project documentation using natural language directly within Microsoft Teams and get intelligent responses powered by Azure OpenAI.

## 🏗️ Architecture

The system consists of several key components:

1. **Microsoft Teams Bot**: Native Teams bot using Bot Framework
2. **SharePoint Integration**: Connects to DTCE's Suitefiles (SharePoint) via Microsoft Graph API
3. **Document Processing**: Extracts text and metadata from various file types (PDF, Word, Excel)
4. **Azure Storage**: Stores processed documents and metadata in Azure Blob Storage
5. **Search Index**: Uses Azure Cognitive Search for fast, filtered document retrieval
6. **AI Engine**: Azure OpenAI (GPT) generates intelligent summaries and answers
7. **FastAPI Backend**: Hosts the bot messaging endpoint and API services

## 📁 Project Structure

```
dtce-ai-bot/
├── src/
│   ├── models.py                 # Pydantic models for data structures
│   ├── sharepoint_client.py      # SharePoint/Graph API integration
│   ├── azure_blob_client.py      # Azure Blob Storage operations
│   ├── azure_search_client.py    # Azure Cognitive Search operations
│   ├── azure_openai_client.py    # Azure OpenAI integration
│   ├── document_processor.py     # Document text extraction
│   └── teams_bot.py              # Microsoft Teams Bot implementation
├── teams-app/
│   ├── manifest.json             # Teams app manifest
│   └── DTCE-AI-Assistant.zip     # Teams app package (generated)
├── main.py                       # FastAPI application with Teams bot endpoint
├── config.py                     # Application configuration
├── requirements.txt              # Python dependencies
├── test_sharepoint.py           # SharePoint connectivity test
├── test_azure.py                # Azure services test
├── setup_teams.py               # Teams bot setup script
├── .env.example                 # Environment variables template
└── README.md                    # This file
```

## 🚀 Setup Instructions

### 1. Prerequisites

- Python 3.10 or higher
- Azure subscription with the following services:
  - Azure Storage Account
  - Azure Cognitive Search
  - Azure OpenAI
  - Azure App Service (for deployment)
- Microsoft 365 access to DTCE SharePoint

### 2. Clone and Install

```bash
git clone <repository-url>
cd dtce-ai-bot
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

### 3. Configure Microsoft Teams Bot

Register your bot in Azure:
- Go to Azure Portal → Bot Services → Create
- Choose "Multi Tenant" bot
- Set messaging endpoint: `https://your-domain.com/api/messages`
- Note down App ID and create App Password

Required variables:
- **Teams Bot**: `MICROSOFT_APP_ID`, `MICROSOFT_APP_PASSWORD`, `MICROSOFT_APP_TENANT_ID`
- **Microsoft Graph API**: `MICROSOFT_CLIENT_ID`, `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_SECRET`
- **SharePoint**: `SHAREPOINT_SITE_ID`
- **Azure Storage**: `AZURE_STORAGE_CONNECTION_STRING`
- **Azure Search**: `AZURE_SEARCH_SERVICE_NAME`, `AZURE_SEARCH_ADMIN_KEY`
- **Azure OpenAI**: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`

### 4. Test Connections

Test SharePoint connectivity:
```bash
python test_sharepoint.py
```

Test Azure services:
```bash
python test_azure.py
```

### 5. Start the Application

```bash
python main.py
```

The API will be available at `http://localhost:8000`

## 📊 Folder Structure in SharePoint

The system focuses on these SharePoint folders:

### Engineering Folder
- Contains general engineering guides, references, and templates

### Projects Folder (219, 220, 221, 222, 223, 224, 225)
Each project folder contains subfolders:
- `01_Fees_and_Invoices` - Financial documents
- `02_Emails` - Project correspondence  
- `03_For_internal_review` - Internal review documents
- `04_Received` - Documents received from clients/vendors
- `05_Issued` - Documents issued to clients
- `06_Calculations` - Engineering calculations
- `07_Drawings` - Technical drawings
- `08_Reports_and_Specifications` - ⭐ **Critical for AI search**
- `09_Photos` - ❌ **Excluded** (images not indexed)
- `10_Site_meeting_and_phone_notes` - Meeting notes

## 🔧 API Endpoints

### Teams Bot Messaging
```http
POST /api/messages
```
*This is the main endpoint that Microsoft Teams uses to send messages to your bot.*

### Teams App Manifest
```http
GET /api/teams/manifest
```

### Health Check
```http
GET /health
```

### Search Documents (API)
```http
POST /api/search
Content-Type: application/json

{
  "query": "Show me seismic retrofit projects from 2024",
  "max_results": 20,
  "include_content": true
}
```

### Other API Endpoints
- `POST /api/ingest/start` - Start document ingestion
- `GET /api/ingest/status/{operation_id}` - Check ingestion status  
- `GET /api/projects` - List projects
- `GET /api/projects/{project_id}` - Get project details
- `POST /api/ask` - Ask questions

## 🤖 Example Queries

Engineers can ask natural language questions like:

- "Show me projects like this bridge design in 2022"
- "What seismic retrofits did we complete in 2024?"
- "Find all final reports for project 225"
- "List projects with internal reviews pending"
- "Show me all structural calculations for bridges"
- "What was issued to the client for project 222?"

## 🔄 Document Processing Flow

1. **Scan SharePoint**: System scans Engineering and Projects folders
2. **Extract Metadata**: Captures file info, project ID, document type, dates
3. **Download Content**: Retrieves file content from SharePoint
4. **Process Text**: Extracts text from PDFs, Word docs, Excel files
5. **Store in Blob**: Saves processed content to Azure Blob Storage
6. **Index Content**: Adds searchable content to Azure Cognitive Search
7. **AI Enhancement**: Uses GPT to extract additional insights

## 📋 Document Metadata Captured

For each document, the system captures:

- **Basic Info**: File name, size, type, dates
- **Location**: SharePoint path, project ID, folder structure
- **Content**: Extracted text, preview, keywords
- **Business Info**: Client name, project title, status
- **Technical**: Document type, engineering keywords

## 🛠️ Deployment

### Local Development
```bash
python main.py
```

### Azure App Service
1. Create App Service with Python 3.10 runtime
2. Deploy code via GitHub Actions or ZIP upload
3. Configure environment variables in App Service settings
4. Set startup command: `python main.py`

### Docker (Optional)
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## 🔒 Security Considerations

- Use Azure Key Vault for production secrets
- Configure appropriate CORS settings
- Implement authentication for the API
- Use managed identities where possible
- Regular security updates for dependencies

## 📈 Monitoring and Maintenance

- Monitor Azure service costs and usage
- Set up alerts for failed document processing
- Regular index optimization
- Monitor search query performance
- Update AI prompts based on user feedback

## 🧪 Testing

Run the test scripts to verify all components:

```bash
# Test SharePoint connection
python test_sharepoint.py

# Test Azure services
python test_azure.py

# Run unit tests (if available)
pytest
```

## 🤝 Usage Examples

### Search for Bridge Projects
```python
import requests

response = requests.post("http://localhost:8000/api/search", json={
    "query": "bridge structural analysis reports",
    "max_results": 10
})

results = response.json()
print(f"Found {results['total_results']} documents")
print(f"AI Summary: {results['ai_summary']}")
```

### Ask Specific Questions
```python
response = requests.post("http://localhost:8000/api/ask", json={
    "question": "What seismic retrofits were completed in 2024?"
})

answer = response.json()
print(f"Answer: {answer['answer']}")
```

## 📝 Next Steps

1. **Setup Azure Services** (if not done):
   - Azure Storage Account: `dtceai-storage`
   - Azure Cognitive Search: `dtceai-search`  
   - Azure OpenAI: `dtceai-gpt`
   - Azure App Service: `dtceai-backend`

2. **Initial Data Ingestion**:
   - Run ingestion for a single project first
   - Verify search results are accurate
   - Gradually expand to all projects

3. **Frontend Integration**:
   - Teams bot integration
   - Simple web interface
   - Mobile-friendly design

4. **Advanced Features**:
   - Document similarity search
   - Project timeline visualization
   - Budget/cost analysis from financial docs
   - Automated project status updates

## 🆘 Troubleshooting

### Common Issues

**Authentication Fails**:
- Check client ID and tenant ID
- Verify app permissions in Azure AD
- For device flow, complete browser authentication

**Search Returns No Results**:
- Check if documents are indexed
- Verify search service is running
- Try simpler search terms

**Document Processing Fails**:
- Check file permissions in SharePoint
- Verify supported file types
- Check Azure storage connectivity

**AI Responses Are Poor**:
- Ensure documents contain extracted text
- Check OpenAI model deployment
- Adjust prompt templates in code

### Getting Help

1. Check application logs for detailed error messages
2. Use test scripts to isolate issues
3. Verify all environment variables are set correctly
4. Check Azure service health and quotas

## 📄 License

[Add your license information here]

## 👥 Contributing

[Add contribution guidelines here]
