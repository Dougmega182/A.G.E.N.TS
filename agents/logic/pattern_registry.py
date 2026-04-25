from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


PATTERN_REGISTRY_PATH = Path("Agent logs") / "pattern_registry.log.jsonl"


def _count_prior_matches(signature: str) -> int:
    if not PATTERN_REGISTRY_PATH.exists():
        return 0
    count = 0
    with PATTERN_REGISTRY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("workflow_signature") == signature:
                count += 1
    return count


def _record_type_entry(record_type: str, trace_id: str, payload: Dict[str, Any]) -> None:
    entry = {
        "record_type": record_type,
        "timestamp": datetime.utcnow().isoformat(),
        "trace_id": trace_id,
        **payload,
    }
    PATTERN_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PATTERN_REGISTRY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def log_pattern(
    *,
    trace_id: str,
    scenario: str,
    user_input: str,
    workflow_signature: str,
    agent_sequence: List[str],
    action_types: List[str],
    final_decision: str,
    served_from_cache: bool,
    governance_flag_types: List[str],
    override_chain: List[str],
) -> None:
    """Append one structural workflow record to the pattern registry."""
    prior_seen_count = _count_prior_matches(workflow_signature)
    _record_type_entry("pattern_observed", trace_id, {
        "scenario": scenario,
        "workflow_signature": workflow_signature,
        "prior_seen_count": prior_seen_count,
        "is_repeat_pattern": prior_seen_count > 0,
        "workflow_shape": {
            "agent_sequence": agent_sequence,
            "action_types": action_types,
            "final_decision": final_decision,
            "served_from_cache": served_from_cache,
            "governance_flag_types": governance_flag_types,
            "override_chain": override_chain,
            "outcome_quality_signal": "pending",
        },
        "sample_input": user_input,
    })


def log_outcome_quality_update(
    *,
    trace_id: str,
    outcome_quality_signal: str,
    signal_source: str,
    source: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a downstream quality signal for an existing workflow trace."""
    _record_type_entry("outcome_quality_update", trace_id, {
        "outcome_quality_signal": outcome_quality_signal,
        "signal_source": signal_source,
        "source": source,
        "details": details or {},
    })


def derive_execution_quality_signal(result: Any) -> Optional[str]:
    """Map execution results into a coarse quality signal."""
    if not isinstance(result, dict):
        return None

    completion_status = str(result.get("completion_status", "")).upper()
    if completion_status == "EXECUTED":
        return "success"
    if completion_status == "PARTIALLY_EXECUTED":
        return "partial"
    if completion_status == "FAILED":
        return "failure"

    status = str(result.get("status", "")).lower()
    if status == "success":
        bundle = result.get("result")
        if isinstance(bundle, list):
            statuses = [str(item.get("status", "")).lower() for item in bundle if isinstance(item, dict)]
            if any(s == "failed" for s in statuses) and any(s in {"success", "skipped"} for s in statuses):
                return "partial"
            if any(s == "failed" for s in statuses):
                return "failure"
            return "success"
        return "success"

    if status == "failed":
        return "failure"
    return None
