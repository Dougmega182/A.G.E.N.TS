import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

LOG_ROOT = Path("Agent logs")
EVENTS_LOG_PATH = LOG_ROOT / "events.log.jsonl"
STANDARD_EVENT_TYPES = {
    "LOOP_STARTED",
    "RISK_SCORE_CALCULATED",
    "REASONING_CONTEXT_ASSEMBLED",
    "PLAN_GENERATED",
    "IMPLEMENTATION_PLAN_GENERATED",
    "CRITIQUE_GENERATED",
    "VOTE_CAST",
    "DECISION_MADE",
    "DECISION_FINALIZED_V1",
    "ACTION_INTENT",
    "STATE_MUTATED",
    "ACTION_EXECUTED",
    "CONTRACT_VALIDATION_FAILED",
    "RETRY_TRIGGERED",
    "LOOP_COMPLETE",
    "APPROVAL_REQUESTED",
    "APPROVAL_DECIDED",
    "ACTION_BLOCKED",
    "ACTION_APPROVED",
    "EXTERNAL_ACTION_INTENT",
    "EXTERNAL_ACTION_EXECUTED",
    "OWEN_INSIGHT_EXTRACTED",
    "OWEN_INSIGHT_VALIDATED",
    # Phase 5.1.5 — Inference Caching (Decision Cache telemetry)
    "CACHE_HIT",
    "CACHE_MISS",
    "CACHE_BYPASS",
}

def emit_event(
    event_type: str, 
    trace_id: str, 
    agent_id: str = "SYSTEM", 
    scenario: str = "N/A", 
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Append-only, strictly ordered event emitter.
    Provides structured traceability across the autonomous decision loop.
    """
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "type": event_type,
        "agent_id": agent_id,
        "scenario": scenario,
        "metadata": metadata or {}
    }
    if event_type not in STANDARD_EVENT_TYPES:
        event["metadata"] = {
            **event.get("metadata", {}),
            "event_type_warning": "non_standard_event_type"
        }
    
    # Ensure directory exists
    EVENTS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Append-only write
    with open(EVENTS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    
    # Optional debug print for observability during dev
    # print(f"[EVENT] {event_type} | Trace: {trace_id[:8]} | Agent: {agent_id}")

def generate_trace_id() -> str:
    """Generates a unique Trace ID for a new execution thread."""
    return str(uuid.uuid4())
