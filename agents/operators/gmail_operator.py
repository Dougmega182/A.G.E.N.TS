"""
Gmail Operator — Pure function executor for Gmail drafting.
Phase 3A Hardened: Operator-level input validation before any side-effect.
No sending, no reasoning, no editing.
"""

import logging
from typing import Dict, Any
from ..logic import event_bus

logger = logging.getLogger("agents.gmail_operator")

# Allowed fields — reject anything unexpected
REQUIRED_FIELDS = {"to", "subject", "body"}
ALLOWED_FIELDS = {"to", "subject", "body", "cc", "bcc"}
class OperatorValidationError(Exception):
    """Raised when operator-level input validation fails."""
    def __init__(self, reason: str, details: Dict[str, Any] = None):
        self.reason = reason
        self.details = details or {}
        super().__init__(reason)


def _validate_parameters(parameters: Dict[str, Any]):
    """
    Lightweight re-validation at the operator boundary.
    Treats input as untrusted even though gateway already checked it.
    """
    if not isinstance(parameters, dict):
        raise OperatorValidationError("invalid_parameters_type", {"type": str(type(parameters))})

    # Check required fields
    missing = REQUIRED_FIELDS - set(parameters.keys())
    if missing:
        raise OperatorValidationError("missing_required_fields", {"missing": list(missing)})

    # Check no unexpected fields
    unexpected = set(parameters.keys()) - ALLOWED_FIELDS
    if unexpected:
        raise OperatorValidationError("unexpected_fields", {"fields": list(unexpected)})

    # Validate field types and content
    for field in REQUIRED_FIELDS:
        value = parameters[field]
        if not isinstance(value, str):
            raise OperatorValidationError("invalid_field_type", {"field": field, "type": str(type(value))})
        if not value.strip():
            raise OperatorValidationError("empty_field", {"field": field})
        # Basic encoding safety — reject null bytes
        if "\x00" in value:
            raise OperatorValidationError("encoding_violation", {"field": field})

from .google_auth import get_gmail_service, get_calendar_service
import base64
from email.message import EmailMessage

def execute_gmail_draft(parameters: Dict[str, Any], execution_trace_id: str) -> Dict[str, Any]:
    """
    Creates a real Gmail draft and verifies its existence.
    """
    # 1. OPERATOR-LEVEL VALIDATION (Chaos protection)
    _validate_parameters(parameters)

    recipient = parameters["to"]
    subject = parameters["subject"]
    body = parameters["body"]

    try:
        # 2. Authenticate
        service = get_gmail_service()

        # 3. Create MIME message
        message = EmailMessage()
        message.set_content(body)
        message["To"] = recipient
        message["Subject"] = subject
        
        # cc/bcc support
        if "cc" in parameters: message["Cc"] = parameters["cc"]
        if "bcc" in parameters: message["Bcc"] = parameters["bcc"]

        # Gmail API expects base64url encoded string
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"message": {"raw": encoded_message}}

        # 4. EXECUTE SIDE-EFFECT
        logger.info(f"Creating real Gmail draft for {recipient}...")
        draft = service.users().drafts().create(userId="me", body=create_message).execute()
        draft_id = draft["id"]

        verified_draft = service.users().drafts().get(userId="me", id=draft_id, format="full").execute()
        semantic_match = verify_draft_state(verified_draft, parameters)

        # Emit audit event
        event_bus.emit_event("EXTERNAL_SIDE_EFFECT_V1", execution_trace_id, agent_id="gmail_operator", metadata={
            "type": "GMAIL_DRAFT",
            "draft_id": draft_id,
            "thread_id": verified_draft.get("message", {}).get("threadId"),
            "recipient": recipient,
            "subject": subject,
            "verification": {
                "api_ack": True,
                "read_back": True,
                "semantic_match": semantic_match
            }
        })

        return {
            "status": "SUCCESS" if semantic_match else "FAILED",
            "draft_id": draft_id,
            "thread_id": verified_draft.get("message", {}).get("threadId"),
            "verification": {
                "api_ack": True,
                "read_back": True,
                "semantic_match": semantic_match
            }
        }

    except Exception as e:
        logger.error(f"Gmail draft creation failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

def read_draft(draft_id: str) -> Dict[str, Any]:
    """Exposed for verify_execution.py to re-read truth state."""
    service = get_gmail_service()
    try:
        return service.users().drafts().get(userId="me", id=draft_id, format="full").execute()
    except Exception:
        return None

def verify_draft_state(draft_obj: Dict[str, Any], expected_state: Dict[str, Any]) -> bool:
    if not draft_obj: return False
    
    headers = draft_obj.get("message", {}).get("payload", {}).get("headers", [])
    
    draft_to = ""
    draft_subject = ""
    for h in headers:
        name = h.get("name", "").lower()
        if name == "to": draft_to = h.get("value", "")
        elif name == "subject": draft_subject = h.get("value", "")
            
    def normalize(text):
        return " ".join(str(text).strip().lower().split())
        
    subject = expected_state.get("subject", "")
    recipient = expected_state.get("to", "")
    
    return (
        normalize(subject) == normalize(draft_subject) and
        normalize(recipient) in normalize(draft_to)
    )
