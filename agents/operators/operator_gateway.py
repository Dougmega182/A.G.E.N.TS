"""
Operator Gateway — Dispatcher for specific external executors.
Phase 3A.
"""

from typing import Dict, Any
from .gmail_operator import execute_gmail_draft
from .calendar_operator import execute_calendar_event

def route_execution(action_intent: Dict[str, Any], execution_trace_id: str) -> Dict[str, Any]:
    """Route the approved intent to the correct operator."""
    action = action_intent.get("action", "")
    
    if action == "gmail_draft":
        return execute_gmail_draft(action_intent.get("parameters", {}), execution_trace_id)
    elif action == "calendar_event":
        return execute_calendar_event(action_intent.get("parameters", {}))
    else:
        raise ValueError(f"Unsupported action: {action}. Phase 4 supports 'gmail_draft' and 'calendar_event'.")
