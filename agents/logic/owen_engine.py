"""
Owen Intelligence Engine — The System's Intelligence Synthesizer.

This engine implements Owen's new role as the "Memory Intelligence Layer".
It is RESPONSIBLE for:
    1. Extracting patterns and lessons from the decisions database.
    2. Generating deterministic Intelligence Briefings for the decision loop.
    3. Updating the owen_insights table with new findings.

It is NOT PERMITTED to:
    1. Make decisions or influence governance.
    2. Affect the reasoning of other agents beyond providing context data.
    3. Use LLM calls in the real-time execution path (deterministic only).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .memory_contract import (
    MemoryDomain,
    OWEN_BOUNDARY,
    check_owen_boundary,
    assert_write_permission,
    assert_read_permission,
)
from .memory_db import (
    read_decisions,
    read_owen_insights,
    write_owen_insight,
    validate_owen_insight,
)
from .memory_cache import cache_owen_briefing, get_owen_briefing
from . import event_bus

logger = logging.getLogger("agents.owen_engine")

COMPONENT_NAME = "owen_engine"


class OwenEngine:
    """Owen's intelligence core for pattern extraction and synthesis."""

    def __init__(self):
        if not check_owen_boundary("initialize"):
             raise RuntimeError("Owen boundary check failed during initialization")

    def generate_intelligence_briefing(self, scenario_type: str, query_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Produce a deterministic intelligence briefing for the current scenario.
        Checks cache first, then synthesizes from SQLite.
        """
        assert_read_permission(COMPONENT_NAME, MemoryDomain.OWEN_INSIGHTS)

        # 0. Performance: Keyword Gate (Short-circuit for low-priority scenarios)
        # Check both scenario_type AND the actual query_text for core keywords.
        CORE_KEYWORDS = {"delay", "rain", "weather", "cost", "budget", "safety", "concrete", "pour", "incident", "issue"}
        combined_text = f"{scenario_type} {query_text or ''}".lower()
        if not any(kw in combined_text for kw in CORE_KEYWORDS):
             return {
                 "scenario": scenario_type,
                 "metrics": {"sample_size": 0, "failure_rate": 0, "override_rate": 0, "net_outcome_score": 0},
                 "lessons_learned": [],
                 "patterns": {"dos": [], "donts": [], "risk_patterns": []},
                 "timestamp": datetime.utcnow().isoformat(),
                 "note": "Short-circuited (no core keywords detected)"
             }

        # 1. Check Cache
        cached = get_owen_briefing(COMPONENT_NAME, scenario_type)
        if cached:
            return cached

        # 2. Synthesize from DB
        recent_decisions = read_decisions(COMPONENT_NAME, scenario=scenario_type, limit=20)
        existing_insights = read_owen_insights(COMPONENT_NAME, scenario_type=scenario_type, limit=5)

        # 3. Calculate Deterministic Metrics
        total_recent = len(recent_decisions)
        overrides = [d for d in recent_decisions if d.get("was_overridden")]
        failures = [d for d in recent_decisions if d.get("outcome_score", 0) < 0]
        
        failure_rate = (len(failures) / total_recent) if total_recent > 0 else 0
        override_rate = (len(overrides) / total_recent) if total_recent > 0 else 0

        # 4. Filter Insights by Type
        lessons = [i["summary"] for i in existing_insights if i["insight_type"] == "lesson_learned"]
        dos = [i["summary"] for i in existing_insights if i["insight_type"] == "do"]
        donts = [i["summary"] for i in existing_insights if i["insight_type"] == "dont_do"]
        risk_patterns = [i["summary"] for i in existing_insights if i["insight_type"] == "risk_pattern"]

        # 4b. Pull Negative Patterns (Execution Drift)
        # We focus on the core construction actions (gmail_draft) for now
        from .memory_db import get_patterns_for_action
        negative_patterns = get_patterns_for_action(COMPONENT_NAME, "gmail_draft")

        # 5. Build Briefing
        briefing = {
            "scenario": scenario_type,
            "metrics": {
                "sample_size": total_recent,
                "failure_rate": round(failure_rate, 2),
                "override_rate": round(override_rate, 2),
                "net_outcome_score": sum(d.get("outcome_score", 0) for d in recent_decisions)
            },
            "lessons_learned": lessons,
            "patterns": {
                "dos": dos,
                "donts": donts,
                "risk_patterns": risk_patterns,
                "negative_patterns": negative_patterns
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        # 6. Cache and Return
        cache_owen_briefing(COMPONENT_NAME, scenario_type, briefing)
        return briefing

    def extract_lesson_from_decision(self, finalized_decision: Dict[str, Any]) -> Optional[int]:
        """
        Post-decision turn: Analyze the finalized decision and store any obvious lessons.
        Always deterministic logic.
        """
        assert_write_permission(COMPONENT_NAME, MemoryDomain.OWEN_INSIGHTS)

        meta = finalized_decision.get("metadata", {})
        scenario = finalized_decision.get("scenario", "unknown")
        trace_id = finalized_decision.get("trace_id", "unknown")
        
        was_overridden = meta.get("was_overridden", False)
        outcome_score = meta.get("outcome_score", 0)
        final_decision = meta.get("final_decision", "UNKNOWN")
        
        insight_id = None

        # Logic A: If it was overridden, it's a "Don't Do" or a "Lesson"
        if was_overridden:
            original = meta.get("original_decision", "UNKNOWN")
            reason = meta.get("primary_override_reason", "policy_alignment")
            
            if reason == "low_confidence":
                conf_reason = meta.get("confidence_reason", "No justification provided.")
                summary = f"Attempt to '{original}' was overridden due to LOW CONFIDENCE. Reason given: {conf_reason}. Avoid proposals lacking strong governance/historical backing."
            else:
                summary = f"Variation intent '{original}' was overridden by orchestrator ({reason}). Ensure alignment with governance before proposing."
            
            det_key = self._generate_deterministic_key(summary, scenario)
            insight_id = write_owen_insight(
                COMPONENT_NAME,
                insight_type="dont_do",
                summary=summary,
                scenario_type=scenario,
                evidence=[trace_id],
                confidence=0.8,
                deterministic_key=det_key
            )
            
            # Emit event to support Cold Start Rebuild
            event_bus.emit_event(
                "OWEN_INSIGHT_EXTRACTED", 
                trace_id, 
                agent_id=COMPONENT_NAME, 
                scenario=scenario, 
                metadata={
                    "insight_id": insight_id,
                    "insight_type": "dont_do",
                    "summary": summary,
                    "evidence": [trace_id],
                    "confidence": 0.8,
                    "deterministic_key": det_key
                }
            )
            logger.info(f"[OWEN] Extracted negative lesson from trace {trace_id}")

        # Logic B: If it succeeded (stable), it's a "Do" or "Pattern"
        elif outcome_score > 0 and final_decision != "ESCALATE":
            summary = f"Strategy '{final_decision}' resulted in a stable outcome for {scenario}."
            # Check if similar insight exists to validate instead of creating new
            existing = read_owen_insights(COMPONENT_NAME, scenario_type=scenario, insight_type="do", limit=1)
            
            if not existing:
                insight_id = write_owen_insight(
                    COMPONENT_NAME,
                    insight_type="do",
                    summary=summary,
                    scenario_type=scenario,
                    evidence=[trace_id],
                    confidence=0.6
                )
                # Emit event to support Cold Start Rebuild
                event_bus.emit_event(
                    "OWEN_INSIGHT_EXTRACTED", 
                    trace_id, 
                    agent_id=COMPONENT_NAME, 
                    scenario=scenario, 
                    metadata={
                        "insight_id": insight_id,
                        "insight_type": "do",
                        "summary": summary,
                        "evidence": [trace_id],
                        "confidence": 0.6
                    }
                )
                logger.info(f"[OWEN] Extracted positive pattern from trace {trace_id}")

            else:
                validate_owen_insight(COMPONENT_NAME, existing[0]["id"])
                event_bus.emit_event(
                    "OWEN_INSIGHT_VALIDATED", 
                    trace_id, 
                    agent_id=COMPONENT_NAME, 
                    scenario=scenario, 
                    metadata={
                        "insight_id": existing[0]["id"],
                        "summary": summary
                    }
                )

        return insight_id

    def extract_lesson_from_feedback(self, trace_id: str, outcome: str, notes: str) -> Optional[int]:
        """
        Ingest real-world execution feedback to close the loop on intelligence.
        """
        assert_write_permission(COMPONENT_NAME, MemoryDomain.OWEN_INSIGHTS)
        
        scenario = "post_execution"  # Generally applies cross-scenario or mapped via trace
        summary = f"Real-world feedback ({outcome.upper()}): {notes}"
        insight_type = "lesson_learned"
        
        if outcome == "failure":
            insight_type = "dont_do"
        elif outcome == "success":
            insight_type = "do"
            
        det_key = self._generate_deterministic_key(summary, trace_id)
        
        insight_id = write_owen_insight(
            COMPONENT_NAME,
            insight_type=insight_type,
            summary=summary,
            scenario_type=scenario,
            evidence=[trace_id],
            confidence=0.9, # Human feedback has very high confidence
            deterministic_key=det_key
        )
        
        event_bus.emit_event(
            "OWEN_INSIGHT_EXTRACTED", 
            trace_id, 
            agent_id=COMPONENT_NAME, 
            scenario=scenario, 
            metadata={
                "insight_id": insight_id,
                "insight_type": insight_type,
                "summary": summary,
                "evidence": [trace_id],
                "confidence": 0.9,
                "deterministic_key": det_key
            }
        )
        logger.info(f"[OWEN] Ingested human operational feedback from trace {trace_id}")
        return insight_id

    def ingest_execution_failure(self, event: dict):
        """Process execution drift and true failures to assign dynamic penalties."""
        action_type = event.get("action_type")
        diffs = event.get("diff", {})
        
        # If TRUE_FAILURE, there is no diff, we just use a generic 'missing' key
        if not diffs:
            from .memory_db import upsert_negative_pattern
            upsert_negative_pattern(COMPONENT_NAME, action_type, "object_missing")
            return
            
        for key in diffs.keys():
            from .memory_db import upsert_negative_pattern
            upsert_negative_pattern(COMPONENT_NAME, action_type, key)

    def get_penalty_for_action(self, action_type: str) -> float:
        """Calculate the total confidence penalty for an action based on recent failures."""
        from .memory_db import get_patterns_for_action
        patterns = get_patterns_for_action(COMPONENT_NAME, action_type)
        total_penalty = sum(p.get("penalty", 0.0) for p in patterns)
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

        # Add Reliability Alerts (Drift detection)
        neg_patterns = briefing.get("patterns", {}).get("negative_patterns", [])
        if neg_patterns:
            lines.append("\n⚠️ SYSTEM RELIABILITY ALERTS (EXECUTION DRIFT detected):")
            for p in neg_patterns:
                lines.append(f" - WARNING: Action '{p['action_type']}' has recurring failure on key '{p['failure_key']}' (Count: {p['count']}). Trust Index: {max(0, 1.0 - p['penalty']):.2f}")

        return "\n".join(lines)
