#!/usr/bin/env python3
"""
One-time Gmail OAuth setup. Run this once to authorise the email agent.

Requirements:
  1. Download credentials.json from Google Cloud Console (OAuth 2.0 Desktop app)
  2. Place credentials.json in the same directory as this script
  3. Run:  python3 setup_gmail_auth.py

A browser window will open for you to log in and grant permissions.
On success, token.json is saved and the script prints your Gmail address.
"""

import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token.json")


def main():
    os.chdir(SCRIPT_DIR)

    if not os.path.exists(CREDENTIALS_FILE):
        print("ERROR: credentials.json not found.")
        print()
        print("To fix this:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. Create a project and enable the Gmail API")
        print("  3. Create OAuth 2.0 credentials (Desktop app type)")
        print("  4. Download the JSON file and rename it to credentials.json")
        print(f"  5. Place credentials.json in: {SCRIPT_DIR}")
        sys.exit(1)

    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing existing token...")
            creds.refresh(Request())
        else:
            print("Opening browser for Gmail authorisation...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"Token saved to: {TOKEN_FILE}")

    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    email_address = profile["emailAddress"]

    print()
    print("Setup complete!")
    print(f"  Authenticated as: {email_address}")
    print(f"  Token file:       {TOKEN_FILE}")
    print()
    print("You can now run the agent:")
    print("  python3 email_agent.py")


if __name__ == "__main__":
    main()
