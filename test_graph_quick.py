#!/usr/bin/env python3
"""
Quick test script to check Microsoft Graph API connectivity without full folder scanning.
"""

import asyncio
import structlog
from dtce_ai_bot.integrations.microsoft_graph import MicrosoftGraphClient

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

async def test_graph_connection():
    """Test basic Microsoft Graph connectivity."""
    try:
        logger.info("Testing Microsoft Graph API connection...")
        
        client = MicrosoftGraphClient()
        
        # Test 1: Get access token
        logger.info("Step 1: Testing authentication...")
        token = await client._get_access_token()
        logger.info("Authentication successful", token_length=len(token))
        
        # Test 2: Get sites
        logger.info("Step 2: Testing sites retrieval...")
        sites = await client.get_sites()
        logger.info("Sites retrieved", count=len(sites))
        for site in sites[:3]:  # Show first 3 sites
            logger.info("Site found", name=site.get("displayName"), id=site.get("id"))
        
        # Test 3: Find Suitefiles site
        logger.info("Step 3: Testing Suitefiles site lookup...")
        suitefiles_site = await client.get_site_by_name("suitefiles")
        if not suitefiles_site:
            logger.warning("Suitefiles site not found, trying 'dtce' site")
            suitefiles_site = await client.get_site_by_name("dtce")
        
        if suitefiles_site:
            site_id = suitefiles_site["id"]
            logger.info("Found target site", site_id=site_id, name=suitefiles_site.get("displayName"))
            
            # Test 4: Get drives for the site
            logger.info("Step 4: Testing drives retrieval...")
            drives = await client.get_drives(site_id)
            logger.info("Drives retrieved", count=len(drives))
            for drive in drives:
                logger.info("Drive found", name=drive.get("name"), id=drive.get("id"))
            
            if drives:
                # Test 5: Get a small sample of files from first drive (non-recursive, root only)
                drive_id = drives[0]["id"]
                logger.info("Step 5: Testing root level file listing...")
                files = await client.get_files_in_drive(site_id, drive_id, max_depth=1)  # Very shallow
                logger.info("Root files retrieved", count=len(files))
                
                # Show sample files
                for file in files[:5]:  # Show first 5 files
                    if "file" in file:
                        logger.info("File found", name=file.get("name"), size=file.get("size"))
                
        else:
            logger.error("No suitable SharePoint site found")
            
        logger.info("Microsoft Graph API test completed successfully!")
        
    except Exception as e:
        logger.error("Microsoft Graph API test failed", error=str(e), exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_graph_connection())
