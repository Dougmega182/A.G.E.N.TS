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

# Phase 2-Ext: Domain Weights
_DOMAIN_WEIGHTS = {
    "MATERIAL": 1.0,
    "LABOUR": 0.8,
    "LOGISTICS": 0.6,
    "ENVIRONMENTAL": 0.4,
    "FINANCIAL": 0.9
}

def _calculate_impact_score(domain: str, delay_bucket: str, velocity_impact: float) -> float:
    """Quantitative impact calculation (0.0 to 1.0)."""
    weight = _DOMAIN_WEIGHTS.get(domain, 0.5)
    
    # Delay multiplier
    delay_map = {"0-1d": 0.1, "1-3d": 0.3, "3-7d": 0.6, "7-14d": 0.8, "14d+": 1.0}
    delay_mult = delay_map.get(delay_bucket, 0.2)
    
    # Drag component (velocity impact is negative for drag)
    drag_score = min(1.0, abs(velocity_impact) * 2.0)
    
    # Composite: 40% Domain, 40% Delay, 20% Momentum
    score = (weight * 0.4) + (delay_mult * 0.4) + (drag_score * 0.2)
    return round(min(1.0, score), 2)

def _map_severity(score: float) -> str:
    """Categorical severity based on impact score."""
    if score >= 0.85: return "CRITICAL"
    if score >= 0.60: return "HIGH"
    if score >= 0.30: return "MEDIUM"
    return "LOW"

def analyze_momentum(context: CacheContext) -> Dict[str, Any]:
    """
    Map an abstracted CacheContext to a structured Momentum Signal.
    Now includes Phase 2-Ext Impact Scoring.
    """
    issue = context.normalized_issue
    tokens = set(issue.split())
    
    # 1. Determine Domain
    domain = "LOGISTICS" # Default
    for token, mapped_domain in _DOMAIN_MAP.items():
        if token in tokens:
            domain = mapped_domain
            break
            
    # 2. Heuristic Velocity Impact
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
        
    # 4. Phase 2-Ext: Impact Scoring & Severity
    impact_score = _calculate_impact_score(domain, context.delay_bucket, velocity_impact)
    severity = _map_severity(impact_score)

    # 5. Urgency
    urgency = "MEDIUM"
    if "critical" in tokens or context.governance_flag_set:
        urgency = "HIGH"
    if trend == "STALL" or severity == "CRITICAL":
        urgency = "CRITICAL"

    # 6. Confidence Heuristic
    confidence = 0.6 # Base confidence
    if any(token in tokens for token in _DOMAIN_MAP):
        confidence = 0.85
    if trend == "STALL" and not context.governance_flag_set:
        confidence -= 0.1 

    signal = {
        "abstracted_issue": issue,
        "velocity_impact": round(velocity_impact, 2),
        "confidence": round(confidence, 2),
        "impact_score": impact_score,
        "severity": severity,
        "trend_direction": trend,
        "urgency": urgency,
        "domain": domain,
        "justification": f"Heuristic mapping: {domain} ({severity}) with {context.delay_bucket} delay. Impact Score: {impact_score}."
    }
    
    # Validate against contract
    validation = validate_momentum_signal(signal)
    if not validation.ok:
        logger.error(f"Momentum Signal validation failed: {validation.reason}")
        
    return signal
