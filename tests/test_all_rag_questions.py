#!/usr/bin/env python3
"""
Test ALL specific questions mentioned in RAG.TXT to verify compliance
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.integrations.azure.search_client import AzureSearchClient
from dtce_ai_bot.services.document_qa import DocumentQAService

async def test_all_rag_questions():
    """Test ALL specific questions from RAG.TXT"""
    
    print("🚀 Testing ALL RAG.TXT Questions for Compliance...")
    
    # Initialize services
    settings = get_settings()
    search_client = AzureSearchClient()
    qa_service = DocumentQAService(search_client.search_client)
    
    # ALL questions from RAG.TXT organized by category
    rag_questions = {
        "NZ Standards & Codes": [
            "Please tell me the minimum clear cover requirements as per NZS code in designing a concrete element.",
            "Tell me what particular clause talks about the detailing requirements in designing a beam.",
            "Tell me the strength reduction factors used when I'm designing a beam or when considering seismic actions.",
            "Tell me what particular NZS structural code to refer to if I'm designing a composite slab to make it a floor diaphragm?"
        ],
        
        "Past Project References": [
            "I am designing a precast panel, please tell me all past projects that have a scope about the following keywords or description: Precast Panel, Precast, Precast Connection, Unispans",
            "I am designing a timber retaining wall, it's going to be 3m tall; can you provide me example past projects and help me draft a design philosophy?",
            "Please advise me on what DTCE has done in the past for a 2-storey concrete precast panel building maybe with a timber-framed structure on top?"
        ],
        
        "Product Specifications": [
            "I'm looking for a specific proprietary product that's suitable to provide a waterproofing layer to a concrete block wall that DTCE has used in the past.",
            "I need timber connection details for joining a timber beam to a column. Please provide specifications for the proprietary products DTCE usually refers to, as well as other options to consider.",
            "What are the available sizes of LVL timber on the market? Please list all links containing the sizes and price per length. Also, confirm if the suppliers are located near Wellington."
        ],
        
        "Online References": [
            "I am currently designing a composite beam but need to make it haunched/tapered. Please provide related references or online threads mentioning the keyword 'tapered composite beam', preferably from anonymous structural engineers.",
            "Please provide design guidelines for a reinforced concrete column to withstand both seismic and gravity actions. If possible, include a legitimate link that gives direct access to the specific design guidelines."
        ],
        
        "Builder/Contact Information": [
            "My client is asking about builders that we've worked with before. Can you find any companies and/or contact details that constructed a design for us in the past 3 years and didn't seem to have too many issues during construction? The design job I'm dealing with now is a steel structure retrofit of an old brick building."
        ],
        
        "Templates & Forms": [
            "Please provide me with the template we generally use for preparing a PS1. Also, please provide me with the direct link to access it on SuiteFiles.",
            "I wasn't able to find a PS3 template in SuiteFiles. Please provide me with a legitimate link to a general PS3 template that can be submitted to any council in New Zealand.",
            "Please provide me with the link or the file for the timber beam design spreadsheet that DTCE usually uses or has used."
        ],
        
        "Scenario-Based Technical": [
            "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed.",
            "What foundation systems have we used for houses on steep slopes in Wellington?",
            "Find projects where we designed concrete shear walls for seismic strengthening.",
            "What connection details have we used for balconies on coastal apartment buildings?"
        ],
        
        "Problem-Solving & Lessons Learned": [
            "What issues have we run into when using screw piles in soft soils?",
            "Summarise any lessons learned from projects where retaining walls failed during construction.",
            "What waterproofing methods have worked best for basement walls in high water table areas?"
        ],
        
        "Regulatory & Consent Precedents": [
            "Give me examples of projects where council questioned our wind load calculations.",
            "How have we approached alternative solution applications for non-standard stair designs?",
            "Show me precedent for using non-standard bracing in heritage building retrofits."
        ],
        
        "Cost & Time Insights": [
            "How long does it typically take from concept to PS1 for small commercial alterations?",
            "What's the typical cost range for structural design of multi-unit residential projects?",
            "Find projects where the structural scope expanded significantly after concept design."
        ],
        
        "Best Practices & Templates": [
            "What's our standard approach to designing steel portal frames for industrial buildings?",
            "Show me our best example drawings for timber diaphragm design.",
            "What calculation templates do we have for multi-storey timber buildings?"
        ],
        
        "Materials & Methods Comparisons": [
            "When have we chosen precast concrete over in-situ concrete for floor slabs, and why?",
            "What timber treatment levels have we specified for exterior beams in coastal conditions?",
            "Compare different seismic retrofit methods we've used for unreinforced masonry buildings."
        ],
        
        "Internal Knowledge Mapping": [
            "Which engineers have experience with tilt-slab construction?",
            "Who has documented expertise in pile design for soft coastal soils?",
            "Show me project notes authored by our senior engineer on seismic strengthening."
        ]
    }
    
    total_questions = sum(len(questions) for questions in rag_questions.values())
    print(f"\n🔍 Testing {total_questions} questions from RAG.TXT...\n")
    
    results = {}
    question_count = 0
    
    for category, questions in rag_questions.items():
        print(f"📂 **{category}** ({len(questions)} questions)")
        print("=" * 80)
        
        category_results = []
        
        for question in questions:
            question_count += 1
            print(f"\n📝 Q{question_count}: {question[:80]}...")
            print("-" * 80)
            
            try:
                response = await qa_service.answer_question(question)
                
                rag_type = response.get('rag_type', response.get('search_type', 'Unknown'))
                confidence = response.get('confidence', 'Unknown')
                docs_found = response.get('documents_searched', 0)
                answer = response.get('answer', 'No answer')
                
                # Analyze response quality
                quality = "✅ GOOD" if confidence == 'high' and docs_found > 0 else \
                         "⚠️ MEDIUM" if confidence == 'medium' or docs_found > 0 else \
                         "❌ POOR"
                
                print(f"🎯 Type: {rag_type}")
                print(f"📊 Quality: {quality} (Confidence: {confidence}, Docs: {docs_found})")
                print(f"💬 Answer: {answer[:150]}...")
                
                if response.get('sources'):
                    print(f"🔗 Sources: {len(response['sources'])} found")
                
                category_results.append({
                    'question': question,
                    'rag_type': rag_type,
                    'confidence': confidence,
                    'docs_found': docs_found,
                    'has_sources': bool(response.get('sources')),
                    'quality': quality,
                    'answer_length': len(answer)
                })
                
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                category_results.append({
                    'question': question,
                    'error': str(e),
                    'quality': "❌ ERROR"
                })
        
        results[category] = category_results
        print(f"\n📊 {category} Summary: {len([r for r in category_results if r.get('quality', '').startswith('✅')])} good, {len([r for r in category_results if r.get('quality', '').startswith('⚠️')])} medium, {len([r for r in category_results if not r.get('quality', '').startswith('✅') and not r.get('quality', '').startswith('⚠️')])} poor")
        print("\n" + "="*80 + "\n")
    
    # Generate summary report
    print("📈 **FINAL RAG.TXT COMPLIANCE REPORT**")
    print("="*80)
    
    total_good = 0
    total_medium = 0
    total_poor = 0
    
    for category, category_results in results.items():
        good = len([r for r in category_results if r.get('quality', '').startswith('✅')])
        medium = len([r for r in category_results if r.get('quality', '').startswith('⚠️')])
        poor = len(category_results) - good - medium
        
        total_good += good
        total_medium += medium
        total_poor += poor
        
        print(f"{category}: {good}✅ {medium}⚠️ {poor}❌")
    
    print(f"\n🎯 **OVERALL COMPLIANCE:**")
    print(f"✅ Good responses: {total_good}/{total_questions} ({total_good/total_questions*100:.1f}%)")
    print(f"⚠️ Medium responses: {total_medium}/{total_questions} ({total_medium/total_questions*100:.1f}%)")
    print(f"❌ Poor responses: {total_poor}/{total_questions} ({total_poor/total_questions*100:.1f}%)")
    
    compliance_score = (total_good + total_medium * 0.5) / total_questions * 100
    print(f"📊 **RAG.TXT Compliance Score: {compliance_score:.1f}%**")
    
    if compliance_score >= 80:
        print("🎉 EXCELLENT: System meets RAG.TXT requirements!")
    elif compliance_score >= 60:
        print("✅ GOOD: System mostly meets RAG.TXT requirements")
    else:
        print("⚠️ NEEDS IMPROVEMENT: System needs work to meet RAG.TXT requirements")

if __name__ == "__main__":
    asyncio.run(test_all_rag_questions())
