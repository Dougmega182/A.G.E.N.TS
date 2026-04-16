import json
from pathlib import Path
from typing import List, Dict, Any
from .risk_engine import calculate_risk_trend

EVENTS_LOG_PATH = Path("data/events.log.jsonl")

def _read_all_events() -> List[Dict[str, Any]]:
    """Reads all events from the log file, handling potential file locking or mid-write reads."""
    if not EVENTS_LOG_PATH.exists():
        return []
    
    events = []
    with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue # Skip malformed lines
    return events

def get_recent_decisions_from_events(n: int = 10) -> List[Dict[str, Any]]:
    """
    Fetches the last n 'DECISION_MADE' events.
    Replaces state-based decision history.
    """
    events = _read_all_events()
    decision_events = [e for e in events if e.get("type") == "DECISION_MADE"]
    
    recent = decision_events[-n:]
    return [
        {
            "timestamp": e["timestamp"],
            "trace_id": e["trace_id"],
            "decision": e["metadata"].get("decision"),
            "risk_score": e["metadata"].get("risk_score", 0.0),
            "type": e.get("scenario", "variation"),
            "cost": e["metadata"].get("impact", {}).get("cost", 0),
            "justification": e["metadata"].get("justification", "")
        }
        for e in recent
    ]

def get_risk_trend_from_events() -> Dict[str, Any]:
    """Derives current project health/trend from the event stream."""
    decisions = get_recent_decisions_from_events(n=10) # 10 for smoothed trend
    return calculate_risk_trend(decisions)

def get_trace_lineage(trace_id: str) -> List[Dict[str, Any]]:
    """Reconstructs the full lineage of events for a specific execution thread."""
    events = _read_all_events()
    return [e for e in events if e.get("trace_id") == trace_id]
