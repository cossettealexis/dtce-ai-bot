import asyncio
import os
import sys
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient

# Add project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file
load_dotenv()

# Import the RAG service
from dtce_ai_bot.services.azure_rag_service_v2 import AzureRAGService

async def run_test_query():
    """
    Initializes the RAG service and runs a test query.
    """
    # --- Configuration ---
    AZURE_SEARCH_SERVICE_ENDPOINT = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
    AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
    AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    # --- Validation ---
    required_vars = {
        "AZURE_SEARCH_SERVICE_ENDPOINT": AZURE_SEARCH_SERVICE_ENDPOINT,
        "AZURE_SEARCH_INDEX_NAME": AZURE_SEARCH_INDEX_NAME,
        "AZURE_SEARCH_API_KEY": AZURE_SEARCH_API_KEY,
        "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
        "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
        "AZURE_OPENAI_DEPLOYMENT_NAME": AZURE_OPENAI_DEPLOYMENT_NAME,
    }

    for var_name, value in required_vars.items():
        if not value:
            print(f"❌ Error: Environment variable '{var_name}' is not set.")
            return

    print("✅ All required environment variables are set.")

    # --- Initialize Clients ---
    try:
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_SERVICE_ENDPOINT,
            index_name=AZURE_SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(AZURE_SEARCH_API_KEY)
        )
        
        openai_client = AsyncAzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2023-12-01-preview"
        )
        
        print("✅ Azure clients initialized successfully.")
    except Exception as e:
        print(f"❌ Error initializing Azure clients: {e}")
        return

    # --- Initialize RAG Service ---
    rag_service = AzureRAGService(
        search_client=search_client,
        openai_client=openai_client,
        model_name=AZURE_OPENAI_DEPLOYMENT_NAME
    )
    print("✅ RAG Service initialized.")

    # --- Run Test Query ---
    test_question = "what is the seismic bracing requirements for project 225"
    print(f"\n🤔 Running test query: '{test_question}'")
    
    try:
        result = await rag_service.process_query(test_question)
        
        print("\n--- Query Result ---")
        print(f"💬 Answer: {result.get('answer', 'No answer returned.')}")
        
        sources = result.get('sources', [])
        if sources:
            print("\n📚 Sources:")
            for i, source in enumerate(sources, 1):
                filename = source.get('filename', 'Unknown')
                folder = source.get('folder', 'N/A')
                project_name = source.get('project_name', 'N/A')
                print(f"  {i}. Filename: {filename}")
                print(f"     Folder: {folder}")
                print(f"     Project: {project_name}")
        else:
            print("\n📚 No sources found.")

        print(f"\n🔍 Search Filter Used: {result.get('search_filter', 'N/A')}")
        print(f"📄 Total Documents Found: {result.get('total_documents', 0)}")
            
        print("\n--- End of Result ---")

    except Exception as e:
        print(f"❌ An error occurred during the query: {e}")
    finally:
        # Cleanly close the clients
        await search_client.close()
        await openai_client.close()
        print("\n✅ Test finished and clients closed.")


if __name__ == "__main__":
    asyncio.run(run_test_query())
