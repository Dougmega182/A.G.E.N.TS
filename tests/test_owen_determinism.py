"""
Test 3: Owen Determinism Test
Goal: Owen must be stable and repeatable.
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

class TestOwenDeterminism(unittest.TestCase):

    def setUp(self):
        self.db_path = os.environ["AGENTS_DB_PATH"]
        
        # Seed DB with fixed data
        self.owen = OwenEngine()
        for i in range(5):
            event = {
                "event_id": f"e{i}",
                "trace_id": f"t{i}",
                "scenario": "variation",
                "timestamp": "now",
                "metadata": {
                    "final_decision": "APPROVE",
                    "original_decision": "APPROVE",
                    "risk_score": 0.2,
                    "outcome_score": 1 # Success
                }
            }
            memory_db.write_decision("orchestrator", event)
            self.owen.extract_lesson_from_decision(event)

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass

    def test_briefing_is_deterministic(self):
        """Owen must produce the exact same briefing for the same data."""
        # Clear cache to force synthesis
        from agents.logic import memory_cache
        memory_cache.clear_cache("orchestrator")
        
        brief1 = self.owen.generate_intelligence_briefing("variation")
        
        # Clear cache again
        memory_cache.clear_cache("orchestrator")
        brief2 = self.owen.generate_intelligence_briefing("variation")
        
        self.assertEqual(brief1["metrics"], brief2["metrics"])
        self.assertEqual(brief1["patterns"], brief2["patterns"])
        self.assertEqual(len(brief1["patterns"]["dos"]), len(brief2["patterns"]["dos"]))

if __name__ == "__main__":
    unittest.main()
