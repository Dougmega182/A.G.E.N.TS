import json
from email.message import EmailMessage
from pathlib import Path # Added Path import
import base64 # Added base64 import
from typing import Dict, Any, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .firewall import PreflightApprovalEngine, PreflightApprovalError
from .logic import event_bus
from .contracts import ContractValidationResult # Import the new ContractValidationResult

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
        """Standard OAuth2 flow with robustness against corrupt/empty tokens."""
        print(f"[AUTH] Looking for token at: {self.token_path}")
        
        # 0-byte check: if token file exists but is empty, delete it to prevent JSON errors
        if self.token_path.exists() and self.token_path.stat().st_size == 0:
            print(f"[AUTH] Found 0-byte token file. Deleting to allow re-auth...")
            self.token_path.unlink()

        if self.token_path.exists():
            print("[AUTH] Found existing token.json — loading...")
            try:
                self.creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                print(f"[AUTH] Failed to load token.json ({e}). Deleting and re-authenticating...")
                self.token_path.unlink()
                self.creds = None
            
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                print("[AUTH] Token expired — refreshing...")
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"[AUTH] Refresh failed ({e}). Re-authenticating via browser...")
                    self.creds = None # Trigger full auth
            
            if not self.creds:
                print("[AUTH] No valid token found — opening browser for authorization...")
                print("[AUTH] >>> A BROWSER WINDOW WILL OPEN. Please approve access. <<<")
                if not self.creds_path.exists():
                    raise FileNotFoundError(f"Google credentials.json not found at {self.creds_path}. Cannot perform initial auth.")
                
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

    def _preflight_external_action(self, action: str, target: str, payload: dict, summary: str, trace_id: str = "N/A"):
        event_bus.emit_event("EXTERNAL_ACTION_INTENT", trace_id, agent_id=self.agent_id, scenario="preflight", metadata={
            "action": action,
            "target": target,
            "summary": summary
        })
        approval = PreflightApprovalEngine.ensure_approved(
            action=action,
            target=target,
            payload=payload,
            agent_id=self.agent_id,
            trace_id=trace_id,
            summary=summary,
            metadata={"operator": "gmail"}
        )
        return approval

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

    async def send_draft_for_review(self, original_subject: str, draft_body: str, trace_id: str = "N/A"):
        """
        Send a draft response to the Gatekeeper for review.
        Subject format: RESPONSE TO EMAIL (original_subject) DRAFT
        Recipient: dalepsaila@gmail.com (hardcoded for safety)
        """
        try:
            # 1. Create an action_intent_v1 object
            action_intent = {
                "action": "gmail_send_review",
                "agent_id": self.agent_id,
                "parameters": {
                    "to": GATEKEEPER_EMAIL,
                    "subject": f"RESPONSE TO EMAIL ({original_subject}) DRAFT",
                    "body": draft_body
                },
                "trace_id": trace_id,
                "requires_approval": True,
                "status": "pending" # Initial status for the intent
            }

            # Emit ACTION_INTENT_CREATED event
            event_bus.emit_event("ACTION_INTENT_CREATED", trace_id, agent_id=self.agent_id, scenario="preflight", metadata={
                "action": action_intent["action"],
                "intent_payload": action_intent["parameters"]
            })

            # 2. Call PreflightApprovalEngine.ensure_approved()
            approval_request = PreflightApprovalEngine.ensure_approved(
                action=action_intent["action"],
                parameters=action_intent["parameters"], # Pass the parameters directly
                agent_id=self.agent_id,
                trace_id=trace_id
            )

            # 3. Execution only if approved, using the exact frozen parameters
            if approval_request and approval_request.get("status") == "approved":
                return await self.execute_intent(approval_request.get("original_action_intent", {}))
            else:
                raise PreflightApprovalError("external_action_not_approved", {"request_id": approval_request.get("request_id") if approval_request else "N/A"})

        except PreflightApprovalError as approval_error:
            details = approval_error.details or {}
            request_id = details.get("request_id", "N/A")
            status = details.get("status", "pending")
            return f"Preflight blocked external action ({approval_error.reason}). Request ID: {request_id} | Status: {status}"
        except HttpError as error:
            return f"An error occurred: {error}"

    async def execute_intent(self, action_intent: Dict[str, Any]):
        """Execute an approved action intent."""
        action = action_intent["action"]
        parameters = action_intent["parameters"]
        trace_id = action_intent.get("trace_id", "N/A")

        if action == "gmail_send_review":
            to = parameters.get("to")
            subject = parameters.get("subject")
            body = parameters.get("body")

            service = self.get_service()

            message = EmailMessage()
            message.set_content(body)
            message['To'] = to
            message['From'] = 'me'
            message['Subject'] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message = {'raw': encoded_message}

            sent = service.users().messages().send(userId='me', body=send_message).execute()
            
            # Emit ACTION_EXECUTED
            event_bus.emit_event("ACTION_EXECUTED", trace_id, agent_id=self.agent_id, scenario="preflight", metadata={
                "action": action,
                "target": to,
                "message_id": sent.get('id', '')
            })
            print(f"[GMAIL] Draft review sent to {to} | Message ID: {sent['id']}")
            return f"Draft review sent to Gatekeeper. Subject: {subject} | Message ID: {sent['id']}"
        else:
            raise ValueError(f"Unsupported Gmail action: {action}")

class CalendarOperator(GoogleOperator):
    """Native Calendar operations for Jenny."""
    
    def __init__(self, agent_id: str = "jenny"):
        super().__init__(agent_id)
        self.service = None

    def _preflight_external_action(self, action: str, target: str, payload: dict, summary: str, trace_id: str = "N/A"):
        event_bus.emit_event("EXTERNAL_ACTION_INTENT", trace_id, agent_id=self.agent_id, scenario="preflight", metadata={
            "action": action,
            "target": target,
            "summary": summary
        })
        approval = PreflightApprovalEngine.ensure_approved(
            action=action,
            target=target,
            payload=payload,
            agent_id=self.agent_id,
            trace_id=trace_id,
            summary=summary,
            metadata={"operator": "calendar"}
        )
        return approval

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

    async def create_event(self, summary: str, start_time: str, end_time: str, description: str = "", trace_id: str = "N/A"):
        """
        Create a calendar event. 
        start_time and end_time should be ISO strings e.g. '2026-04-15T14:00:00Z'
        """
        try:
            # 1. Create an action_intent_v1 object
            action_intent = {
                "action": "calendar_create_event",
                "agent_id": self.agent_id,
                "parameters": {
                    "summary": summary,
                    "description": description,
                    "start_time": start_time,
                    "end_time": end_time
                },
                "trace_id": trace_id,
                "requires_approval": True,
                "status": "pending" # Initial status for the intent
            }

            # Emit ACTION_INTENT_CREATED event
            event_bus.emit_event("ACTION_INTENT_CREATED", trace_id, agent_id=self.agent_id, scenario="preflight", metadata={
                "action": action_intent["action"],
                "intent_payload": action_intent["parameters"]
            })

            # 2. Call PreflightApprovalEngine.ensure_approved()
            approval_request = PreflightApprovalEngine.ensure_approved(
                action=action_intent["action"],
                parameters=action_intent["parameters"], # Pass the parameters directly
                agent_id=self.agent_id,
                trace_id=trace_id
            )

            # 3. Execution only if approved, using the exact frozen parameters
            if approval_request and approval_request.get("status") == "approved":
                return await self.execute_intent(approval_request.get("original_action_intent", {}))
            else:
                raise PreflightApprovalError("external_action_not_approved", {"request_id": approval_request.get("request_id") if approval_request else "N/A"})

        except PreflightApprovalError as approval_error:
            details = approval_error.details or {}
            request_id = details.get("request_id", "N/A")
            status = details.get("status", "pending")
            return f"Preflight blocked external action ({approval_error.reason}). Request ID: {request_id} | Status: {status}"
        except HttpError as error:
            return f"An error occurred: {error}"

    async def execute_intent(self, action_intent: Dict[str, Any]):
        """Execute an approved action intent."""
        action = action_intent["action"]
        parameters = action_intent["parameters"]
        trace_id = action_intent.get("trace_id", "N/A")

        if action == "calendar_create_event":
            event_summary = parameters.get("summary")
            event_description = parameters.get("description")
            event_start_time = parameters.get("start_time")
            event_end_time = parameters.get("end_time")

            service = self.get_service()
            event = {
                'summary': event_summary,
                'description': event_description,
                'start': {'dateTime': event_start_time},
                'end': {'dateTime': event_end_time},
            }
            event = service.events().insert(calendarId='primary', body=event).execute()
            
            # Emit ACTION_EXECUTED
            event_bus.emit_event("ACTION_EXECUTED", trace_id, agent_id=self.agent_id, scenario="preflight", metadata={
                "action": action,
                "target": "primary",
                "event_link": event.get('htmlLink', '')
            })
            return f"Event created: {event.get('htmlLink')}"
        else:
            raise ValueError(f"Unsupported Calendar action: {action}")

if __name__ == "__main__":
    import sys
    import asyncio
    
    async def main():
        print("="*50)
        print(" A.G.E.N.T.S. — JENNY GOOGLE OPERATOR TEST")
        print("="*50)
        
        try:
            # Step 1: Send Draft for Gatekeeper Review
            print("\n--- STEP 1: SEND DRAFT FOR REVIEW ---")
            gmail = GmailOperator()
            result = await gmail.send_draft_for_review(
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

    asyncio.run(main())
