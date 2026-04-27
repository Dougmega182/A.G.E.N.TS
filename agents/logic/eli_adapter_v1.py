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

# Phase 2.4: Stakeholder Mapping
_RECIPIENT_MAP = {
    "ops_manager": "ops@agents.ai",
    "foreman": "site.foreman@agents.ai",
    "scheduler": "planning@agents.ai",
    "pm": "project.manager@agents.ai",
    "executive": "dalepsaila@gmail.com", # Final Authority
    "internal": None # No external dispatch
}

# Domain to Recipient Override
_DOMAIN_ROUTING = {
    "ENVIRONMENTAL": "internal",
    "LOGISTICS": "scheduler",
    "MATERIAL": "foreman",
    "LABOUR": "foreman",
    "FINANCIAL": "ops_manager"
}

# Phase 3: Recipient Tiers
_RECIPIENT_TIERS = {
    "Primary": ["foreman", "scheduler", "ops_manager"],
    "Secondary": ["pm", "executive"],
    "Internal": ["internal"]
}

# Phase 2.6: Conflict Resolution Patterns
_ENTITIES = {
    "MATERIAL_FLOW": "SITE_MATERIALS",
    "LABOUR_FLOW": "SITE_LABOUR",
    "WEATHER_BLOCK": "SITE_WEATHER",
    "RFI_CLASH": "SITE_TECHNICAL",
    "steel": "MATERIAL_STEEL",
    "labour": "LABOUR_CREW",
    "crew": "LABOUR_CREW",
    "concrete": "MATERIAL_CONCRETE",
    "power": "SITE_UTILITIES",
    "tiles": "MATERIAL_FINISHES",
    "paint": "MATERIAL_FINISHES",
    "crane": "SITE_EQUIPMENT",
    "equipment": "SITE_EQUIPMENT"
}

_DELAY_KEYWORDS = {"late", "delay", "postpone", "shortage", "behind", "miss", "fail", "stall", "bankrupt"}
_RESOLVE_KEYWORDS = {"arriv", "resolv", "fixed", "done", "ready"}

def _extract_entity(tokens: set) -> str:
    """Identify the primary physical or labour entity involved."""
    for token in tokens:
        for key, mapped_entity in _ENTITIES.items():
            if token.startswith(key):
                return mapped_entity
    return "GENERAL_SITE"

def _determine_polarity(tokens: set) -> str:
    """Determine if the intent is worsening (DELAY) or improving (RESOLVED)."""
    if any(k in tokens for k in _RESOLVE_KEYWORDS):
        return "RESOLVED"
    if any(k in tokens for k in _DELAY_KEYWORDS):
        return "DELAY"
    return "NEUTRAL"

# Phase 2.8: Multi-Draft Templates
_PRIMARY_TEMPLATES = {
    "STABILISE": {
        "subject": "ACTION: Stabilise {domain} - Impact {impact}",
        "body": "Deterministic Logistics Alert: {domain} classified as {trend}.\n\nREQUIRED ACTION: STABILISE\nRole: {to}\nChecks: {checks}\n\nPerform efficiency audit and resource check immediately."
    },
    "MONITOR": {
        "subject": "UPDATE: Monitoring {domain} - Status Stable",
        "body": "Logistics Update: {domain} momentum is STABLE.\n\nACTION: MONITOR\nRole: {to}\nChecks: {checks}\n\nTrack schedule alignment. No escalation needed."
    },
    "PRIORITISE": {
        "subject": "URGENT ACTION: Fast-Track {domain} - Impact {impact}",
        "body": "Momentum Shift detected: {trend} in {domain}.\n\nREQUIRED ACTION: PRIORITISE\nRole: {to}\nChecks: {checks}\n\nFast-track execution and assess critical path immediately."
    }
}

_SECONDARY_TEMPLATES = {
    "STABILISE": {
        "subject": "FYI: Stabilisation Initiated for {domain} ({trend})",
        "body": "Awareness Notification: A {domain} issue has triggered a STABILISE intent for the site team.\n\nVelocity Impact: {impact}\nPrimary Target: {primary_role}\n\nNo direct action required from you. Monitor for further escalation."
    },
    "MONITOR": {
        "subject": "FYI: {domain} Momentum remains STABLE",
        "body": "Status Update: {domain} logistics currently within normal parameters.\n\nPrimary Target: {primary_role}\n\nContinue routine oversight."
    },
    "PRIORITISE": {
        "subject": "FYI: Priority Fast-Track for {domain} Momentum Shift",
        "body": "Strategic Awareness: A positive {trend} shift in {domain} has triggered a PRIORITISE intent.\n\nVelocity Impact: {impact}\nPrimary Target: {primary_role}\n\nAssessing critical path for early delivery gains."
    }
}

def transform_signal_to_actions(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consumer-only transformation. 
    Strictly maps Momentum Signal (v1) to a structured Action Queue.
    Now includes Phase 2.8 Multi-Draft Generation (Primary vs Secondary).
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
    severity = signal.get("severity", "LOW")
    impact = signal.get("velocity_impact", 0)
    
    # 2. Extract Conflict Resolver Metadata
    entity = _extract_entity(tokens)
    polarity = _determine_polarity(tokens)

    # 3. Select Strategy and Base Target
    strategy = _LOGISTICS_STRATEGY.get(trend, _LOGISTICS_STRATEGY["STABLE"])
    action_type = strategy["action_type"]
    
    # 4. Apply Domain Override for Targeting
    primary_role = _DOMAIN_ROUTING.get(domain, strategy["dispatch_target"])
    
    # 5. Build Dispatch Plan
    recipients = []
    rationale = [f"Domain classification: {domain}", f"Target mapping: {primary_role}"]
    
    # Add Primary
    recipients.append({
        "role": primary_role,
        "email": _RECIPIENT_MAP.get(primary_role),
        "tier": "Primary"
    })
    
    # Add Secondary Stakeholder for CRITICAL issues
    if severity == "CRITICAL" and primary_role != "internal":
        secondary_role = "pm"
        recipients.append({
            "role": secondary_role,
            "email": _RECIPIENT_MAP.get(secondary_role),
            "tier": "Secondary"
        })
        rationale.append(f"Severity CRITICAL -> Added {secondary_role} for awareness")

    # 6. Blast Radius Check
    requires_operator_approval = True 
    dispatch_status = "READY"
    
    external_recipients = [r for r in recipients if r["role"] != "internal" and r["email"]]
    if severity == "CRITICAL" and len(external_recipients) > 1:
        dispatch_status = "HIGH-RISK"
        rationale.append("BLAST RADIUS ALERT: Multi-recipient critical dispatch.")

    # 7. Build Action Object
    action_queue = {
        "trace_id": signal.get("trace_id", "N/A"),
        "signal_trace": issue_key,
        "strategy": action_type,
        "entity": entity,
        "polarity": polarity,
        "execution_priority": round(0.5 + strategy["priority_boost"] + (impact * -1), 2),
        "checks": strategy["required_checks"],
        "dispatch_plan": {
            "severity": severity,
            "recipients": recipients,
            "rationale": rationale,
            "requires_approval": requires_operator_approval
        },
        "dispatch": { # Legacy compatibility
            "to": primary_role,
            "email": _RECIPIENT_MAP.get(primary_role),
            "urgency": signal.get("urgency"),
            "domain": domain
        },
        "meta": {
            "version": "eli_adapter_v2.2",
            "deterministic": True,
            "confidence": confidence,
            "auto_send_policy": AUTO_SEND
        },
        "drafts": {} # Phase 2.8 Multi-Draft container
    }

    # 8. Check for blockages
    if primary_role != "internal" and not _RECIPIENT_MAP.get(primary_role):
        dispatch_status = "BLOCKED_MISSING_RECIPIENT"
            
    if confidence < CONFIDENCE_THRESHOLD:
        dispatch_status = "BLOCKED_LOW_CONFIDENCE"

    # 9. Generate Distinct Drafts (Phase 2.8)
    if dispatch_status in ["READY", "HIGH-RISK"]:
        # Primary Draft
        p_template = _PRIMARY_TEMPLATES.get(action_type)
        p_recip = next((r for r in recipients if r["tier"] == "Primary"), None)
        if p_template and p_recip and p_recip["email"]:
            action_queue["drafts"]["primary"] = {
                "to": p_recip["email"],
                "role": p_recip["role"],
                "subject": p_template["subject"].format(domain=domain, impact=impact),
                "body": p_template["body"].format(
                    domain=domain, trend=trend, impact=impact, 
                    to=p_recip["role"], checks=", ".join(strategy["required_checks"])
                )
            }
            # Maintain top-level gmail_draft for legacy system compatibility
            action_queue["gmail_draft"] = action_queue["drafts"]["primary"]

        # Secondary Draft (Awareness Only)
        s_template = _SECONDARY_TEMPLATES.get(action_type)
        s_recip = next((r for r in recipients if r["tier"] == "Secondary"), None)
        if s_template and s_recip and s_recip["email"]:
            action_queue["drafts"]["secondary"] = {
                "to": s_recip["email"],
                "role": s_recip["role"],
                "subject": s_template["subject"].format(domain=domain, trend=trend),
                "body": s_template["body"].format(
                    domain=domain, trend=trend, impact=impact, 
                    primary_role=primary_role
                )
            }
    
    action_queue["status"] = dispatch_status
    return action_queue
