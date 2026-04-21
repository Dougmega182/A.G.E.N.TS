"""
Test 4: Owen Memory Drift Test
Goal: Ensure Owen updates when reality changes.
"""

import sys
import os
import unittest
from pathlib import Path

import tempfile

# PRE-IMPORT ENV SETUP
TEST_DB_PATH = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_DB_PATH"] = TEST_DB_PATH

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.logic import memory_db
from agents.logic.owen_engine import OwenEngine
from agents.logic import memory_cache

class TestOwenMemoryDrift(unittest.TestCase):

    def setUp(self):
        self.db_path = os.environ["AGENTS_DB_PATH"]
        self.owen = OwenEngine()

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass

    def test_breifing_updates_on_failure_spike(self):
        """Owen should change metrics and patterns when failures occur."""
        
        # 1. Feed 5 successful approvals
        for i in range(5):
            event = {
                "event_id": f"s{i}",
                "trace_id": f"ts{i}",
                "scenario": "variation",
                "timestamp": f"2026-04-16T1{i}:00:00",
                "metadata": {
                    "final_decision": "APPROVE",
                    "original_decision": "APPROVE",
                    "risk_score": 0.2,
                    "outcome_score": 1, 
                    "was_overridden": False
                }
            }
            memory_db.write_decision("orchestrator", event)
            self.owen.extract_lesson_from_decision(event)

        memory_cache.clear_cache("orchestrator")
        brief_stable = self.owen.generate_intelligence_briefing("variation")
        self.assertEqual(brief_stable["metrics"]["failure_rate"], 0.0)
        self.assertGreater(len(brief_stable["patterns"]["dos"]), 0)

        # 2. Feed 3 failures (overridden or bad outcome)
        for i in range(3):
            event = {
                "event_id": f"f{i}",
                "trace_id": f"tf{i}",
                "scenario": "variation",
                "timestamp": f"2026-04-17T1{i}:00:00",
                "metadata": {
                    "final_decision": "ESCALATE",
                    "original_decision": "APPROVE",
                    "risk_score": 0.5,
                    "outcome_score": -1, # Failure
                    "was_overridden": True,
                    "primary_override_reason": "safety_violation"
                }
            }
            memory_db.write_decision("orchestrator", event)
            self.owen.extract_lesson_from_decision(event)

        memory_cache.clear_cache("orchestrator")
        brief_drifted = self.owen.generate_intelligence_briefing("variation")
        
        # Assert metrics drifted
        self.assertGreater(brief_drifted["metrics"]["failure_rate"], 0.0)
        self.assertGreater(brief_drifted["metrics"]["override_rate"], 0.0)
        
        # Assert new "Don't Do" patterns appeared
        self.assertGreater(len(brief_drifted["patterns"]["donts"]), 0)
        self.assertIn("overridden by orchestrator", brief_drifted["patterns"]["donts"][0])

if __name__ == "__main__":
    unittest.main()
