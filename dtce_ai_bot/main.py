"""
Main FastAPI application entry point for DTCE AI Bot.
Updated: ChatGPT-style responses deployed.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
import structlog
from datetime import datetime

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.api.documents import router as documents_router
from dtce_ai_bot.bot.endpoints import router as bot_router

# Configure structured logging
logger = structlog.get_logger(__name__)
settings = get_settings()

# Initialize FastAPI application
app = FastAPI(
    title="DTCE AI Bot",
    description="AI-powered document processing and chat bot for engineering projects",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents_router, prefix="/documents", tags=["Documents"])
app.include_router(bot_router, prefix="/api", tags=["Bot"])

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return JSONResponse({
        "message": "DTCE AI Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "teams_bot": "/api/teams",
            "documents": "/documents",
            "project_scoping": "/projects"
        }
    })

@app.get("/health")
async def health_check():
    """Health check endpoint with real-time timestamp."""
    return JSONResponse({
        "status": "healthy",
        "service": "dtce-ai-bot",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    """Privacy policy endpoint for Teams compliance."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Privacy Policy - DTCE AI Assistant</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; line-height: 1.6; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px; }
            h2 { color: #333; margin-top: 30px; }
            .effective-date { background: #f0f8ff; padding: 10px; border-left: 4px solid #0078d4; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Privacy Policy</h1>
            <div class="effective-date">
                <strong>Effective Date:</strong> August 17, 2025
            </div>
            
            <h2>1. Information We Collect</h2>
            <p>DTCE AI Assistant collects and processes the following information:</p>
            <ul>
                <li><strong>Document Content:</strong> Engineering documents, project files, and reports uploaded or accessed through SharePoint integration</li>
                <li><strong>Usage Data:</strong> Chat messages, search queries, and interaction patterns with the AI assistant</li>
                <li><strong>Account Information:</strong> Microsoft 365 user identity and authentication tokens</li>
                <li><strong>Technical Data:</strong> Session information, error logs, and performance metrics</li>
            </ul>
            
            <h2>2. How We Use Your Information</h2>
            <p>We use collected information to:</p>
            <ul>
                <li>Provide AI-powered document search and analysis capabilities</li>
                <li>Improve the accuracy and relevance of search results</li>
                <li>Maintain and improve the service performance</li>
                <li>Ensure security and prevent unauthorized access</li>
            </ul>
            
            <h2>3. Data Security</h2>
            <p>We implement industry-standard security measures including:</p>
            <ul>
                <li>Encryption of data in transit and at rest</li>
                <li>Azure Active Directory authentication</li>
                <li>Role-based access controls</li>
                <li>Regular security audits and monitoring</li>
            </ul>
            
            <h2>4. Data Retention</h2>
            <p>We retain your data as follows:</p>
            <ul>
                <li>Document content: Retained while actively used in the system</li>
                <li>Chat history: Retained for 90 days for service improvement</li>
                <li>Technical logs: Retained for 365 days for security and troubleshooting</li>
            </ul>
            
            <h2>5. Your Rights</h2>
            <p>You have the right to:</p>
            <ul>
                <li>Access your personal data processed by the system</li>
                <li>Request correction of inaccurate information</li>
                <li>Request deletion of your personal data</li>
                <li>Withdraw consent for data processing</li>
            </ul>
            
            <h2>6. Contact Information</h2>
            <p>For privacy-related questions or requests, please contact:</p>
            <p><strong>DTCE Engineering</strong><br>
            Email: privacy@dtce.com<br>
            Address: New Zealand</p>
            
            <h2>7. Updates to This Policy</h2>
            <p>We may update this privacy policy from time to time. Any changes will be posted on this page with an updated effective date.</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/terms", response_class=HTMLResponse)
async def terms_of_use():
    """Terms of use endpoint for Teams compliance."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Terms of Use - DTCE AI Assistant</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; line-height: 1.6; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px; }
            h2 { color: #333; margin-top: 30px; }
            .effective-date { background: #f0f8ff; padding: 10px; border-left: 4px solid #0078d4; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Terms of Use</h1>
            <div class="effective-date">
                <strong>Effective Date:</strong> August 17, 2025
            </div>
            
            <h2>1. Acceptance of Terms</h2>
            <p>By using DTCE AI Assistant, you agree to comply with and be bound by these Terms of Use. If you do not agree to these terms, please do not use the service.</p>
            
            <h2>2. Description of Service</h2>
            <p>DTCE AI Assistant is an AI-powered document analysis and search service designed for engineering teams. The service provides:</p>
            <ul>
                <li>Document search and analysis capabilities</li>
                <li>AI-powered question answering from engineering documents</li>
                <li>Project scoping and similarity analysis</li>
                <li>Microsoft Teams integration</li>
            </ul>
            
            <h2>3. Acceptable Use</h2>
            <p>You agree to use the service responsibly and in accordance with:</p>
            <ul>
                <li>All applicable laws and regulations</li>
                <li>Your organization's policies and procedures</li>
                <li>Professional engineering standards and ethics</li>
                <li>Data security and confidentiality requirements</li>
            </ul>
            
            <h2>4. Prohibited Activities</h2>
            <p>You may not use the service to:</p>
            <ul>
                <li>Upload or process illegal, harmful, or inappropriate content</li>
                <li>Attempt to gain unauthorized access to system resources</li>
                <li>Interfere with the service's operation or security</li>
                <li>Share access credentials with unauthorized users</li>
            </ul>
            
            <h2>5. Data and Content</h2>
            <p>You retain ownership of your data and content. By using the service, you grant us the right to:</p>
            <ul>
                <li>Process your documents to provide search and analysis services</li>
                <li>Store necessary data to maintain service functionality</li>
                <li>Use aggregated, anonymized data to improve service quality</li>
            </ul>
            
            <h2>6. Service Availability</h2>
            <p>We strive to maintain high service availability but cannot guarantee:</p>
            <ul>
                <li>Uninterrupted service operation</li>
                <li>Error-free functionality at all times</li>
                <li>Compatibility with all systems and browsers</li>
            </ul>
            
            <h2>7. Intellectual Property</h2>
            <p>The service, including its software, algorithms, and documentation, is protected by intellectual property laws. You may not:</p>
            <ul>
                <li>Copy, modify, or reverse engineer the service</li>
                <li>Use our trademarks without permission</li>
                <li>Create derivative works based on the service</li>
            </ul>
            
            <h2>8. Limitation of Liability</h2>
            <p>To the fullest extent permitted by law, DTCE Engineering shall not be liable for any indirect, incidental, special, or consequential damages arising from your use of the service.</p>
            
            <h2>9. Support and Contact</h2>
            <p>For technical support or questions about these terms, please contact:</p>
            <p><strong>DTCE Engineering</strong><br>
            Email: support@dtce.com<br>
            Address: New Zealand</p>
            
            <h2>10. Changes to Terms</h2>
            <p>We reserve the right to modify these terms at any time. Changes will be effective immediately upon posting. Your continued use of the service constitutes acceptance of any changes.</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
