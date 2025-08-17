#!/usr/bin/env python3
"""
Test to verify Bot Framework authentication configuration.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

async def test_bot_framework_auth():
    """Test Bot Framework authentication setup."""
    
    print("🔐 Testing Bot Framework Authentication Configuration")
    print("=" * 60)
    
    try:
        from dtce_ai_bot.config.settings import get_settings
        from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
        from botbuilder.core.authentication import JwtTokenValidation, AuthenticationConfiguration
        
        settings = get_settings()
        
        print("📋 Current Bot Configuration:")
        print(f"  App ID: {settings.microsoft_app_id}")
        print(f"  Password: {'***' + settings.microsoft_app_password[-4:] if settings.microsoft_app_password else 'NOT SET'}")
        print(f"  Tenant: {getattr(settings, 'microsoft_app_tenant_id', 'NOT SET')}")
        print(f"  App Type: {getattr(settings, 'microsoft_app_type', 'NOT SET')}")
        
        # Check credentials
        if not settings.microsoft_app_id:
            print("❌ CRITICAL: MICROSOFT_APP_ID is empty!")
            return False
            
        if not settings.microsoft_app_password:
            print("❌ CRITICAL: MICROSOFT_APP_PASSWORD is empty!")
            return False
        
        # Test adapter creation
        bot_settings = BotFrameworkAdapterSettings(
            app_id=settings.microsoft_app_id,
            app_password=settings.microsoft_app_password
        )
        
        adapter = BotFrameworkAdapter(bot_settings)
        print("✅ BotFrameworkAdapter created successfully")
        
        # Test authentication configuration
        auth_config = AuthenticationConfiguration()
        print(f"✅ Authentication configuration created")
        
        # Check if the adapter can validate tokens (this will show the real issue)
        print("\n🔍 Testing JWT Token Validation Setup:")
        
        # Test with an obviously fake token to see the validation process
        fake_auth_header = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.fake.token"
        
        try:
            # This should fail, but will show us HOW it fails
            await JwtTokenValidation.validate_auth_header(
                auth_header=fake_auth_header,
                credentials=bot_settings,
                channel_service_url="https://smba.trafficmanager.net/teams/",
                channel_id="msteams"
            )
            print("❌ UNEXPECTED: Fake token was accepted!")
            
        except Exception as e:
            print(f"✅ EXPECTED: Fake token rejected - {type(e).__name__}: {e}")
            
            # Check what type of error we get - this tells us about the auth setup
            error_msg = str(e).lower()
            if "signature" in error_msg:
                print("✅ JWT signature validation is working")
            elif "issuer" in error_msg:
                print("✅ JWT issuer validation is working")
            elif "audience" in error_msg:
                print("✅ JWT audience validation is working")
            elif "segments" in error_msg:
                print("✅ JWT format validation is working")
            else:
                print(f"⚠️  Unexpected auth error type: {e}")
        
        print("\n🔍 Testing Token Requirements:")
        
        # Check what the adapter expects for valid tokens
        expected_issuer = "https://api.botframework.com"
        expected_audience = settings.microsoft_app_id
        
        print(f"  Expected Token Issuer: {expected_issuer}")
        print(f"  Expected Token Audience: {expected_audience}")
        print(f"  Valid Service URLs: smba.trafficmanager.net, *.botframework.com")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

async def test_endpoint_with_better_auth():
    """Test the endpoint with a properly structured (but still fake) JWT."""
    
    print("\n🌐 Testing Endpoint with Proper JWT Structure")
    print("-" * 50)
    
    import httpx
    import base64
    import json
    from datetime import datetime, UTC, timedelta
    
    # Create a properly structured (but fake) JWT
    # This won't work because we don't have Microsoft's private key,
    # but it will show us exactly what validation step fails
    
    header = {
        "alg": "RS256",
        "typ": "JWT",
        "x5t": "fake-thumbprint"
    }
    
    # Create payload that LOOKS like a Microsoft Bot Framework token
    payload = {
        "iss": "https://api.botframework.com",
        "aud": "c185c174-26f6-4876-b847-0a423d07d1f3",  # Our app ID
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(UTC).timestamp()),
        "nbf": int(datetime.now(UTC).timestamp()),
        "sub": "c185c174-26f6-4876-b847-0a423d07d1f3",
        "serviceurl": "https://smba.trafficmanager.net/teams/",
        "appid": "c185c174-26f6-4876-b847-0a423d07d1f3"
    }
    
    # Encode header and payload (but we can't sign it properly)
    header_encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    
    # Create fake JWT (this will fail signature validation, which is expected)
    fake_jwt = f"{header_encoded}.{payload_encoded}.fake-signature"
    
    print(f"📄 Testing with structured JWT:")
    print(f"  Issuer: {payload['iss']}")
    print(f"  Audience: {payload['aud']}")
    print(f"  App ID: {payload['appid']}")
    
    # Test the endpoint
    base_url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
    endpoint = f"{base_url}/api/teams/messages"
    
    teams_activity = {
        "type": "message",
        "id": "test-message-123",
        "timestamp": datetime.now(UTC).isoformat(),
        "channelId": "msteams",
        "serviceUrl": "https://smba.trafficmanager.net/teams/",
        "from": {
            "id": "29:test-user-id",
            "name": "Test User"
        },
        "conversation": {
            "id": "a:test-conversation-id"
        },
        "recipient": {
            "id": "28:c185c174-26f6-4876-b847-0a423d07d1f3",
            "name": "DTCE AI Assistant"
        },
        "text": "Hello bot!"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            endpoint,
            json=teams_activity,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {fake_jwt}",
                "User-Agent": "Microsoft-BotFramework/3.1"
            }
        )
        
        print(f"\n📊 Response: {response.status_code}")
        print(f"📄 Message: {response.text}")
        
        # Analyze the error to understand what validation failed
        if response.status_code == 500:
            error_text = response.text.lower()
            if "signature" in error_text:
                print("✅ Signature validation is working (expected failure)")
            elif "issuer" in error_text:
                print("⚠️  Issuer validation failed")
            elif "audience" in error_text:
                print("⚠️  Audience validation failed")
            elif "expired" in error_text:
                print("⚠️  Token expiration check failed")
            else:
                print(f"⚠️  Unknown validation error: {error_text}")

async def main():
    """Run all authentication tests."""
    
    # Test 1: Bot Framework configuration
    auth_ok = await test_bot_framework_auth()
    
    if auth_ok:
        # Test 2: Endpoint with proper JWT structure
        await test_endpoint_with_better_auth()
    
    print("\n🏁 Authentication Testing Complete!")
    print("=" * 60)
    print("📝 Summary:")
    print("  ✅ If authentication is rejecting fake tokens, security is working")
    print("  ✅ Real Teams messages will have proper Microsoft-signed JWT tokens")
    print("  ⚠️  If you need to test manually, use Microsoft Bot Emulator")

if __name__ == "__main__":
    asyncio.run(main())
