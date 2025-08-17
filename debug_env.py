#!/usr/bin/env python3
"""
Quick debug script to check environment variables
"""
import os

print("=== Environment Variables Debug ===")
print(f"MICROSOFT_APP_ID: {os.getenv('MICROSOFT_APP_ID', 'NOT_SET')}")
print(f"MICROSOFT_APP_PASSWORD: {os.getenv('MICROSOFT_APP_PASSWORD', 'NOT_SET')}")

# Also check if they're set with any other common variations
common_variations = [
    'MICROSOFT_BOT_APP_ID',
    'BOT_APP_ID', 
    'MICROSOFT_BOT_APP_PASSWORD',
    'BOT_APP_PASSWORD',
    'AZURE_BOT_APP_ID',
    'AZURE_BOT_APP_PASSWORD'
]

print("\n=== Checking common variations ===")
for var in common_variations:
    value = os.getenv(var)
    if value:
        print(f"{var}: {value}")

print("\n=== All environment variables containing 'MICROSOFT' or 'BOT' ===")
for key, value in os.environ.items():
    if 'MICROSOFT' in key.upper() or 'BOT' in key.upper():
        # Mask password for security
        display_value = value if 'PASSWORD' not in key.upper() else '***MASKED***'
        print(f"{key}: {display_value}")
