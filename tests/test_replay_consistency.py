"""
Test 7: Replay Consistency Test
Goal: Ensure that re-running history yields exact same SQLite state.
"""

import sys
import os
import json
import unittest
from pathlib import Path

import tempfile

# PRE-IMPORT ENV SETUP
TEST_DB_PATH = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_DB_PATH"] = TEST_DB_PATH

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.logic import memory_db
from scripts.migrate_events_to_db import migrate

class TestReplayConsistency(unittest.TestCase):

    def setUp(self):
        self.db_path = os.environ["AGENTS_DB_PATH"]

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass

    def test_replay_idempotency(self):
        """Verifies that running migration twice doesn't duplicate data if IDs are same."""
        
        test_log = Path("Agent logs/test_replay.jsonl")
        test_log.parent.mkdir(parents=True, exist_ok=True)
        
        event = {
            "timestamp": "2026-04-16T10:00:00",
            "event_id": "unique-e1",
            "trace_id": "unique-t1",
            "type": "DECISION_FINALIZED_V1",
            "scenario": "variation",
            "metadata": {
                "final_decision": "APPROVE",
                "risk_score": 0.3
            }
        }
        
        with open(test_log, "w") as f:
            f.write(json.dumps(event) + "\n")

        # Patch migration script path
        import scripts.migrate_events_to_db as mig_script
        original_path = mig_script.EVENTS_LOG_PATH
        mig_script.EVENTS_LOG_PATH = test_log
        
        try:
            # First run
            migrate()
            count1 = len(memory_db.read_decisions("orchestrator"))
            
            # Second run
            migrate()
            count2 = len(memory_db.read_decisions("orchestrator"))
            
            self.assertEqual(count1, 1)
            self.assertEqual(count2, 1, "Duplicate data detected on replay!")
            
        finally:
            mig_script.EVENTS_LOG_PATH = original_path
            if test_log.exists():
                test_log.unlink()

if __name__ == "__main__":
    unittest.main()
