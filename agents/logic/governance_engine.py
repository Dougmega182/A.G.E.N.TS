"""
Governance Engine — Phase 2: Structured Heuristic Guardrails

Evaluates construction scenarios against governance thresholds and produces
severity-tagged flags. These flags are injected into agent reasoning contexts
and enforced at the orchestration layer.

Signal Priority:
    1. Safety Gate (absolute — handled in orchestrator via risk_score >= 0.85)
    2. Governance Flags (this module — strong influence)
    3. Risk Score (quantitative baseline — risk_engine.py)
    4. Institutional Memory (contextual — history_engine.py)
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any


# Severity levels — orchestrator enforces CRITICAL as mandatory ESCALATE
SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"
SEVERITY_CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class GovernanceFlag:
    flag_type: str
    message: str
    severity: str
    threshold: str  # What rule triggered this

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_governance(
    scenario_type: str,
    cost: float,
    days: int,
    risk_score: float,
) -> List[GovernanceFlag]:
    """
    Evaluate a scenario against governance thresholds.
    Returns a list of GovernanceFlag objects, ordered by severity (highest first).
    """
    flags: List[GovernanceFlag] = []
    scenario_type = scenario_type.lower()

    # --- Cost Thresholds ---
    if cost > 50000:
        flags.append(GovernanceFlag(
            flag_type="BUDGET_CRITICAL",
            message=f"Cost of ${cost:,.0f} exceeds critical budget threshold ($50,000)",
            severity=SEVERITY_CRITICAL,
            threshold="cost > $50,000"
        ))
    elif cost > 25000:
        flags.append(GovernanceFlag(
            flag_type="BUDGET_HIGH",
            message=f"Cost of ${cost:,.0f} exceeds high budget threshold ($25,000)",
            severity=SEVERITY_HIGH,
            threshold="cost > $25,000"
        ))
    elif cost > 10000:
        flags.append(GovernanceFlag(
            flag_type="HIGH_IMPACT",
            message=f"Cost of ${cost:,.0f} exceeds standard budget threshold ($10,000)",
            severity=SEVERITY_MEDIUM,
            threshold="cost > $10,000"
        ))

    # --- Schedule Thresholds ---
    if days > 14:
        flags.append(GovernanceFlag(
            flag_type="SCHEDULE_CRITICAL",
            message=f"Schedule extension of {days} days exceeds critical threshold (14 days)",
            severity=SEVERITY_CRITICAL,
            threshold="days > 14"
        ))
    elif days > 7:
        flags.append(GovernanceFlag(
            flag_type="SCHEDULE_PRESSURE",
            message=f"Schedule extension of {days} days exceeds pressure threshold (7 days)",
            severity=SEVERITY_HIGH,
            threshold="days > 7"
        ))
    elif days > 3:
        flags.append(GovernanceFlag(
            flag_type="SCHEDULE_WATCH",
            message=f"Schedule extension of {days} days exceeds watch threshold (3 days)",
            severity=SEVERITY_LOW,
            threshold="days > 3"
        ))

    # --- Risk Momentum ---
    if risk_score > 0.85:
        # This is also handled by the Safety Gate, but we flag it here for governance logging
        flags.append(GovernanceFlag(
            flag_type="SAFETY_GATE_ACTIVE",
            message=f"Risk score {risk_score:.2f} exceeds safety gate threshold (0.85). APPROVE is blocked.",
            severity=SEVERITY_CRITICAL,
            threshold="risk_score > 0.85"
        ))
    elif risk_score > 0.75:
        flags.append(GovernanceFlag(
            flag_type="MOMENTUM_RISK",
            message=f"Risk score {risk_score:.2f} indicates elevated project momentum risk (>0.75)",
            severity=SEVERITY_HIGH,
            threshold="risk_score > 0.75"
        ))
    elif risk_score > 0.5:
        flags.append(GovernanceFlag(
            flag_type="RISK_ELEVATED",
            message=f"Risk score {risk_score:.2f} is elevated (>0.50)",
            severity=SEVERITY_MEDIUM,
            threshold="risk_score > 0.50"
        ))

    # --- Scenario-Specific Rules ---
    if scenario_type == "delay" and days > 5:
        flags.append(GovernanceFlag(
            flag_type="DELAY_COMPOUND_RISK",
            message=f"Delay of {days} days may compound with existing schedule commitments",
            severity=SEVERITY_HIGH,
            threshold="delay scenario + days > 5"
        ))

    # Sort by severity (CRITICAL first)
    severity_order = {SEVERITY_CRITICAL: 0, SEVERITY_HIGH: 1, SEVERITY_MEDIUM: 2, SEVERITY_LOW: 3}
    flags.sort(key=lambda f: severity_order.get(f.severity, 99))

    return flags


def has_critical_flag(flags: List[GovernanceFlag]) -> bool:
    """Check if any flag has CRITICAL severity — triggers forced ESCALATE."""
    return any(f.severity == SEVERITY_CRITICAL for f in flags)


def format_flags_for_agents(flags: List[GovernanceFlag]) -> str:
    """Convert flags to a human-readable string for LLM context injection."""
    if not flags:
        return "No governance flags raised."

    lines = ["GOVERNANCE FLAGS:"]
    for f in flags:
        lines.append(f"  [{f.severity}] {f.flag_type}: {f.message}")
    return "\n".join(lines)
