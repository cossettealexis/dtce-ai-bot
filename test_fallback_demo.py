#!/usr/bin/env python3
"""
Demo script showing the enhanced DocumentQA fallback logic.
This demonstrates how the system will work when Azure Search results are insufficient.
"""

class MockDocumentQAService:
    """Mock version of DocumentQAService to demonstrate fallback logic."""
    
    def __init__(self):
        self.min_search_score = 1.0
        self.min_document_count = 3
    
    def should_fallback_to_sharepoint(self, azure_docs, question):
        """Test the fallback logic."""
        
        # No documents found - definitely need fallback
        if not azure_docs:
            return True, "No documents found in Azure Search"
        
        # Too few documents found
        if len(azure_docs) < self.min_document_count:
            return True, f"Only {len(azure_docs)} documents found (need {self.min_document_count})"
        
        # Check if search scores are too low
        high_score_docs = [doc for doc in azure_docs 
                          if doc.get('@search.score', 0) >= self.min_search_score]
        
        if len(high_score_docs) < 2:
            return True, f"Only {len(high_score_docs)} high-relevance documents (score >= {self.min_search_score})"
        
        # Check for specific patterns that might need SharePoint fallback
        question_lower = question.lower()
        sharepoint_indicators = [
            'latest', 'recent', 'current', 'new', 'updated',
            'sharepoint', 'suitefiles', 'live', 'online'
        ]
        
        for indicator in sharepoint_indicators:
            if indicator in question_lower:
                return True, f"Question contains SharePoint indicator: '{indicator}'"
        
        return False, "Azure Search results appear sufficient"

def test_fallback_scenarios():
    """Test various scenarios for fallback logic."""
    
    service = MockDocumentQAService()
    
    # Test scenarios
    scenarios = [
        {
            "name": "No results from Azure Search",
            "azure_docs": [],
            "question": "What is the design standard for concrete?"
        },
        {
            "name": "Few results, low relevance scores",
            "azure_docs": [
                {"@search.score": 0.5, "filename": "doc1.pdf"},
                {"@search.score": 0.3, "filename": "doc2.pdf"}
            ],
            "question": "Project 219 structural calculations"
        },
        {
            "name": "Good results, should not fallback",
            "azure_docs": [
                {"@search.score": 2.5, "filename": "structural_calc.pdf"},
                {"@search.score": 2.1, "filename": "design_spec.pdf"},
                {"@search.score": 1.8, "filename": "analysis.xlsx"},
                {"@search.score": 1.2, "filename": "report.docx"}
            ],
            "question": "Project 219 structural calculations"
        },
        {
            "name": "Question asking for 'latest' documents",
            "azure_docs": [
                {"@search.score": 2.0, "filename": "old_report.pdf"},
                {"@search.score": 1.5, "filename": "analysis.pdf"},
                {"@search.score": 1.3, "filename": "spec.docx"}
            ],
            "question": "What is the latest version of the structural design?"
        },
        {
            "name": "Question mentioning SharePoint",
            "azure_docs": [
                {"@search.score": 1.8, "filename": "doc1.pdf"},
                {"@search.score": 1.6, "filename": "doc2.pdf"},
                {"@search.score": 1.4, "filename": "doc3.pdf"}
            ],
            "question": "Can you check SharePoint for the updated drawings?"
        }
    ]
    
    print("🧪 TESTING SHAREPOINT FALLBACK LOGIC")
    print("=" * 60)
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print(f"   Question: '{scenario['question']}'")
        print(f"   Azure Search Results: {len(scenario['azure_docs'])} documents")
        
        if scenario['azure_docs']:
            scores = [doc.get('@search.score', 0) for doc in scenario['azure_docs']]
            print(f"   Relevance Scores: {scores}")
        
        should_fallback, reason = service.should_fallback_to_sharepoint(
            scenario['azure_docs'], 
            scenario['question']
        )
        
        status = "✅ FALLBACK TO SHAREPOINT" if should_fallback else "⚡ USE AZURE SEARCH"
        print(f"   Decision: {status}")
        print(f"   Reason: {reason}")

def demonstrate_enhanced_workflow():
    """Show the complete enhanced workflow."""
    
    print("\n" + "=" * 60)
    print("🚀 ENHANCED WORKFLOW DEMONSTRATION")
    print("=" * 60)
    
    workflow_steps = [
        "1. 🔍 User asks: 'What are the latest NZS standards for concrete design?'",
        "2. 🔎 Azure Search finds 2 documents (below threshold of 3)",
        "3. 📊 System detects: insufficient results + 'latest' keyword",
        "4. 🔄 FALLBACK TRIGGERED: Search SharePoint/SuiteFiles",
        "5. 📁 SharePoint search targets: Engineering/Standards/ folder",
        "6. 📄 SharePoint finds: 8 recent NZS standard documents",
        "7. 🤖 AI gets: 2 Azure docs + 8 SharePoint docs = comprehensive context",
        "8. ✨ User receives: Complete answer with latest standards from both sources"
    ]
    
    for step in workflow_steps:
        print(f"   {step}")
    
    print("\n🎯 BENEFITS:")
    benefits = [
        "✅ No more 'I couldn't find documents' responses",
        "✅ Always searches the most up-to-date SharePoint content", 
        "✅ Combines indexed + live document sources",
        "✅ Intelligent fallback only when needed (preserves performance)",
        "✅ Transparent source tracking (user knows where info came from)"
    ]
    
    for benefit in benefits:
        print(f"   {benefit}")

if __name__ == "__main__":
    test_fallback_scenarios()
    demonstrate_enhanced_workflow()
    
    print(f"\n{'='*60}")
    print("🎉 FALLBACK SYSTEM READY!")
    print("Your AI will now be much smarter and never leave users empty-handed!")
    print("="*60)
