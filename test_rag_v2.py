"""
Test Script for RAG V2 Architecture

This script verifies the end-to-end RAG V2 pipeline, including:
- Intent Classification
- Dynamic Filter Construction
- Hybrid Search with Semantic Ranking
- Answer Synthesis

It tests each of the 6 knowledge categories to ensure proper routing.
"""
import asyncio
import os
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI
import structlog

from dtce_ai_bot.services.rag_handler import RAGHandler

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger(__name__)

# --- Test Configuration ---
TEST_QUERIES = [
    {
        "id": "PROJECT_YEAR",
        "query": "what is project 225?",
        "expected_intent": "Project",
        "expected_filter_part": "folder ge 'Projects/225/' and folder lt 'Projects/226'"
    },
    {
        "id": "PROJECT_JOB_NUMBER",
        "query": "tell me about job 225221",
        "expected_intent": "Project",
        "expected_filter_part": "folder ge 'Projects/225/225221/' and folder lt 'Projects/225/225222'"
    },
    {
        "id": "POLICY",
        "query": "what is the company's wellness policy?",
        "expected_intent": "Policy",
        "expected_filter_part": "(folder ge 'Policies/' and folder lt 'Policies~') or (folder ge 'Health and Safety/' and folder lt 'Health and Safety~') or (folder ge 'Wellbeing/' and folder lt 'Wellbeing~')"
    },
    {
        "id": "PROCEDURE",
        "query": "how do I use the wind speed spreadsheet?",
        "expected_intent": "Procedure",
        "expected_filter_part": "(folder ge 'Procedures/' and folder lt 'Procedures~') or (folder ge 'How to Handbooks/' and folder lt 'How to Handbooks~') or (folder ge 'H2H/' and folder lt 'H2H~')"
    },
    {
        "id": "STANDARDS",
        "query": "what does NZS 3604 say about wind loads?",
        "expected_intent": "Standards",
        "expected_filter_part": "(folder ge 'Standards/' and folder lt 'Standards~') or (folder ge 'NZ Standards/' and folder lt 'NZ Standards~') or (folder ge 'NZS/' and folder lt 'NZS~')"
    },
    {
        "id": "CLIENT",
        "query": "who is the client for the Smith Project?",
        "expected_intent": "Client",
        "expected_filter_part": "folder ge 'Clients/' and folder lt 'Clients~'"
    },
    {
        "id": "GENERAL_KNOWLEDGE",
        "query": "what is the maximum wind load on a commercial building?",
        "expected_intent": "General_Knowledge",
        "expected_filter_part": None  # No filter
    },
]

async def main():
    """
    Main function to run the RAG V2 test suite.
    """
    # --- Load Environment Variables ---
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    logger.info(f"Attempting to load .env file from: {env_path}")
    if not os.path.exists(env_path):
        logger.error(".env file not found at the expected path. Please ensure it exists.")
        return
        
    load_dotenv(dotenv_path=env_path, verbose=True)
    
    AZURE_SEARCH_SERVICE_ENDPOINT = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
    AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
    AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    # --- Debug: Print loaded variables ---
    print("\n--- DEBUG: Loaded Environment Variables ---")
    print(f"AZURE_SEARCH_SERVICE_ENDPOINT: {'Loaded' if AZURE_SEARCH_SERVICE_ENDPOINT else 'NOT FOUND'}")
    print(f"AZURE_SEARCH_INDEX_NAME: {'Loaded' if AZURE_SEARCH_INDEX_NAME else 'NOT FOUND'}")
    print(f"AZURE_SEARCH_API_KEY: {'Loaded' if AZURE_SEARCH_API_KEY else 'NOT FOUND'}")
    print(f"AZURE_OPENAI_ENDPOINT: {'Loaded' if AZURE_OPENAI_ENDPOINT else 'NOT FOUND'}")
    print(f"AZURE_OPENAI_API_KEY: {'Loaded' if AZURE_OPENAI_API_KEY else 'NOT FOUND'}")
    print(f"AZURE_OPENAI_DEPLOYMENT_NAME: {'Loaded' if AZURE_OPENAI_DEPLOYMENT_NAME else 'NOT FOUND'}")
    print("-----------------------------------------\n")

    # --- Validate Variables ---
    if not all([AZURE_SEARCH_SERVICE_ENDPOINT, AZURE_SEARCH_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME]):
        logger.error("One or more critical environment variables are missing. Halting test.")
        return
    
    # --- Initialize Clients ---
    logger.info("Initializing clients...")
    
    # Azure AI Search Client
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_SERVICE_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY)
    )
    
    # Azure OpenAI Client
    openai_client = AsyncAzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version="2024-02-01"
    )
    
    # RAG Handler (V2)
    from dtce_ai_bot.config.settings import get_settings
    settings = get_settings()
    
    rag_handler = RAGHandler(
        search_client=search_client,
        openai_client=openai_client,
        model_name=settings.azure_openai_deployment_name,
        settings=settings
    )
    
    logger.info("Clients initialized. Starting test queries...")
    
    # --- Run Test Queries ---
    for test in TEST_QUERIES:
        query_id = test["id"]
        query = test["query"]
        
        print("\n" + "="*80)
        logger.info(f"RUNNING TEST: {query_id}", query=query)
        print("="*80)
        
        try:
            # Correctly call the V2 service and its `process_query` method
            result = await rag_handler.rag_service_v2.process_query(
                user_query=query
            )
            
            # --- Print Results ---
            print(f"\n[QUERY]: {query}")
            print(f"\n[INTENT]: {result.get('intent')}")
            print(f"[SEARCH FILTER]: {result.get('search_filter')}")
            print(f"\n[ANSWER]:\n{result.get('answer')}")
            
            print("\n[SOURCES]:")
            sources = result.get('sources', [])
            if sources:
                for i, source in enumerate(sources, 1):
                    print(f"  {i}. {source.get('title')} (Folder: {source.get('folder')})")
                    print(f"     Relevance: {source.get('relevance_score'):.2f}")
            else:
                print("  No sources found.")
            
            # --- Verification ---
            print("\n[VERIFICATION]:")
            intent_match = result.get('intent') == test['expected_intent']
            print(f"  - Intent Correct: {'✅' if intent_match else '❌'} (Expected: {test['expected_intent']}, Got: {result.get('intent')})")
            
            filter_str = result.get('search_filter')
            expected_filter = test['expected_filter_part']
            
            if expected_filter is None:
                filter_match = filter_str is None
            else:
                filter_match = filter_str and expected_filter in filter_str
                
            print(f"  - Filter Correct: {'✅' if filter_match else '❌'}")

        except Exception as e:
            logger.error("Test failed with exception", test_id=query_id, error=str(e))

        print("\n" + "="*80 + "\n")
        
        # Add a delay to avoid hitting API rate limits
        await asyncio.sleep(20)  # 20-second delay between tests


if __name__ == "__main__":
    asyncio.run(main())
