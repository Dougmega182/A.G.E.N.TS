import json
from typing import List, Dict, Any, Optional
from .risk_engine import calculate_risk_trend
from .event_bus import EVENTS_LOG_PATH

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

def get_recent_decisions_from_events(n: int = 10, scenario: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches the last n 'DECISION_MADE' events, optionally filtered by scenario type.
    Replaces state-based decision history.
    """
    events = _read_all_events()
    decision_events = [e for e in events if e.get("type") == "DECISION_MADE"]
    
    if scenario:
        scenario_lower = scenario.lower()
        decision_events = [e for e in decision_events if e.get("scenario", "").lower() == scenario_lower]
    
    recent = decision_events[-n:]
    return [
        {
            "timestamp": e["timestamp"],
            "trace_id": e["trace_id"],
            "decision": e["metadata"].get("decision"),
            "risk_score": e["metadata"].get("risk_score", 0.0),
            "scenario": e.get("scenario", "variation"),
            "cost": e["metadata"].get("impact", {}).get("cost", 0),
            "days": e["metadata"].get("impact", {}).get("days", 0),
            "risk_delta": e["metadata"].get("impact", {}).get("risk_delta", 0.0),
            "justification": e["metadata"].get("justification", ""),
            "conflict": e["metadata"].get("conflict", "false"),
            "forced_by_system": e["metadata"].get("forced_by_system", "false"),
        }
        for e in recent
    ]


def get_structured_memory(scenario_type: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Returns structured memory objects derived from the event stream.
    Each object contains real data fields — no summaries, no hallucination risk.
    
    This is the ONLY source of institutional memory for the system.
    """
    decisions = get_recent_decisions_from_events(n=limit, scenario=scenario_type)
    
    memory = []
    for d in decisions:
        # Determine outcome based on decision + whether it was system-forced
        outcome = "stable"
        if d.get("forced_by_system") == "true":
            outcome = "system_forced_escalation"
        elif d.get("conflict") == "true":
            outcome = "conflict_detected"
        elif d.get("decision", "").upper() == "REJECT":
            outcome = "rejected"
        elif d.get("decision", "").upper() == "ESCALATE":
            outcome = "escalated"
        
        item = {
            "scenario": d.get("scenario", scenario_type),
            "cost": d.get("cost", 0),
            "days": d.get("days", 0),
            "risk_score": d.get("risk_score", 0.0),
            "decision": d.get("decision", "UNKNOWN"),
            "outcome": outcome,
            "governance_overridden": d.get("governance_overridden", "false"),
            "trace_id": d.get("trace_id", ""),
            "timestamp": d.get("timestamp", ""),
        }
        item["outcome_score"] = score_outcome(item)
        memory.append(item)
    
    return memory


def format_memory_for_agents(memory: List[Dict[str, Any]]) -> str:
    """
    Convert structured memory objects to a human-readable string for LLM context injection.
    Structured data goes in first → human text is derived, never the other way around.
    """
    if not memory:
        return "No institutional memory available for this scenario type."
    
    lines = ["INSTITUTIONAL MEMORY (past decisions for this scenario type):"]
    for m in memory:
        decision_str = m.get("decision", "UNKNOWN").upper()
        outcome_str = m.get("outcome", "unknown")
        lines.append(
            f"  - {m['scenario']} | ${m['cost']:,.0f} | {m['days']}d "
            f"| risk {m['risk_score']:.2f} → {decision_str} (outcome: {outcome_str}, score: {m.get('outcome_score', 0):+d})"
        )
    
    # Add net outcome summary
    net = sum(m.get("outcome_score", 0) for m in memory)
    if net > 0:
        quality = "historically positive"
    elif net < 0:
        quality = "historically poor"
    else:
        quality = "historically neutral"
    lines.append(f"  NET OUTCOME SCORE: {net:+d} ({quality})")
    
    return "\n".join(lines)


def score_outcome(decision_record: Dict[str, Any]) -> int:
    """
    Score a past decision's outcome for weighting.
    
    +1 = positive outcome (approved and stable, or correctly rejected)
    0  = neutral (escalated, unknown)
    -1 = negative outcome (system-forced, conflict detected, governance override)
    """
    outcome = decision_record.get("outcome", "unknown")
    decision = str(decision_record.get("decision", "")).upper()
    governance_overridden = decision_record.get("governance_overridden", "false")
    
    # Negative signals
    if outcome == "system_forced_escalation":
        return -1
    if outcome == "conflict_detected":
        return -1
    if governance_overridden == "true":
        return -1
    
    # Positive signals
    if decision == "APPROVE" and outcome == "stable":
        return 1
    if decision == "REJECT" and outcome == "rejected":
        return 1  # Correct rejection is a positive signal
    
    # Neutral
    return 0


def get_outcome_signal(scenario_type: str, limit: int = 5) -> Dict[str, Any]:
    """
    Returns the net outcome signal for a scenario type.
    Used by agents to understand if similar past decisions went well or poorly.
    """
    memory = get_structured_memory(scenario_type, limit=limit)
    
    if not memory:
        return {
            "net_score": 0,
            "quality": "no_history",
            "count": 0,
            "breakdown": {"positive": 0, "neutral": 0, "negative": 0}
        }
    
    scores = [m.get("outcome_score", 0) for m in memory]
    net = sum(scores)
    
    if net > 0:
        quality = "historically_positive"
    elif net < 0:
        quality = "historically_poor"
    else:
        quality = "historically_neutral"
    
    return {
        "net_score": net,
        "quality": quality,
        "count": len(memory),
        "breakdown": {
            "positive": scores.count(1),
            "neutral": scores.count(0),
            "negative": scores.count(-1),
        }
    }


def get_risk_trend_from_events() -> Dict[str, Any]:
    """Derives current project health/trend from the event stream."""
    decisions = get_recent_decisions_from_events(n=10) # 10 for smoothed trend
    return calculate_risk_trend(decisions)

def get_trace_lineage(trace_id: str) -> List[Dict[str, Any]]:
    """Reconstructs the full lineage of events for a specific execution thread."""
    events = _read_all_events()
    return [e for e in events if e.get("trace_id") == trace_id]

def get_avg_miss_latency(limit: int = 20) -> int:
    """
    Calculate average decision_phase_ms for non-cached decisions.
    Defaults to 33000 (33s) if no history exists (baseline).
    """
    events = _read_all_events()
    finalized_events = [e for e in events if e.get("type") == "DECISION_FINALIZED_V1"]
    
    # Filter for MISS/BYPASS cases only
    miss_latencies = [
        int(e["metadata"].get("decision_phase_ms", 0))
        for e in finalized_events
        if not e["metadata"].get("served_from_cache", False)
        and e["metadata"].get("decision_phase_ms") is not None
    ]
    
    if not miss_latencies:
        return 33000 # 33s baseline per Phase 5.1 dataset
        
    recent = miss_latencies[-limit:]
    return int(sum(recent) / len(recent))

