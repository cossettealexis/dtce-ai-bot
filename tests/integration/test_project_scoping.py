#!/usr/bin/env python3
"""
Test script for the new project scoping analysis functionality.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

from dtce_ai_bot.services.project_scoping import get_project_scoping_service


async def test_project_scoping():
    """Test the project scoping analysis with the example client request."""
    
    # Example client request from the user
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
    
    print("🔍 Testing Project Scoping Analysis...")
    print("=" * 60)
    print("CLIENT REQUEST:")
    print(client_request)
    print("=" * 60)
    print("\n🚀 Analyzing...")
    
    try:
        # Get the project scoping service
        scoping_service = get_project_scoping_service()
        
        # Analyze the project request
        result = await scoping_service.analyze_project_request(client_request)
        
        print("\n✅ ANALYSIS COMPLETE!")
        print("=" * 60)
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            return
        
        # Display the main analysis
        if 'analysis' in result:
            print("📋 COMPREHENSIVE ANALYSIS:")
            print(result['analysis'])
            print("\n" + "=" * 60)
        
        # Display characteristics
        if 'characteristics' in result:
            print("\n📊 EXTRACTED CHARACTERISTICS:")
            chars = result['characteristics']
            for key, value in chars.items():
                if key != 'raw_analysis' and value:
                    print(f"• {key.replace('_', ' ').title()}: {value}")
            print()
        
        # Display similar projects
        if 'similar_projects' in result:
            similar = result['similar_projects']
            print(f"\n🔍 FOUND {len(similar)} SIMILAR PROJECTS:")
            for i, project in enumerate(similar[:3], 1):
                title = project.get('title', 'Unknown')
                project_id = project.get('project', 'N/A')
                similarity = project.get('similarity_score', 0)
                print(f"{i}. {title} (Project {project_id}) - {similarity:.1%} similarity")
        
        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_project_scoping())
