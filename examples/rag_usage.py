"""
RAG System Usage Examples

Examples demonstrating how to use the modular RAG system.
"""

import os
from dtce_ai_bot.rag import RAGPipeline, RAGConfig


def basic_usage_example():
    """Basic RAG usage example"""
    
    # Create configuration (loads from environment)
    config = RAGConfig.from_env()
    
    # Create and initialize pipeline
    pipeline = RAGPipeline(config)
    
    # Initialize the system (creates index if needed)
    if not pipeline.initialize():
        print("Failed to initialize RAG system")
        return
    
    # Ingest a sample document
    sample_doc = {
        "content": """
        Building Code Requirements for Fire Safety
        
        All commercial buildings must comply with fire safety standards including:
        1. Automatic sprinkler systems in buildings over 5,000 sq ft
        2. Fire-rated assemblies between occupancy types
        3. Emergency egress lighting with battery backup
        4. Smoke detection systems in all occupied spaces
        
        The building code requires that sprinkler systems be designed according to NFPA 13 standards.
        """,
        "metadata": {
            "title": "Fire Safety Requirements",
            "document_type": "building_code",
            "standard_code": "IBC-2021",
            "section": "Chapter 9",
            "category": "fire_safety"
        }
    }
    
    # Ingest the document
    success = pipeline.ingest_document(
        sample_doc["content"], 
        sample_doc["metadata"]
    )
    
    if success:
        print("Document ingested successfully")
    else:
        print("Failed to ingest document")
        return
    
    # Ask questions
    questions = [
        "What are the sprinkler requirements for commercial buildings?",
        "What fire safety standards apply to buildings?",
        "What is required for emergency lighting?"
    ]
    
    for question in questions:
        print(f"\nQuestion: {question}")
        
        response = pipeline.answer_question(question)
        
        print(f"Answer: {response['answer']}")
        print(f"Confidence: {response['confidence']}")
        print(f"Sources: {len(response['sources'])}")
        
        if response['sources']:
            print("Source preview:", response['sources'][0]['content_preview'][:100] + "...")


def advanced_usage_example():
    """Advanced RAG usage with conversation history and filters"""
    
    # Create pipeline
    pipeline = RAGPipeline()
    pipeline.initialize()
    
    # Conversation history
    conversation_history = [
        {
            "question": "What are building code requirements?",
            "answer": "Building codes specify minimum standards for construction..."
        }
    ]
    
    # Use filters to search specific document types
    filters = {
        "document_type": "building_code",
        "category": "fire_safety"
    }
    
    question = "What are the specific requirements for sprinkler systems?"
    
    response = pipeline.answer_question(
        question=question,
        conversation_history=conversation_history,
        filters=filters
    )
    
    print(f"Filtered Question: {question}")
    print(f"Answer: {response['answer']}")


def document_ingestion_example():
    """Example of ingesting multiple documents"""
    
    pipeline = RAGPipeline()
    pipeline.initialize()
    
    # Multiple documents
    documents = [
        {
            "content": "HVAC systems must be designed according to ASHRAE standards...",
            "metadata": {
                "title": "HVAC Requirements", 
                "document_type": "standard",
                "standard_code": "ASHRAE-90.1"
            }
        },
        {
            "content": "Structural steel connections must meet AWS welding standards...",
            "metadata": {
                "title": "Steel Connection Standards",
                "document_type": "standard", 
                "standard_code": "AWS-D1.1"
            }
        }
    ]
    
    # Batch ingestion
    results = pipeline.ingest_documents(documents)
    
    print(f"Ingestion Results:")
    print(f"- Total documents: {results['total_documents']}")
    print(f"- Successful: {results['successful']}")
    print(f"- Total chunks: {results['total_chunks']}")
    print(f"- Success rate: {results['success_rate']:.2%}")


def system_status_example():
    """Example of checking system status"""
    
    pipeline = RAGPipeline()
    pipeline.initialize()
    
    status = pipeline.get_system_status()
    
    print("System Status:")
    print(f"- Config valid: {status['config_valid']}")
    print(f"- Document count: {status['index_stats'].get('document_count', 'unknown')}")
    print(f"- Vector search enabled: {status['index_stats'].get('vector_search_enabled', False)}")
    
    # Search existing documents
    documents = pipeline.search_documents("*", top=5)
    print(f"- Documents in index: {len(documents)}")


if __name__ == "__main__":
    # Set environment variables (replace with your actual values)
    # os.environ["AZURE_SEARCH_SERVICE_NAME"] = "your-search-service"
    # os.environ["AZURE_SEARCH_ADMIN_KEY"] = "your-admin-key"  
    # os.environ["AZURE_OPENAI_ENDPOINT"] = "https://your-openai.openai.azure.com/"
    # os.environ["AZURE_OPENAI_API_KEY"] = "your-openai-key"
    
    print("=== Basic Usage Example ===")
    # basic_usage_example()
    
    print("\n=== Advanced Usage Example ===")
    # advanced_usage_example()
    
    print("\n=== Document Ingestion Example ===")
    # document_ingestion_example()
    
    print("\n=== System Status Example ===")
    # system_status_example()
    
    print("\nUncomment the examples and set your Azure credentials to run.")
