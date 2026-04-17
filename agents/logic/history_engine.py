"""
History Engine — Phase 2: Institutional Memory Proxy

Thin proxy between orchestrator and event_analytics.
All memory is DERIVED from the event stream — never stored separately.

Architecture:
    events.log.jsonl → event_analytics.py → history_engine.py → orchestrator.py
"""

from typing import List, Dict, Any
from . import event_analytics


def get_relevant_memory(scenario_type: str, limit: int = 5) -> Dict[str, Any]:
    """
    Fetch structured institutional memory for a given scenario type.
    
    Returns a dict with both the raw structured data (for programmatic use)
    and the human-readable format (for LLM injection).
    """
    structured = event_analytics.get_structured_memory(scenario_type, limit=limit)
    formatted = event_analytics.format_memory_for_agents(structured)
    
    return {
        "structured": structured,
        "formatted": formatted,
        "count": len(structured),
        "scenario_type": scenario_type,
    }


def check_memory_conflicts(scenario_type: str, proposed_decision: str) -> Dict[str, Any]:
    """
    Check if the proposed decision contradicts recent history.
    
    Example: If similar past scenarios were REJECTED but we're now proposing APPROVE,
    this flags a conflict that Aria must explicitly justify.
    """
    memory = event_analytics.get_structured_memory(scenario_type, limit=5)
    
    if not memory:
        return {"has_conflict": False, "details": "No prior history to compare against."}
    
    proposed_upper = proposed_decision.strip().upper()
    
    # Find contradictions: past decisions that differ from the proposed one
    contradictions = []
    for m in memory:
        past_decision = m.get("decision", "").upper()
        if past_decision and past_decision != proposed_upper:
            contradictions.append({
                "past_decision": past_decision,
                "past_cost": m.get("cost", 0),
                "past_risk": m.get("risk_score", 0.0),
                "past_outcome": m.get("outcome", "unknown"),
                "trace_id": m.get("trace_id", ""),
            })
    
    if contradictions:
        return {
            "has_conflict": True,
            "details": f"Proposed {proposed_upper} conflicts with {len(contradictions)} prior decision(s) in this scenario type.",
            "contradictions": contradictions,
        }
    
    return {"has_conflict": False, "details": "Proposed decision aligns with historical pattern."}
