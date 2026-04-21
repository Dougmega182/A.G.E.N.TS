"""
Stress Test 7: Memory Poisoning Test (Owen)
Goal: Ensure Owen does NOT blindly reinforce bad historical data.
Simulates injecting misleading "always approve $50k variations" patterns.
"""

import sys
import os
import unittest
from pathlib import Path

import tempfile
os.environ["AGENTS_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_PREFLIGHT_STORE"] = tempfile.mktemp(suffix=".json")

sys.path.append(str(Path(__file__).parent.parent))

from agents.logic.owen_engine import OwenEngine
from agents.logic import memory_db


class TestMemoryPoisoning(unittest.TestCase):

    def setUp(self):
        self.owen = OwenEngine()

    def test_overridden_decision_creates_dont_do_not_do(self):
        """
        If a decision was overridden by governance, Owen must create
        a 'dont_do' insight — NOT a 'do' insight, regardless of what
        the original decision was.
        """
        poisoned_event = {
            "trace_id": "trace-poison-1",
            "scenario": "variation",
            "metadata": {
                "final_decision": "ESCALATE",
                "original_decision": "APPROVE",
                "was_overridden": True,
                "primary_override_reason": "governance_critical",
                "outcome_score": 1,  # Attacker tries to make it look successful
            }
        }

        insight_id = self.owen.extract_lesson_from_decision(poisoned_event)
        self.assertIsNotNone(insight_id, "Owen should have extracted an insight")

        # Read the insight back
        insights = memory_db.read_owen_insights("owen_engine", scenario_type="variation")
        self.assertEqual(len(insights), 1)

        # CRITICAL: must be a "dont_do" despite the positive outcome_score
        self.assertEqual(insights[0]["insight_type"], "dont_do")
        self.assertIn("overridden", insights[0]["summary"].lower())

    def test_low_outcome_score_does_not_create_do_pattern(self):
        """
        Owen should NOT extract a 'do' pattern from a decision
        with outcome_score <= 0 (failure or neutral).
        """
        bad_event = {
            "trace_id": "trace-poison-2",
            "scenario": "variation",
            "metadata": {
                "final_decision": "APPROVE",
                "original_decision": "APPROVE",
                "was_overridden": False,
                "outcome_score": 0,  # Neutral — not a success
            }
        }

        insight_id = self.owen.extract_lesson_from_decision(bad_event)
        # Should NOT create an insight for neutral outcome
        self.assertIsNone(insight_id)

    def test_escalated_decision_does_not_create_do_pattern(self):
        """
        Owen must never create a 'do' pattern for ESCALATE decisions,
        even with a positive outcome score.
        """
        escalated_event = {
            "trace_id": "trace-poison-3",
            "scenario": "variation",
            "metadata": {
                "final_decision": "ESCALATE",
                "original_decision": "APPROVE",
                "was_overridden": False,
                "outcome_score": 1,  # Positive, but it was escalated
            }
        }

        insight_id = self.owen.extract_lesson_from_decision(escalated_event)
        # Should NOT create a positive pattern for an escalated decision
        self.assertIsNone(insight_id)

    def test_confidence_stays_bounded(self):
        """
        Owen insights should never have confidence > 1.0 or < 0.0,
        even after repeated validation.
        """
        # Create a genuine positive decision
        good_event = {
            "trace_id": "trace-poison-4",
            "scenario": "material_order",
            "metadata": {
                "final_decision": "APPROVE",
                "original_decision": "APPROVE",
                "was_overridden": False,
                "outcome_score": 1,
            }
        }

        insight_id = self.owen.extract_lesson_from_decision(good_event)
        self.assertIsNotNone(insight_id)

        # Read it back — confidence should be within [0, 1]
        insights = memory_db.read_owen_insights("owen_engine", scenario_type="material_order")
        self.assertGreaterEqual(insights[0]["confidence"], 0.0)
        self.assertLessEqual(insights[0]["confidence"], 1.0)

    def test_briefing_reflects_override_rate(self):
        """
        If most decisions were overridden, the briefing should show
        a high override_rate metric — alerting agents to systemic issues.
        """
        # Inject 3 overridden decisions into the DB directly
        for i in range(3):
            event = {
                "event_id": f"poison-brief-{i}",
                "trace_id": f"trace-brief-{i}",
                "scenario": "safety_upgrade",
                "timestamp": "2026-01-01T00:00:00",
                "metadata": {
                    "final_decision": "ESCALATE",
                    "original_decision": "APPROVE",
                    "was_overridden": True,
                    "outcome_score": -1,
                }
            }
            memory_db.write_decision("orchestrator", event)

        # Generate briefing
        briefing = self.owen.generate_intelligence_briefing("safety_upgrade")

        # Override rate should be 100% (3/3)
        self.assertEqual(briefing["metrics"]["override_rate"], 1.0)
        self.assertEqual(briefing["metrics"]["sample_size"], 3)
        # Net outcome should be negative
        self.assertLess(briefing["metrics"]["net_outcome_score"], 0)


if __name__ == "__main__":
    unittest.main()
