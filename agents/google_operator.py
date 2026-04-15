import os
import json
import base64
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes for Jenny (AGT-009)
# Gmail: Read + Compose (drafts + send review copies to Gatekeeper).
# Calendar: Full read/write management.
GATEKEEPER_EMAIL = "dalepsaila@gmail.com"
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/calendar'
]

class GoogleOperator:
    """Base operator for Google API authentication and service management."""
    
    def __init__(self, agent_id: str = "jenny"):
        self.agent_id = agent_id
        self.agent_dir = Path(__file__).parent / agent_id
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        self.token_path = self.agent_dir / "token.json"
        self.creds_path = Path(__file__).parent.parent / "credentials.json"
        self.creds = None

    def authenticate(self):
        """Standard OAuth2 flow to handle token persistence and initial browser login."""
        print(f"[AUTH] Looking for token at: {self.token_path}")
        print(f"[AUTH] Looking for credentials at: {self.creds_path}")
        
        if self.token_path.exists():
            print("[AUTH] Found existing token.json — loading...")
            self.creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                print("[AUTH] Token expired — refreshing...")
                self.creds.refresh(Request())
            else:
                print("[AUTH] No valid token found — opening browser for authorization...")
                print("[AUTH] >>> A BROWSER WINDOW WILL OPEN. Please approve access. <<<")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.creds_path), SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            print(f"[AUTH] Saving token to: {self.token_path}")
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())
        else:
            print("[AUTH] Token is valid — no re-auth needed.")
        
        return self.creds

class GmailOperator(GoogleOperator):
    """Native Gmail operations for Jenny."""
    
    def __init__(self, agent_id: str = "jenny"):
        super().__init__(agent_id)
        self.service = None

    def get_service(self):
        if not self.service:
            creds = self.authenticate()
            self.service = build('gmail', 'v1', credentials=creds)
        return self.service

    def list_messages(self, max_results=5):
        """List metadata for the most recent emails."""
        try:
            service = self.get_service()
            results = service.users().messages().list(userId='me', maxResults=max_results).execute()
            messages = results.get('messages', [])
            
            summary = []
            for msg in messages:
                m = service.users().messages().get(userId='me', id=msg['id'], format='minimal').execute()
                snippet = m.get('snippet', '')
                summary.append({"id": msg['id'], "snippet": snippet})
            return summary
        except HttpError as error:
            return f"An error occurred: {error}"

    def create_draft(self, to: str, subject: str, message_text: str):
        """Create an email draft. This does NOT send the email."""
        try:
            service = self.get_service()
            
            message = EmailMessage()
            message.set_content(message_text)
            message['To'] = to
            message['From'] = 'me'
            message['Subject'] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            create_message = {
                'message': {
                    'raw': encoded_message
                }
            }
            
            draft = service.users().drafts().create(userId='me', body=create_message).execute()
            return f"Draft created successfully. Draft ID: {draft['id']}"
        except HttpError as error:
            return f"An error occurred: {error}"

    def send_draft_for_review(self, original_subject: str, draft_body: str):
        """
        Send a draft response to the Gatekeeper for review.
        Subject format: RESPONSE TO EMAIL (original_subject) DRAFT
        Recipient: dalepsaila@gmail.com (hardcoded for safety)
        """
        try:
            service = self.get_service()
            
            subject = f"RESPONSE TO EMAIL ({original_subject}) DRAFT"
            
            message = EmailMessage()
            message.set_content(draft_body)
            message['To'] = GATEKEEPER_EMAIL
            message['From'] = 'me'
            message['Subject'] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message = {'raw': encoded_message}
            
            sent = service.users().messages().send(userId='me', body=send_message).execute()
            print(f"[GMAIL] Draft review sent to {GATEKEEPER_EMAIL} | Message ID: {sent['id']}")
            return f"Draft review sent to Gatekeeper. Subject: {subject} | Message ID: {sent['id']}"
        except HttpError as error:
            return f"An error occurred: {error}"

class CalendarOperator(GoogleOperator):
    """Native Calendar operations for Jenny."""
    
    def __init__(self, agent_id: str = "jenny"):
        super().__init__(agent_id)
        self.service = None

    def get_service(self):
        if not self.service:
            creds = self.authenticate()
            self.service = build('calendar', 'v3', credentials=creds)
        return self.service

    def list_events(self, max_results=5):
        """List upcoming events."""
        try:
            service = self.get_service()
            now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            events_result = service.events().list(calendarId=GATEKEEPER_EMAIL, timeMin=now,
                                                maxResults=max_results, singleEvents=True,
                                                orderBy='startTime').execute()
            events = events_result.get('items', [])
            
            summary = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                summary.append({"start": start, "summary": event.get('summary', '(No Title)')})
            return summary
        except HttpError as error:
            return f"An error occurred: {error}"

    def create_event(self, summary: str, start_time: str, end_time: str, description: str = ""):
        """
        Create a calendar event. 
        start_time and end_time should be ISO strings e.g. '2026-04-15T14:00:00Z'
        """
        try:
            service = self.get_service()
            event = {
                'summary': summary,
                'description': description,
                'start': {'dateTime': start_time},
                'end': {'dateTime': end_time},
            }
            event = service.events().insert(calendarId='primary', body=event).execute()
            return f"Event created: {event.get('htmlLink')}"
        except HttpError as error:
            return f"An error occurred: {error}"

if __name__ == "__main__":
    import sys
    print("="*50)
    print(" A.G.E.N.T.S. — JENNY GOOGLE OPERATOR TEST")
    print("="*50)
    
    try:
        # Step 1: Send Draft for Gatekeeper Review
        print("\n--- STEP 1: SEND DRAFT FOR REVIEW ---")
        gmail = GmailOperator()
        result = gmail.send_draft_for_review(
            "Meeting with Client X - Thursday 2pm",
            "Hi,\n\nThank you for the meeting invitation. Unfortunately I will not be available at the proposed time. Could we reschedule to Friday morning?\n\nKind regards,\nDale"
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"[GMAIL ERROR] {type(e).__name__}: {e}")
    
    try:
        # Step 2: Calendar List
        print("\n--- STEP 2: CALENDAR EVENTS ---")
        calendar = CalendarOperator()
        events = calendar.list_events()
        if isinstance(events, str):
            print(f"Result: {events}")
        elif len(events) == 0:
            print("No upcoming events found.")
        else:
            print(f"Found {len(events)} upcoming events:")
            for ev in events:
                print(f"  - {ev['start']}: {ev['summary']}")
    except Exception as e:
        print(f"[CALENDAR ERROR] {type(e).__name__}: {e}")
    
    print("\n" + "="*50)
    print(" TEST COMPLETE")
    print("="*50)
