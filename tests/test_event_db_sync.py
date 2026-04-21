"""
Test 2: Event -> DB Consistency Test
Goal: Ensure event log == SQLite projection.
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

class TestEventDbSync(unittest.TestCase):

    def setUp(self):
        # Fresh environment
        self.db_path = os.environ["AGENTS_DB_PATH"]
        
        self.log_path = Path("Agent logs/test_events_sync.jsonl")
        if self.log_path.exists():
            try:
                self.log_path.unlink()
            except PermissionError:
                pass
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Cleanup
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            if self.log_path.exists():
                os.remove(self.log_path)
        except PermissionError:
            pass

    def test_sync_preserves_data(self):
        """Verifies that migration preserves trace_id and metadata keys."""
        
        # 1. Create mock events
        events = [
            {
                "timestamp": "2026-04-16T10:00:00",
                "event_id": "e1",
                "trace_id": "trace-sync-1",
                "type": "DECISION_FINALIZED_V1",
                "scenario": "variation",
                "metadata": {
                    "final_decision": "APPROVE",
                    "original_decision": "APPROVE",
                    "risk_score": 0.4,
                    "override_chain": ["SOME_POLICY"],
                    "impact": {"cost": 5000}
                }
            },
            {
                "timestamp": "2026-04-16T11:00:00",
                "event_id": "e2",
                "trace_id": "trace-sync-2",
                "type": "DECISION_MADE", # Legacy event
                "metadata": {
                    "decision": "reject",
                    "risk_score": 0.9,
                    "justification": "Too risky"
                }
            }
        ]
        
        with open(str(self.log_path), "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        # 2. Patch the script's global path before running
        import scripts.migrate_events_to_db as mig_script
        original_path = mig_script.EVENTS_LOG_PATH
        mig_script.EVENTS_LOG_PATH = self.log_path
        
        try:
            migrate()
        finally:
            mig_script.EVENTS_LOG_PATH = original_path

        # 3. Verify SQLite
        results = memory_db.read_decisions("orchestrator", limit=10)
        self.assertEqual(len(results), 2)
        
        # Check trace-sync-1 (New schema)
        d1 = next(d for d in results if d["trace_id"] == "trace-sync-1")
        self.assertEqual(d1["final_decision"], "APPROVE")
        self.assertEqual(json.loads(d1["override_chain"]), ["SOME_POLICY"])
        
        # Check trace-sync-2 (Legacy transformed)
        d2 = next(d for d in results if d["trace_id"] == "trace-sync-2")
        self.assertEqual(d2["final_decision"], "REJECT")
        self.assertEqual(d2["risk_score"], 0.9)
        self.assertEqual(d2["justification"], "Too risky")

if __name__ == "__main__":
    unittest.main()
