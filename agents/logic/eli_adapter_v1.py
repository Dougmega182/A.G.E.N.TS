"""
Eli Adapter — The Deterministic Logistics Engine.
Phase 2.1 Implementation: Converts Momentum Signals into structured Action Queues.
"""

import logging
from typing import Dict, Any, List
from ..contracts import validate_momentum_signal

logger = logging.getLogger("agents.eli_adapter")

# Deterministic Action Mapping
_LOGISTICS_STRATEGY = {
    "STALL": {
        "action_type": "STABILISE",
        "priority_boost": 0.0,
        "required_checks": ["resource_availability", "bottleneck_id"],
        "dispatch_target": "ops_manager"
    },
    "DRAG": {
        "action_type": "STABILISE",
        "priority_boost": 0.1,
        "required_checks": ["efficiency_audit"],
        "dispatch_target": "foreman"
    },
    "STABLE": {
        "action_type": "MONITOR",
        "priority_boost": 0.2,
        "required_checks": ["schedule_alignment"],
        "dispatch_target": "scheduler"
    },
    "ACCEL": {
        "action_type": "PRIORITISE",
        "priority_boost": 0.5,
        "required_checks": ["critical_path_impact"],
        "dispatch_target": "executive"
    }
}

# Dispatch Policy Layer
AUTO_SEND = False # Mandatory Approval Gate
CONFIDENCE_THRESHOLD = 0.7 # Minimum confidence required for auto-drafting

# Action to Email Content Map
_DISPATCH_TEMPLATES = {
    "STABILISE": {
        "subject": "Action Required: Project Stabilisation Required for {domain} Issue",
        "body": "This is a deterministic logistics alert. A {domain} issue has been classified as {trend}, creating a velocity impact of {impact}.\n\nLogistics Action: STABILISE\nTarget: {to}\nRequired Checks: {checks}\n\nPlease perform an efficiency audit and resource availability check immediately."
    },
    "MONITOR": {
        "subject": "Logistics Update: Monitoring {domain} Momentum",
        "body": "Project momentum for {domain} is currently STABLE. No immediate escalation required.\n\nLogistics Action: MONITOR\nTarget: {to}\nRequired Checks: {checks}\n\nContinue tracking schedule alignment."
    },
    "PRIORITISE": {
        "subject": "CRITICAL: Fast-Track Execution Required for {domain} Momentum Shift",
        "body": "A positive momentum shift ({trend}) has been detected in the {domain} domain. Velocity Impact: {impact}.\n\nLogistics Action: PRIORITISE\nTarget: {to}\nRequired Checks: {checks}\n\nPlease fast-track execution and assess critical path impact."
    }
}

# Phase 2.6: Conflict Resolution Patterns
_ENTITIES = ["steel", "labour", "crew", "concrete", "power", "tiles", "paint", "crane", "equipment"]
_DELAY_KEYWORDS = {"late", "delay", "postpone", "shortage", "behind", "miss", "fail"}
_RESOLVE_KEYWORDS = {"arriv", "resolv", "today", "now", "fixed", "done", "ready"}

def _extract_entity(tokens: set) -> str:
    """Identify the primary physical or labour entity involved."""
    for e in _ENTITIES:
        if e in tokens:
            return e
    return "general"

def _determine_polarity(tokens: set) -> str:
    """Determine if the intent is worsening (DELAY) or improving (RESOLVED)."""
    if any(k in tokens for k in _RESOLVE_KEYWORDS):
        return "RESOLVED"
    if any(k in tokens for k in _DELAY_KEYWORDS):
        return "DELAY"
    return "NEUTRAL"

def transform_signal_to_actions(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consumer-only transformation. 
    Strictly maps Momentum Signal (v1) to a structured Action Queue.
    Now includes Phase 2.6 Entity + Polarity for Conflict Resolution.
    """
    # 1. Input Validation (Verify Handshake)
    validation = validate_momentum_signal(signal)
    if not validation.ok:
        raise ValueError(f"Invalid Momentum Signal: {validation.reason}")
        
    issue_key = signal.get("abstracted_issue", "")
    tokens = set(issue_key.split())
    
    trend = signal.get("trend_direction", "STABLE")
    confidence = signal.get("confidence", 0)
    domain = signal.get("domain", "LOGISTICS")
    
    # 2. Extract Conflict Resolver Metadata (Phase 2.6.1)
    entity = _extract_entity(tokens)
    polarity = _determine_polarity(tokens)

    # 3. Select Strategy and Base Target
    strategy = _LOGISTICS_STRATEGY.get(trend, _LOGISTICS_STRATEGY["STABLE"])
    
    # 4. Apply Domain Override for Targeting (Phase 2.4)
    target_role = _DOMAIN_ROUTING.get(domain, strategy["dispatch_target"])
    recipient_email = _RECIPIENT_MAP.get(target_role)

    # 5. Build Action Object
    action_queue = {
        "signal_trace": issue_key,
        "strategy": strategy["action_type"],
        "entity": entity,
        "polarity": polarity,
        "execution_priority": round(0.5 + strategy["priority_boost"] + (signal.get("velocity_impact", 0) * -1), 2),
        "checks": strategy["required_checks"],
        "dispatch": {
            "to": target_role,
            "email": recipient_email,
            "urgency": signal.get("urgency"),
            "domain": domain
        },
        "meta": {
            "version": "eli_adapter_v1.2",
            "deterministic": True,
            "confidence": confidence,
            "auto_send_policy": AUTO_SEND
        }
    }

    # 6. Generate Draft Payload (Only if above threshold AND has recipient)
    status = "READY"
    if not recipient_email and target_role != "internal":
        status = "BLOCKED_MISSING_RECIPIENT"
    elif confidence < CONFIDENCE_THRESHOLD:
        status = "BLOCKED_LOW_CONFIDENCE"

    if status == "READY":
        template = _DISPATCH_TEMPLATES.get(strategy["action_type"])
        if template:
            action_queue["gmail_draft"] = {
                "to": recipient_email,
                "subject": template["subject"].format(domain=domain),
                "body": template["body"].format(
                    domain=domain,
                    trend=trend,
                    impact=signal.get("velocity_impact"),
                    to=target_role,
                    checks=", ".join(strategy["required_checks"])
                )
            }
    
    action_queue["status"] = status
    return action_queue
