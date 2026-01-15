#!/usr/bin/env python3
"""
Gmail OAuth Setup Script

Run this once to authenticate with Gmail API.
Opens a browser window for Google sign-in.

Prerequisites:
1. Download OAuth client credentials from Google Cloud Console
2. Save as config/client_secrets.json

Usage:
    python scripts/setup_gmail_oauth.py
    
After successful auth, token is saved to config/.credentials/gmail_token.json
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.drivers.gmail_driver import GmailDriver


def main():
    print("=" * 60)
    print("GMAIL OAUTH SETUP")
    print("=" * 60)
    
    # Check for client secrets
    client_secrets_path = 'config/client_secrets.json'
    if not os.path.exists(client_secrets_path):
        print(f"""
❌ Client secrets file not found: {client_secrets_path}

To get this file:
1. Go to Google Cloud Console: https://console.cloud.google.com
2. Select your project (or create one)
3. Enable Gmail API: APIs & Services > Library > Gmail API
4. Create credentials: APIs & Services > Credentials
5. Click "Create Credentials" > "OAuth client ID"
6. Application type: "Desktop app"
7. Download the JSON file
8. Save it as: {client_secrets_path}

Then run this script again.
""")
        return 1
    
    print(f"✓ Found client secrets: {client_secrets_path}")
    print()
    
    # Create driver and authenticate
    driver = GmailDriver(
        credentials_dir='config/.credentials',
        token_file='gmail_token.json',
        client_secrets_file=client_secrets_path
    )
    
    try:
        driver.authenticate()
        print()
        print("=" * 60)
        print("✓ AUTHENTICATION SUCCESSFUL")
        print("=" * 60)
        
        # Test by listing labels
        print("\nTesting API access...")
        labels = driver.list_labels()
        print(f"✓ Found {len(labels)} labels in mailbox")
        
        # Look for mrayeh label
        mrayeh_label = None
        for label in labels:
            if label['name'].lower() == 'mrayeh':
                mrayeh_label = label
                break
        
        if mrayeh_label:
            print(f"✓ Found 'mrayeh' label (ID: {mrayeh_label['id']})")
        else:
            print("⚠ Label 'mrayeh' not found - you may need to create it")
            print("\nAvailable labels:")
            for label in sorted(labels, key=lambda x: x['name']):
                if not label['name'].startswith('CATEGORY_'):
                    print(f"  - {label['name']}")
        
        print()
        print("Setup complete! Token saved to: config/.credentials/gmail_token.json")
        print("You can now use the Gmail driver in your code.")
        return 0
        
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
