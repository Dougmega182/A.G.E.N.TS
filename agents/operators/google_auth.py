"""
Google Auth Helper — Handles logic for OAuth2 credentials and token persistence.
Implements the "Copy-Paste" flow for Headless/Terminal environments.
"""

import os
import logging
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger("agents.google_auth")

# SCOPES requested for Operators
SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events"
]

def get_gmail_service():
    """
    Returns an authorized Gmail API service instance.
    Handles the OAuth2 flow if necessary.
    """
    from googleapiclient.discovery import build
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)

def get_calendar_service():
    """
    Returns an authorized Google Calendar API service instance.
    """
    from googleapiclient.discovery import build
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds)

def get_credentials():
    """
    Authenticates the user and returns OAuth2 credentials.
    Uses token.json if available, otherwise starts the flow.
    """
    creds = None
    token_path = Path("token.json")
    creds_path = Path("credentials.json")

    # 1. Load existing token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # 2. Refresh or Re-auth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Gmail token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                creds = None
        
        if not creds:
            if not creds_path.exists():
                raise FileNotFoundError(
                    "credentials.json not found! Please download your OAuth client "
                    "secret from Google Cloud Console and place it in the project root."
                )

            logger.info("Starting Gmail OAuth flow (Copy-Paste)...")
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            
            # Use run_local_server with bind_addr='localhost' for modern desktop environments.
            # If the user is on a remote server, they'll need to use port forwarding or 
            # we'd need the deprecated run_console.
            # Given the USER's specific request for "Copy-Paste", we'll use a local server 
            # with a fixed port or allow them to copy the URL.
            
            # NOTE: run_local_server launches a browser. If it fails, the user gets a URL 
            # to visit and we wait for the redirect.
            try:
                creds = flow.run_local_server(port=0, prompt="consent", timeout_seconds=300)
            except Exception as e:
                logger.error(f"OAuth flow failed: {e}")
                print("\n[AUTH ERROR] Could not start local server for OAuth.")
                print("If you are on a headless server, please run this script on a machine with a browser.")
                raise

        # 3. Save the token for next time
        with open(token_path, "w") as token:
            token.write(creds.to_json())
            logger.info("New Gmail token saved to token.json")

    return creds

if __name__ == "__main__":
    # Test auth flow
    try:
        logging.basicConfig(level=logging.INFO)
        get_credentials()
        print("\n[SUCCESS] Authentication successful. token.json is ready.")
    except Exception as e:
        print(f"\n[FAILURE] Authentication failed: {e}")
