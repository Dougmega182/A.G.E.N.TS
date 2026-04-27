"""
Owen Intelligence Engine — The System's Intelligence Synthesizer.

This engine implements Owen's new role as the "Memory Intelligence Layer".
It is RESPONSIBLE for:
    1. Extracting patterns and lessons from the decision log
    2. Maintaining "Strategic Dos and Don'ts"
    3. Detecting Drift Pressure (performance degradation over time)
    4. Providing pre-briefings to agents based on history
"""

from __future__ import annotations

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from .event_bus import emit_event
from .memory_db import (
    write_owen_insight, 
    read_owen_insights, 
    validate_owen_insight,
    read_decisions
)
from .memory_contract import MemoryDomain, assert_read_permission, assert_write_permission

logger = logging.getLogger("agents.owen_engine")

COMPONENT_NAME = "owen_engine"

class OwenEngine:
    """
    Owen (AGT-014) — Memory & Consequence Engine.
    Operates strictly in the 'Learn' step of the A.G.E.N.T.S control loop.
    """

    def generate_intelligence_briefing(self, scenario_type: str, query_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Synthesize history into an advisory briefing for the current scenario.
        Used by the 'Decide' step to inform agents of past outcomes.
        """
        assert_read_permission(COMPONENT_NAME, MemoryDomain.OWEN_INSIGHTS)
        
        # 1. Fetch historical decisions
        decisions = read_decisions(COMPONENT_NAME, scenario=scenario_type, limit=50)
        
        # 2. Fetch curated insights
        insights = read_owen_insights(COMPONENT_NAME, scenario_type=scenario_type, limit=20)
        
        # 3. Aggregate metrics
        success_count = sum(1 for d in decisions if d.get("outcome_score", 0) > 0)
        total_count = len(decisions)
        
        # 4. Extract "Lessons Learned" from metadata of historical decisions
        lessons = []
        for d in decisions:
            # Decisions table has a 'justification' field we can parse
            if d.get("was_overridden"):
                lessons.append(f"PREVIOUS OVERRIDE: {d.get('primary_override_reason')} (Impact: {d.get('cost')})")
        
        # 5. Build structured briefing
        briefing = {
            "scenario": scenario_type,
            "metrics": {
                "sample_size": total_count,
                "net_outcome_score": success_count,
            },
            "lessons_learned": lessons[:5],
            "patterns": {
                "dos": [i["summary"] for i in insights if i["insight_type"] == "do"],
                "donts": [i["summary"] for i in insights if i["insight_type"] == "dont_do"]
            }
        }
        
        return briefing

    def extract_lesson_from_decision(self, event_id: str, trace_id: str, scenario: str, metadata: Dict[str, Any]) -> Optional[int]:
        """
        Closed-loop learning: Convert a finalized decision into a strategic insight.
        """
        assert_write_permission(COMPONENT_NAME, MemoryDomain.OWEN_INSIGHTS)
        
        # We only care about overriden decisions for "don'ts"
        if metadata.get("was_overridden"):
            reason = metadata.get("primary_override_reason", "unknown_override")
            summary = f"AVOID: {reason} in {scenario}. Aria attempted {metadata.get('original_decision')} but system forced ESCALATE."
            
            # Check for duplicates before writing
            existing = read_owen_insights(COMPONENT_NAME, scenario_type=scenario, limit=100)
            if not any(i["summary"] == summary for i in existing):
                insight_id = write_owen_insight(
                    COMPONENT_NAME,
                    insight_type="dont_do",
                    summary=summary,
                    scenario_type=scenario,
                    evidence=[event_id],
                    confidence=0.8,
                    deterministic_key=self._generate_deterministic_key(summary, scenario)
                )
                
                emit_event(
                    "OWEN_INSIGHT_EXTRACTED", 
                    trace_id, 
                    agent_id=COMPONENT_NAME, 
                    scenario=scenario, 
                    metadata={
                        "insight_id": insight_id,
                        "insight_type": "dont_do",
                        "summary": summary,
                        "evidence": [event_id],
                        "confidence": 0.8,
                        "deterministic_key": self._generate_deterministic_key(summary, scenario)
                    }
                )
            else:
                validate_owen_insight(COMPONENT_NAME, existing[0]["id"])
                emit_event(
                    "OWEN_INSIGHT_VALIDATED", 
                    trace_id, 
                    agent_id=COMPONENT_NAME, 
                    scenario=scenario, 
                    metadata={
                        "insight_id": existing[0]["id"],
                        "summary": summary
                    }
                )

        return None

    def register_pending_evaluation(self, trace_id: str, action_type: str):
        """Mark a trace as awaiting evaluation to prevent premature learning."""
        emit_event(
            "EVALUATION_PENDING", 
            trace_id, 
            agent_id=COMPONENT_NAME,
            metadata={"action_type": action_type, "evaluation_integrity": "PENDING"}
        )

    def extract_lesson_from_feedback(self, trace_id: str, outcome: str, notes: str) -> Optional[int]:
        """
        Ingest real-world execution feedback to close the loop on intelligence.
        DISTINGUISHES: SUCCESS, FAILURE, OVERRIDDEN, CONFLICT_RESOLVED, and MISSING.
        Tracks Shadow Accuracy & Pressure Metrics for 48h Audit.
        """
        assert_write_permission(COMPONENT_NAME, MemoryDomain.OWEN_INSIGHTS)
        
        outcome_norm = str(outcome).strip().upper()
        
        # 1. Handle Broken Feedback Loop (DEFERRED LEARNING)
        if outcome_norm in {"MISSING", "TIMEOUT", "EVALUATION_TIMEOUT", "EVALUATION_MISSING"}:
            emit_event(
                "LEARNING_DEFERRED", 
                trace_id, 
                agent_id=COMPONENT_NAME,
                metadata={
                    "reason": f"Feedback {outcome_norm}", 
                    "evaluation_integrity": "DEGRADED",
                    "status": "AWAITING_RETRY_OR_ESCALATION"
                }
            )
            return None # Owen waits. No assumptions.

        # 2. Shadow Accuracy & Pressure Metrics Tracking
        from ..preflight_validator import get_request_by_trace_id
        request = get_request_by_trace_id(trace_id)
        is_shadow = False
        audit_meta = {}
        
        if request:
            req_meta = request.get("metadata", {})
            is_shadow = req_meta.get("shadow_mode", False)
            auto_eligible = req_meta.get("auto_eligible", False)
            risk_level = req_meta.get("risk_level", "CONTROLLED")
            gate_action = req_meta.get("gate_action", "REQUIRE_APPROVAL")
            
            # --- OVERRIDE REASON CLASSIFICATION ---
            override_class = None
            if outcome_norm == "OVERRIDDEN":
                notes_lower = notes.lower()
                if any(k in notes_lower for k in ["wording", "typo", "format", "tone", "grammar", "style"]):
                    override_class = "cosmetic"
                elif any(k in notes_lower for k in ["dangerous", "wrong recipient", "critical", "security", "financial"]):
                    override_class = "critical_error"
                else:
                    override_class = "context_miss"

            # --- AGGREGATE AUDIT METRICS ---
            from .event_bus import EVENTS_LOG_PATH
            if EVENTS_LOG_PATH.exists():
                try:
                    with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
                        lines = f.readlines()[-500:] # Last 500 events
                        
                        # Initialize counters
                        metrics = {
                            "total": 0,
                            "approvals": 0,
                            "auto_act_eligible": {"SAFE": 0, "CONTROLLED": 0},
                            "total_by_risk": {"SAFE": 0, "CONTROLLED": 0, "CRITICAL": 0},
                            "overrides": {"cosmetic": 0, "context_miss": 0, "critical_error": 0},
                            "shadow_agreements": 0,
                            "shadow_total": 0
                        }
                        
                        # Include CURRENT event in counters
                        metrics["total"] = 1
                        metrics["total_by_risk"][risk_level] = 1
                        if gate_action == "REQUIRE_APPROVAL": metrics["approvals"] = 1
                        if auto_eligible: metrics["auto_act_eligible"][risk_level] = 1
                        if override_class: metrics["overrides"][override_class] = 1
                        if is_shadow and auto_eligible:
                            metrics["shadow_total"] = 1
                            if outcome_norm == "SUCCESS": metrics["shadow_agreements"] = 1

                        for line in lines:
                            try:
                                evt = json.loads(line)
                                if evt.get("type") == "OWEN_INSIGHT_EXTRACTED":
                                    m = evt.get("metadata", {})
                                    metrics["total"] += 1
                                    
                                    rl = m.get("risk_level", "CONTROLLED")
                                    metrics["total_by_risk"][rl] = metrics["total_by_risk"].get(rl, 0) + 1
                                    
                                    if m.get("gate_action") == "REQUIRE_APPROVAL": metrics["approvals"] += 1
                                    if m.get("auto_eligible"): 
                                        metrics["auto_act_eligible"][rl] = metrics["auto_act_eligible"].get(rl, 0) + 1
                                    
                                    oc = m.get("override_class")
                                    if oc: metrics["overrides"][oc] = metrics["overrides"].get(oc, 0) + 1
                                    
                                    if m.get("is_shadow") and m.get("auto_eligible"):
                                        metrics["shadow_total"] += 1
                                        if m.get("outcome") == "SUCCESS": metrics["shadow_agreements"] += 1
                            except Exception: continue

                        # Calculate final pressure metrics
                        audit_meta = {
                            "shadow_accuracy": round(metrics["shadow_agreements"] / metrics["shadow_total"], 3) if metrics["shadow_total"] > 0 else 1.0,
                            "approval_ratio": round(metrics["approvals"] / metrics["total"], 3),
                            "auto_act_rate_by_risk": {
                                k: round(metrics["auto_act_eligible"][k] / max(1, metrics["total_by_risk"][k]), 3)
                                for k in ["SAFE", "CONTROLLED"]
                            },
                            "override_mix": metrics["overrides"],
                            "audit_window_size": metrics["total"]
                        }
                        
                        emit_event(
                            "SHADOW_AUDIT_SUMMARY",
                            trace_id,
                            agent_id=COMPONENT_NAME,
                            metadata=audit_meta
                        )
                except Exception as e:
                    logger.error(f"Error calculating shadow audit metrics: {e}")

            is_shadow_meta = {
                "is_shadow": is_shadow, 
                "auto_eligible": auto_eligible,
                "risk_level": risk_level,
                "gate_action": gate_action,
                "override_class": override_class,
                **audit_meta
            }
        else:
            is_shadow_meta = {}

        scenario = "post_execution"  # Generally applies cross-scenario or mapped via trace
        summary = f"Real-world feedback ({outcome.upper()}): {notes}"
        
        # Outcome classification logic (unchanged core decision-making)
        override_class_internal = is_shadow_meta.get("override_class")
        if outcome_norm == "FAILURE":
            insight_type = "dont_do"
            confidence = 0.9
        elif outcome_norm == "SUCCESS":
            insight_type = "do"
            confidence = 0.9
        elif outcome_norm == "OVERRIDDEN":
            # Set confidence based on classification
            if override_class_internal == "cosmetic":
                confidence = 0.3
            elif override_class_internal == "critical_error":
                confidence = 0.9
            else:
                confidence = 0.6
                
            insight_type = "lesson_learned"
            summary = f"HUMAN OVERRIDE ({str(override_class_internal).upper()}): {notes} (System was technically correct but operator preferred a different path)"
        elif outcome_norm == "CONFLICT_RESOLVED":
            insight_type = "lesson_learned"
            confidence = 0.8
            summary = f"CONFLICT RESOLVED: {notes} (Strategic dominance established in decision loop)"
        else:
            insight_type = "lesson_learned"
            confidence = 0.5
            
        det_key = self._generate_deterministic_key(summary, trace_id)
        
        insight_id = write_owen_insight(
            COMPONENT_NAME,
            insight_type=insight_type,
            summary=summary,
            scenario_type=scenario,
            evidence=[trace_id],
            confidence=confidence,
            deterministic_key=det_key
        )
        
        emit_event(
            "OWEN_INSIGHT_EXTRACTED", 
            trace_id, 
            agent_id=COMPONENT_NAME,
            metadata={
                "insight_id": insight_id, 
                "outcome": outcome_norm,
                "evaluation_integrity": "VERIFIED",
                **is_shadow_meta
            }
        )
        return insight_id

    def ingest_execution_failure(self, failure_data: Dict[str, Any]):
        """
        Ingest a hard execution failure (Gateway layer) to immediately penalize confidence.
        """
        assert_write_permission(COMPONENT_NAME, MemoryDomain.OWEN_INSIGHTS)
        
        action_type = failure_data.get("action_type", "unknown")
        scenario = failure_data.get("scenario_type", "global")
        penalty = failure_data.get("confidence_penalty", 0.1)
        
        summary = f"CRITICAL FAILURE: {action_type} crashed during execution. Applying -{penalty} penalty to future intents."
        
        write_owen_insight(
            COMPONENT_NAME,
            insight_type="risk_pattern",
            summary=summary,
            scenario_type=scenario,
            evidence=["gateway_crash"],
            confidence=penalty, # Abuse confidence field to store penalty weight for fast lookup
            deterministic_key=self._generate_deterministic_key(summary, f"{action_type}_{scenario}")
        )
        logger.warning(f"[OWEN] Hard failure ingested for {action_type}. Confidence penalty applied.")

    def get_penalty_for_action(self, action_type: str) -> float:
        """
        Calculate the total confidence penalty for an action based on recent failures.
        Deterministic and fast.
        """
        assert_read_permission(COMPONENT_NAME, MemoryDomain.OWEN_INSIGHTS)
        
        insights = read_owen_insights(COMPONENT_NAME, limit=50)
        # Filter for recent critical failures matching this action
        failures = [
            i for i in insights 
            if i["insight_type"] == "risk_pattern" 
            and action_type.lower() in i["summary"].lower()
        ]
        
        if not failures:
            return 0.0
            
        # Sum of penalties (max 0.4 per action to prevent total paralysis)
        total_penalty = sum(i.get("confidence", 0.1) for i in failures)
        return min(total_penalty, 0.4)

    def _generate_deterministic_key(self, summary: str, scenario: str) -> str:
        """Create a stable key for an insight to prevent duplicates during replay."""
        import hashlib
        raw = f"{summary.strip()}|{scenario.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def format_briefing_for_prompt(self, briefing: Dict[str, Any]) -> str:
        """
        Convert structured briefing into a clean text block for agent prompts.
        Used by the orchestrator.
        """
        if not briefing.get("lessons_learned") and not briefing.get("patterns", {}).get("dos"):
             return "No mature intelligence patterns detected yet for this scenario."

        lines = [f"OWEN INTELLIGENCE BRIEFING ({briefing['scenario']})"]
        lines.append(f"Historical Reliability: {briefing['metrics']['net_outcome_score']} (Sample size: {briefing['metrics']['sample_size']})")
        
        if briefing.get("lessons_learned"):
            lines.append("\nLESSONS LEARNED:")
            for l in briefing["lessons_learned"]:
                lines.append(f" - {l}")
        
        dos = briefing.get("patterns", {}).get("dos", [])
        if dos:
            lines.append("\nPROVEN STABLE PATTERNS (DO):")
            for d in dos:
                lines.append(f" - {d}")

        donts = briefing.get("patterns", {}).get("donts", [])
        if donts:
            lines.append("\nREJECTED/OVERRIDDEN PATTERNS (DON'T DO):")
            for d in donts:
                lines.append(f" - {d}")

        return "\n".join(lines)
