import logging
import datetime
from typing import Dict, Any

from .google_auth import get_calendar_service

logger = logging.getLogger("agents.calendar_operator")

def execute_calendar_event(intent_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates or shifts a mock milestone event in the primary Google Calendar.
    Input params should contain:
    - title: str
    - delay_days: int (how many days to shift)
    - description: str (optional)
    """
    try:
        service = get_calendar_service()
        
        # In a real system, you would query for the specific event ID.
        # For the demo, we will create a NEW event representing the rescheduled milestone.
        delay_days = int(intent_params.get("delay_days", 0))
        title = intent_params.get("title", "Site Recovery Plan")
        description = intent_params.get("description", "Auto-scheduled via A.G.E.N.T.S.")
        
        # Reschedule from "tomorrow"
        # Since it's a delay, we add delay_days to tomorrow.
        start_date = datetime.datetime.utcnow().date() + datetime.timedelta(days=1 + delay_days)
        end_date = start_date + datetime.timedelta(days=1)  # All day event usually spans 1 day
        
        event = {
            'summary': f"[Rescheduled] {title}",
            'description': description,
            'start': {
                'date': start_date.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'date': end_date.isoformat(),
                'timeZone': 'UTC',
            },
            # Optional: Add attendees if needed
            # 'attendees': [
            #     {'email': intent_params.get("to", "stakeholder@example.com")},
            # ],
            'reminders': {
                'useDefault': True,
            },
        }

        logger.info(f"Creating real Calendar event for: {title} (Delay: {delay_days} days)")
        
        # Call the Calendar API
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        
        event_id = created_event.get("id")
        event_link = created_event.get('htmlLink')
        logger.info(f"Calendar event created: {event_link}")
        
        # 1. READ-BACK VERIFICATION
        verified_event = service.events().get(calendarId="primary", eventId=event_id).execute()
        semantic_match = verify_event_state(verified_event, event)
        
        return {
            "status": "SUCCESS" if semantic_match else "FAILED",
            "event_id": event_id,
            "verification": {
                "api_ack": True,
                "read_back": True,
                "semantic_match": semantic_match
            }
        }
        
    except Exception as e:
        logger.error(f"Calendar event creation failed: {e}")
        raise RuntimeError(f"Calendar Operator failed: {e}")

def read_event(event_id: str) -> Dict[str, Any]:
    """Exposed for verify_execution.py to re-read truth state."""
    service = get_calendar_service()
    try:
        return service.events().get(calendarId="primary", eventId=event_id).execute()
    except Exception:
        return None

def verify_event_state(actual_event: Dict[str, Any], expected_state: Dict[str, Any]) -> bool:
    if not actual_event: return False

    import datetime as dt_lib
    def parse_and_normalize_time(evt_node):
        if not evt_node: return None
        if "dateTime" in evt_node:
            dt_str = evt_node["dateTime"]
            dt = dt_lib.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.astimezone(dt_lib.timezone.utc).replace(second=0, microsecond=0)
        elif "date" in evt_node:
            return dt_lib.datetime.strptime(evt_node["date"], "%Y-%m-%d").replace(tzinfo=dt_lib.timezone.utc)
        return None

    actual_start = parse_and_normalize_time(actual_event.get("start", {}))
    actual_end = parse_and_normalize_time(actual_event.get("end", {}))
    
    expected_start = parse_and_normalize_time(expected_state.get("start", {}))
    expected_end = parse_and_normalize_time(expected_state.get("end", {}))
    
    def normalize_title(text):
        return " ".join(str(text).strip().lower().split())
        
    actual_title = normalize_title(actual_event.get("summary", ""))
    expected_title_norm = normalize_title(expected_state.get("summary", ""))

    return (
        actual_start == expected_start and
        actual_end == expected_end and
        actual_title == expected_title_norm
    )
