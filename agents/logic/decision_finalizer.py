"""
Decision Finalizer — The Canonical Decision Layer

This is the ONLY component that produces the final, authoritative decision
for any execution loop. Everything upstream is advisory or intent.

Architecture:
    Aria (intent) → Finalizer (truth gate) → DECISION_FINALIZED_V1 (canonical event)

The finalizer:
    1. Receives Aria's raw decision + all system signals
    2. Applies deterministic overrides (governance, safety)
    3. Detects conflicts (WALL-E vs Aria)
    4. Validates reasoning quality
    5. Enforces Saturation Control (Rate limits, Cooldowns)
    6. Enforces Risk-Tiered Autonomy Gates
    7. Produces ONE canonical result

Rule: Only the orchestrator calls this. Nothing else changes decisions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .governance_engine import GovernanceFlag, has_critical_flag


@dataclass
class FinalizedDecision:
    """The single source of truth for a decision loop's outcome."""

    # What actually happened
    final_decision: str                           # APPROVE | REJECT | ESCALATE
    final_justification: str                      # The canonical reason

    # What Aria originally said
    original_decision: str
    original_justification: str

    # Override chain — ordered list of overrides applied (empty if none)
    override_chain: List[str] = field(default_factory=list)
    primary_override_reason: Optional[str] = None

    # Confidence Gate (The Authority Check)
    gate_action: str = "REQUIRE_APPROVAL"         # AUTO_ACT | REQUIRE_APPROVAL | SUPPRESS
    gate_thresholds: Dict[str, float] = field(default_factory=lambda: {"AUTO": 0.9, "APPROVAL": 0.7})

    # Saturation Control
    saturation_status: str = "PASS"               # PASS | COOLDOWN_ACTIVE | RATE_LIMIT_EXCEEDED | BURST_DETECTED
    saturation_metadata: Dict[str, Any] = field(default_factory=dict)
    entity_id: Optional[str] = None

    # Risk-Tiered Autonomy
    risk_level: str = "CONTROLLED"                # SAFE | CONTROLLED | CRITICAL

    # Signals that fed into the decision
    risk_score: float = 0.0
    governance_flags: List[Dict[str, Any]] = field(default_factory=list)
    governance_flag_count: int = 0
    has_critical_governance: bool = False
    conflict_detected: bool = False               # Signal or Agent conflict
    conflict_detail: str = ""
    conflict_status: Optional[str] = None        # CONFLICT_RESOLVED | CONFLICT_ESCALATED
    winning_signal_id: Optional[str] = None
    dominance_reason: Optional[str] = None

    # Reasoning quality
    reasoning_quality_warnings: List[str] = field(default_factory=list)

    # Metadata
    was_overridden: bool = False
    was_system_forced: bool = False                # Contract validation failure
    outcome_score: int = 0                         # 1 for success, -1 for failure/reject, 0 for neutral
    trace_id: str = ""
    scenario_type: str = ""
    confidence_score: float = 0.0
    confidence_reason: str = ""
    
    # Adaptive metrics
    confidence_adjusted: float = 0.0
    confidence_penalty: float = 0.0
    confidence_threshold: float = 0.6
    drift_pressure_index: float = 0.0
    why: str = ""
    distrust_level: str = "LOW"
    momentum_signal: Dict[str, Any] = field(default_factory=dict)
    competing_signals: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> FinalizedDecision:
        """Reconstruct a FinalizedDecision from a dict payload."""
        return cls(
            final_decision=payload.get("final_decision", "UNKNOWN"),
            final_justification=payload.get("final_justification", ""),
            original_decision=payload.get("original_decision", "UNKNOWN"),
            original_justification=payload.get("original_justification", ""),
            override_chain=payload.get("override_chain", []),
            primary_override_reason=payload.get("primary_override_reason"),
            gate_action=payload.get("gate_action", "REQUIRE_APPROVAL"),
            gate_thresholds=payload.get("gate_thresholds", {"AUTO": 0.9, "APPROVAL": 0.7}),
            saturation_status=payload.get("saturation_status", "PASS"),
            saturation_metadata=payload.get("saturation_metadata", {}),
            entity_id=payload.get("entity_id"),
            risk_level=payload.get("risk_level", "CONTROLLED"),
            risk_score=payload.get("risk_score", 0.0),
            governance_flags=payload.get("governance_flags", []),
            governance_flag_count=payload.get("governance_flag_count", 0),
            has_critical_governance=payload.get("has_critical_governance", False),
            conflict_detected=payload.get("conflict_detected", False),
            conflict_detail=payload.get("conflict_detail", ""),
            conflict_status=payload.get("conflict_status"),
            winning_signal_id=payload.get("winning_signal_id"),
            dominance_reason=payload.get("dominance_reason"),
            reasoning_quality_warnings=payload.get("reasoning_quality_warnings", []),
            was_overridden=payload.get("was_overridden", False),
            was_system_forced=payload.get("was_system_forced", False),
            outcome_score=payload.get("outcome_score", 0),
            confidence_score=payload.get("confidence_score", 0.0),
            confidence_reason=payload.get("confidence_reason", ""),
            confidence_adjusted=payload.get("confidence_adjusted", 0.0),
            confidence_penalty=payload.get("confidence_penalty", 0.0),
            confidence_threshold=payload.get("confidence_threshold", 0.6),
            drift_pressure_index=payload.get("drift_pressure_index", 0.0),
            why=payload.get("why", ""),
            distrust_level=payload.get("distrust_level", "LOW"),
            momentum_signal=payload.get("momentum_signal", {}),
            competing_signals=payload.get("competing_signals", [])
        )

    def to_event_payload(self) -> Dict[str, Any]:
        """Produce the canonical DECISION_FINALIZED_V1 event metadata."""
        return {
            "final_decision": self.final_decision,
            "final_justification": self.final_justification,
            "original_decision": self.original_decision,
            "original_justification": self.original_justification,
            "override_chain": self.override_chain,
            "primary_override_reason": self.primary_override_reason,
            "gate_action": self.gate_action,
            "gate_thresholds": self.gate_thresholds,
            "saturation_status": self.saturation_status,
            "saturation_metadata": self.saturation_metadata,
            "entity_id": self.entity_id,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "governance_flags": self.governance_flags,
            "governance_flag_count": self.governance_flag_count,
            "has_critical_governance": self.has_critical_governance,
            "conflict_detected": self.conflict_detected,
            "conflict_detail": self.conflict_detail,
            "conflict_status": self.conflict_status,
            "winning_signal_id": self.winning_signal_id,
            "dominance_reason": self.dominance_reason,
            "reasoning_quality_warnings": self.reasoning_quality_warnings,
            "was_overridden": self.was_overridden,
            "was_system_forced": self.was_system_forced,
            "outcome_score": self.outcome_score,
            "confidence_score": self.confidence_score,
            "confidence_reason": self.confidence_reason,
            "confidence_adjusted": self.confidence_adjusted,
            "confidence_penalty": self.confidence_penalty,
            "confidence_threshold": self.confidence_threshold,
            "drift_pressure_index": self.drift_pressure_index,
            "why": self.why,
            "distrust_level": self.distrust_level,
            "momentum_signal": self.momentum_signal,
            "competing_signals": self.competing_signals
        }

    def to_json(self) -> str:
        return json.dumps(self.to_event_payload(), ensure_ascii=False)


def compute_current_distrust_level(scenario_type: str) -> tuple[float, float, str]:
    """
    Computes penalty, DPI and label for the current state.
    Factored out for orchestrator to use in cache decisions.
    """
    from .owen_engine import OwenEngine
    # Using 'gmail_draft' as the primary risk surface
    penalty = OwenEngine().get_penalty_for_action("gmail_draft")
    penalty = min(penalty, 0.3)
    
    BASE_THRESHOLD = 0.6
    if penalty > 0.25:
        threshold = 0.8
    elif penalty > 0.15:
        threshold = 0.7
    else:
        threshold = BASE_THRESHOLD
        
    dpi = penalty / threshold if threshold > 0 else 0
    
    label = "LOW"
    if dpi > 0.4: label = "BLOCKED"
    elif dpi > 0.3: label = "HIGH"
    elif dpi > 0.15: label = "ELEVATED"
    
    return penalty, dpi, label


def finalize_decision(
    *,
    decision_data: Dict[str, Any],
    decision_valid: bool,
    decision_error_reason: Optional[str],
    risk_score: float,
    governance_flags: List[GovernanceFlag],
    critique_data: Optional[Dict[str, Any]],
    memory_count: int,
    trace_id: str,
    scenario_type: str,
    momentum_signal: Dict[str, Any],
    competing_signals: Optional[List[Dict[str, Any]]] = None,
    outcome_score: Optional[int] = None,
    user_input: str = ""
) -> FinalizedDecision:
    """
    The single decision canonicalization function.

    Input: all raw signals from the loop.
    Output: one FinalizedDecision — the only thing downstream should trust.
    """

    override_chain: List[str] = []
    warnings: List[str] = []
    conflict_detected = False
    conflict_detail = ""
    conflict_status = None
    winning_signal_id = None
    dominance_reason = None

    # 0. CONFLICT RESOLUTION: Signal Dominance (Priority-Weighted)
    actual_signal = momentum_signal
    all_signals = [momentum_signal] + (competing_signals or [])
    if len(all_signals) > 1:
        conflict_detected = True
        # Scoring: (impact_score * 0.7) + (confidence * 0.3)
        # We prioritize impact (real world cost) but weight it by our confidence
        def score_signal(s):
            impact = s.get("impact_score", 0.5)
            conf = s.get("confidence", 0.5)
            # Urgency CRITICAL adds a flat 0.2 bonus
            bonus = 0.2 if s.get("urgency") == "CRITICAL" else 0.0
            return (impact * 0.7) + (conf * 0.3) + bonus

        # Determine winner
        scored_signals = [(score_signal(s), s) for s in all_signals]
        scored_signals.sort(key=lambda x: x[0], reverse=True)
        
        winner_score, winning_signal = scored_signals[0]
        loser_score, losing_signal = scored_signals[1]
        
        actual_signal = winning_signal
        winning_signal_id = winning_signal.get("signal_id", "PRIMARY")
        conflict_status = "CONFLICT_RESOLVED"
        
        dominance_reason = (
            f"Signal Dominance: Winner score {winner_score:.2f} vs Loser {loser_score:.2f}. "
            f"Winner Urgency: {winning_signal.get('urgency')}, Impact: {winning_signal.get('impact_score')}. "
            f"Loser Urgency: {losing_signal.get('urgency')}, Impact: {losing_signal.get('impact_score')}."
        )
        conflict_detail = f"Signal Conflict Resolved: {dominance_reason}"

    # Capture Aria's original intent before any override
    original_decision = str(decision_data.get("decision", "UNKNOWN")).upper()
    original_justification = str(decision_data.get("justification", ""))
    final_decision = original_decision
    final_justification = original_justification
    was_system_forced = False
    primary_reason: Optional[str] = None
    
    confidence_score = float(decision_data.get("confidence_score", 0.0))
    confidence_reason = str(decision_data.get("confidence_reason", "No confidence reason provided."))

    # --- OVERRIDE 1: Contract validation failure (highest priority) ---
    is_repaired = decision_error_reason == "repaired"
    
    if not decision_valid or not decision_data or is_repaired:
        failure_reason = decision_error_reason or "decision_payload_unparseable"
        
        if is_repaired:
            # If repaired, we have valid data but we MUST block AUTO_ACT
            override_chain.append("CONTRACT_DISCIPLINE_REPAIR")
            primary_reason = "contract_repair_required"
            was_system_forced = True
            warnings.append("AUTOMATED_DISCIPLINE_REPAIR_PERFORMED")
        else:
            final_decision = "ESCALATE"
            final_justification = (
                f"Technical Logic Failure: decision_v1 validation failed ({failure_reason}). "
                f"System-forced escalation to protect project integrity."
            )
            override_chain.append("CONTRACT_VALIDATION_FAILURE")
            primary_reason = "contract_failure"
            was_system_forced = True
            # Replace decision_data with safe defaults
            decision_data = {
                "decision": "ESCALATE",
                "justification": final_justification,
                "conditions": ["Manual human review required", "Re-run decision turn with valid contract payload"],
                "impact": {"cost": 0, "days": 0, "risk_delta": 0},
            }

    # --- OVERRIDE 2: CRITICAL governance flags (only if not already forced) ---
    if not was_system_forced and has_critical_flag(governance_flags) and final_decision == "APPROVE":
        critical_types = [f.flag_type for f in governance_flags if f.severity == "CRITICAL"]
        final_decision = "ESCALATE"
        final_justification = (
            f"GOVERNANCE OVERRIDE: Aria attempted to APPROVE but CRITICAL governance flag(s) "
            f"[{', '.join(critical_types)}] are active. "
            f"Original justification: {original_justification}"
        )
        override_chain.append("GOVERNANCE_CRITICAL_OVERRIDE")
        primary_reason = primary_reason or "governance_critical"

    # --- OVERRIDE 3: Safety gate (risk >= 0.85 + APPROVE) ---
    if not was_system_forced and risk_score >= 0.85 and final_decision == "APPROVE":
        final_decision = "ESCALATE"
        final_justification = (
            f"SAFETY GATE OVERRIDE: Aria attempted to APPROVE with risk_score {risk_score} (>= 0.85). "
            f"Original justification: {original_justification}"
        )
        override_chain.append("SAFETY_GATE_OVERRIDE")
        primary_reason = primary_reason or "safety_gate"

    # --- OWEN CONFIDENCE ADJUSTMENT ---
    penalty, dpi, distrust_label = compute_current_distrust_level(scenario_type)
    adjusted_conf = max(0.0, confidence_score - penalty)
    
    threshold = 0.8 if penalty > 0.25 else 0.7 if penalty > 0.15 else 0.6

    # --- OVERRIDE 4: Confidence Gate (Dynamic Threshold) ---
    if not was_system_forced and adjusted_conf < threshold and final_decision == "APPROVE":
        final_decision = "ESCALATE"
        reason_str = f"CONFIDENCE GATE OVERRIDE: Aria attempted to APPROVE with low confidence ({adjusted_conf:.2f} after {penalty:.2f} penalty). Threshold is {threshold:.2f}. DPI: {dpi:.2f}."
        final_justification = (
            f"{reason_str} "
            f"Confidence Reason: {confidence_reason}. "
            f"Original justification: {original_justification}"
        )
        override_chain.append("CONFIDENCE_GATE_OVERRIDE")
        primary_reason = primary_reason or "low_confidence_with_failure_history"

    # --- CONFLICT DETECTION: WALL-E vs Aria ---
    if not was_system_forced and critique_data:
        try:
            sentinel_rec = str(critique_data.get("recommendation", "")).upper()
            if sentinel_rec == "REJECT" and original_decision == "APPROVE":
                conflict_detected = True
                conflict_detail = "WALL-E recommended REJECT but Aria APPROVED"
        except Exception:
            pass

    # --- REASONING QUALITY VALIDATION ---
    if not was_system_forced:
        justification_lower = final_justification.lower()

        # Check governance flag references
        if governance_flags:
            flag_types_lower = [f.flag_type.lower() for f in governance_flags]
            has_gov_ref = (
                any(ft in justification_lower for ft in flag_types_lower)
                or "governance" in justification_lower
                or "flag" in justification_lower
            )
            if not has_gov_ref:
                warnings.append("MISSING_GOVERNANCE_REFERENCE")

        # Check institutional memory references
        if memory_count > 0:
            has_mem_ref = any(
                kw in justification_lower
                for kw in ("memory", "previous", "prior", "past", "history", "historical")
            )
            if not has_mem_ref:
                warnings.append("MISSING_MEMORY_REFERENCE")

    # --- BUILD PRELIMINARY CANONICAL RESULT ---
    was_overridden = len(override_chain) > 0
    why = f"{final_decision}: {primary_reason}" if was_overridden else f"{final_decision}: Direct Approval"
    if conflict_status:
        why += f" | {conflict_status}"

    # --- DETERMINE RISK LEVEL (Discipline Layer) ---
    input_lower = user_input.lower()
    forced_critical = any(k in input_lower for k in ["financial", "security", "critical", "structural", "dangerous"])
    
    if forced_critical or risk_score >= 0.7 or has_critical_flag(governance_flags):
        risk_level = "CRITICAL"
    elif risk_score < 0.4:
        risk_level = "SAFE"
    else:
        risk_level = "CONTROLLED"

    # --- FINAL STEP: RISK-TIERED CONFIDENCE GATE (Pre-Act Enforcement) ---
    gate_action = "REQUIRE_APPROVAL"
    gate_thresholds = {"SAFE": 0.70, "CONTROLLED": 0.85, "CRITICAL": 1.0} # 1.0 ensures Critical never auto-execs
    auto_act_threshold = gate_thresholds.get(risk_level, 0.85)

    if adjusted_conf >= auto_act_threshold and risk_level != "CRITICAL":
        gate_action = "AUTO_ACT"
    elif adjusted_conf < 0.6: # Stricter than the escalation threshold to force suppression
        gate_action = "SUPPRESS"
    
    # Force REQUIRE_APPROVAL for any overridden or escalated decision regardless of confidence
    if was_overridden or final_decision == "ESCALATE":
        gate_action = "REQUIRE_APPROVAL"

    # --- SATURATION CONTROL (Control Layer) ---
    from .saturation_control import SaturationControl
    sat_status, sat_meta = SaturationControl.check_saturation(
        scenario_type=scenario_type,
        user_input=user_input,
        intent_type=scenario_type, # Using scenario as intent for now
        trace_id=trace_id
    )
    
    entity_id = sat_meta.get("entity_id")
    
    if sat_status in {"COOLDOWN_ACTIVE", "RATE_LIMIT_EXCEEDED"}:
        gate_action = "SUPPRESS"
        final_justification = (
            f"SATURATION OVERRIDE: {sat_status}. {sat_meta.get('reason')} "
            f"Original decision: {final_decision}. {final_justification}"
        )
    elif sat_status == "BURST_DETECTED":
        gate_action = "REQUIRE_APPROVAL" # Force review on bursts
        final_justification = (
            f"SATURATION OVERRIDE: BURST_DETECTED. {sat_meta.get('reason')} "
            f"Forcing approval despite confidence."
        )

    return FinalizedDecision(
        final_decision=final_decision,
        final_justification=final_justification,
        original_decision=original_decision,
        original_justification=original_justification,
        override_chain=override_chain,
        primary_override_reason=primary_reason,
        gate_action=gate_action,
        saturation_status=sat_status,
        saturation_metadata=sat_meta,
        entity_id=entity_id,
        risk_level=risk_level,
        risk_score=risk_score,
        governance_flags=[f.to_dict() for f in governance_flags],
        governance_flag_count=len(governance_flags),
        has_critical_governance=has_critical_flag(governance_flags),
        conflict_detected=conflict_detected,
        conflict_detail=conflict_detail,
        conflict_status=conflict_status,
        winning_signal_id=winning_signal_id,
        dominance_reason=dominance_reason,
        reasoning_quality_warnings=warnings,
        was_overridden=was_overridden,
        was_system_forced=was_system_forced,
        outcome_score=outcome_score if outcome_score is not None else 1 if final_decision == "APPROVE" else 0,
        trace_id=trace_id,
        scenario_type=scenario_type,
        confidence_score=confidence_score,
        confidence_reason=confidence_reason,
        confidence_adjusted=adjusted_conf,
        confidence_penalty=penalty,
        confidence_threshold=auto_act_threshold,
        drift_pressure_index=dpi,
        why=why,
        distrust_level=distrust_label,
        momentum_signal=actual_signal,
        competing_signals=competing_signals or []
    )
