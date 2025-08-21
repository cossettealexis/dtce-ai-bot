#!/usr/bin/env python3
"""
Direct test of Teams bot endpoint to check if there are authentication issues.
"""
import requests
import json

# Test the endpoint directly
url = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net/api/messages"

# Simple test payload (like Teams would send)
payload = {
    "type": "message",
    "id": "test-123",
    "timestamp": "2025-08-22T00:00:00Z",
    "text": "hello",
    "from": {
        "id": "test-user",
        "name": "Test User"
    },
    "conversation": {
        "id": "test-conv"
    },
    "recipient": {
        "id": "c185c174-26f6-4876-b847-0a423d07d1f3",
        "name": "DTCE AI Assistant"
    },
    "channelData": {},
    "channelId": "msteams"
}

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer fake-token-for-testing"
}

print("Testing Teams bot endpoint...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
