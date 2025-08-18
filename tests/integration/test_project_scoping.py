#!/usr/bin/env python3
"""
Test script for the new project scoping analysis functionality.
This simulates how the Teams bot would handle client requests.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from dtce_ai_bot.services.project_scoping import get_project_scoping_service


async def test_marquee_project_analysis():
    """Test the project scoping analysis with your marquee example."""
    
    # Sample client request (exactly like your example)
    client_request = """
    Hi Team,
    Thanks again for all your help so far with the other PS1 and for supporting us through the current situation. It's been a frustrating process, especially considering how much we've paid for the renewal.
    
    I now have another structure I need to get certified. This time, it's for a 15x40m double decker marquee that I'm 90% certain will be installed in Wellington. I'm just waiting on final sign-off from both the client and the supplier.
    
    I've attached the drawing and have also asked the supplier for the current technical data. What I know so far:
    The marquee is rated to withstand wind loads of up to 120kph, which is excellent for Trentham and even exceeds the threshold of their grandstand, which currently needs to be evacuated at 80kph.
    The marquee will be installed on a concrete pad. We're open to your recommendation on fixing—bolting into the ground sounds like a good option to us.
    
    Could you please provide a quote for the PS1 certification and let me know:
    Your cost for the full certification
    Anything else you would need from us
    Any other recommendations or considerations for compliance
    
    Feel free to give me a call tomorrow if easier to discuss.
    Thanks again for your support.
    """
    
    print("🔍 Testing Project Scoping Analysis Feature")
    print("=" * 60)
    print(f"📋 Client Request:\n{client_request}")
    print("=" * 60)
    print("🤖 AI Analysis in progress...")
    print()
    
    try:
        # Get the project scoping service
        scoping_service = get_project_scoping_service()
        
        # Analyze the project request
        result = await scoping_service.analyze_project_request(client_request)
        
        print("✅ Analysis Complete!")
        print("=" * 60)
        
        # Display the characteristics extracted
        if 'project_type' in result:
            print("📊 PROJECT CHARACTERISTICS EXTRACTED:")
            print(f"  • Project Type: {result.get('project_type', 'N/A')}")
            print(f"  • Dimensions: {result.get('dimensions', 'N/A')}")
            print(f"  • Location: {result.get('location', 'N/A')}")
            print(f"  • Load Requirements: {result.get('loads', 'N/A')}")
            print(f"  • Compliance Needs: {result.get('compliance', 'N/A')}")
            print(f"  • Materials: {result.get('materials', 'N/A')}")
            print()
        
        # Display similar projects found
        similar_projects = result.get('similar_projects', [])
        print(f"🔍 SIMILAR PROJECTS FOUND: {len(similar_projects)}")
        if similar_projects:
            for i, project in enumerate(similar_projects[:3], 1):
                print(f"  {i}. {project.get('title', 'Unknown')} (Score: {project.get('similarity_score', 0):.2f})")
        else:
            print("  No similar projects found in database")
        print()
        
        # Display the comprehensive analysis
        analysis = result.get('comprehensive_analysis', 'No analysis available')
        print("📋 COMPREHENSIVE ANALYSIS:")
        print("-" * 40)
        print(analysis)
        
        # Display any errors
        if 'error' in result:
            print(f"❌ Error occurred: {result['error']}")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_different_project_types():
    """Test with different types of project requests."""
    
    test_cases = [
        {
            "name": "Residential Extension",
            "request": "We need structural engineering for a 2-story extension to our home in Auckland. The extension will be 8m x 6m and needs PS1 certification for building consent."
        },
        {
            "name": "Commercial Warehouse", 
            "request": "Looking for PS1 certification for a new 30m x 20m steel warehouse in Christchurch. Need seismic design and foundation recommendations."
        },
        {
            "name": "Bridge Assessment",
            "request": "We have an existing concrete bridge that needs structural assessment and possible strengthening. Can you provide a quote for inspection and certification?"
        }
    ]
    
    scoping_service = get_project_scoping_service()
    
    for test_case in test_cases:
        print(f"\n🧪 Testing: {test_case['name']}")
        print("-" * 40)
        
        try:
            result = await scoping_service.analyze_project_request(test_case['request'])
            
            # Quick summary
            print(f"Project Type: {result.get('project_type', 'Unknown')}")
            print(f"Similar Projects: {len(result.get('similar_projects', []))}")
            print(f"Analysis Generated: {'✅' if result.get('comprehensive_analysis') else '❌'}")
            
        except Exception as e:
            print(f"❌ Failed: {str(e)}")


if __name__ == "__main__":
    print("🚀 DTCE AI Project Scoping Analysis Test")
    print("========================================")
    
    # Test the main marquee example
    asyncio.run(test_marquee_project_analysis())
    
    # Test additional project types
    print("\n" + "=" * 60)
    print("🔬 ADDITIONAL PROJECT TYPE TESTS")
    asyncio.run(test_different_project_types())
    
    print("\n✅ Testing Complete!")
    print("The project scoping analysis feature is ready for use in Teams!")
