"""
Momentum Engine — Phase 2 Handshake.
Translates abstracted issue signals into project momentum vectors.
"""

import logging
from typing import Dict, Any, List
from .decision_cache import CacheContext
from ..contracts import validate_momentum_signal

logger = logging.getLogger("agents.momentum_engine")

# Initial Domain Mapping
_DOMAIN_MAP = {
    "rain": "ENVIRONMENTAL",
    "slab_pour": "LOGISTICS",
    "steel": "MATERIAL",
    "material": "MATERIAL",
    "supply": "MATERIAL",
    "rfi": "LOGISTICS",
    "mismatch": "MATERIAL",
    "power": "LOGISTICS",
    "power_outage": "LOGISTICS",
    "equipment": "MATERIAL",
    "site": "ENVIRONMENTAL",
    "crew": "LABOUR",
    "labour": "LABOUR",
    "subbie": "LABOUR",
    "contractor": "LABOUR",
}

def analyze_momentum(context: CacheContext) -> Dict[str, Any]:
    """
    Map an abstracted CacheContext to a structured Momentum Signal.
    This is the first implementation of the Eli Handshake.
    """
    issue = context.normalized_issue
    tokens = set(issue.split())
    
    # 1. Determine Domain
    domain = "LOGISTICS" # Default
    for token, mapped_domain in _DOMAIN_MAP.items():
        if token in tokens:
            domain = mapped_domain
            break
            
    # 2. Heuristic Velocity Impact (Placeholder for Eli's deep logic)
    # Negative impact scaled by buckets
    velocity_impact = -0.1 # Base drag
    
    if context.delay_bucket == "7-14d":
        velocity_impact = -0.4
    elif context.delay_bucket == "14d+":
        velocity_impact = -0.7
        
    if context.cost_bucket == "25-50k":
        velocity_impact -= 0.1
    elif context.cost_bucket == "50k+":
        velocity_impact -= 0.2
        
    # 3. Trend Direction
    trend = "DRAG"
    if velocity_impact < -0.5:
        trend = "STALL"
    elif velocity_impact > -0.05:
        trend = "STABLE"
        
    # 4. Urgency
    urgency = "MEDIUM"
    if "critical" in tokens or context.governance_flag_set:
        urgency = "HIGH"
    if trend == "STALL":
        urgency = "CRITICAL"

    # 5. Confidence Heuristic
    # Higher if we matched a specific token from our domain map
    confidence = 0.6 # Base confidence
    if any(token in tokens for token in _DOMAIN_MAP):
        confidence = 0.85
    if trend == "STALL" and not context.governance_flag_set:
        confidence -= 0.1 # Less certain about stalls if no gov flags raised

    signal = {
        "abstracted_issue": issue,
        "velocity_impact": round(velocity_impact, 2),
        "confidence": round(confidence, 2),
        "trend_direction": trend,
        "urgency": urgency,
        "domain": domain,
        "justification": f"Heuristic mapping for {domain} issue with {context.delay_bucket} delay."
    }
    
    # Validate against contract
    validation = validate_momentum_signal(signal)
    if not validation.ok:
        logger.error(f"Momentum Signal validation failed: {validation.reason}")
        # We still return but log error
        
    return signal
