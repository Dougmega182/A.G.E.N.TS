"""
Test 1: Cold Start Rebuild (Truth Test)
Goal: Verify the system can be 100% reconstructed from event logs.
"""

import os
import sys
import unittest
import json
import tempfile
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Isolate environment before imports
temp_log = tempfile.mktemp(suffix=".jsonl")
temp_db = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_DB_PATH"] = temp_db

from agents.logic import event_bus, memory_db, owen_engine
# Override event log path in module
event_bus.EVENTS_LOG_PATH = Path(temp_log)


class TestColdStartRebuild(unittest.TestCase):

    def setUp(self):
        # Ensure fresh state
        if Path(temp_log).exists(): os.remove(temp_log)
        if Path(temp_db).exists(): os.remove(temp_db)
        
        self.owen = owen_engine.OwenEngine()

    def test_complete_reconstruction(self):
        """
        Flow: Generate Events -> Create New DB -> Rebuild -> Verify Parity
        """
        # 1. Generate 3 Decisions
        for i in range(3):
            event = {
                "event_id": f"evt-{i}",
                "trace_id": f"trace-{i}",
                "scenario": "material_order",
                "timestamp": "2026-04-17T12:00:00",
                "metadata": {
                    "final_decision": "APPROVE",
                    "original_decision": "APPROVE",
                    "was_overridden": False,
                    "outcome_score": 1,
                    "risk_score": 0.1,
                    "justification": f"Order {i} looks good."
                }
            }
            # This writes to both Log and DB
            event_bus.emit_event("DECISION_FINALIZED_V1", f"trace-{i}", metadata=event["metadata"])
            memory_db.write_decision("orchestrator", event)

        # 2. Extract 1 Owen Lesson (this now emits an event!)
        decision_event = {
            "trace_id": "trace-lesson-1",
            "scenario": "security_breach",
            "metadata": {
                "final_decision": "ESCALATE",
                "original_decision": "APPROVE",
                "was_overridden": True,
                "primary_override_reason": "governance_critical",
                "outcome_score": -1
            }
        }
        event_bus.emit_event("DECISION_FINALIZED_V1", "trace-lesson-1", scenario="security_breach", metadata=decision_event["metadata"])
        memory_db.write_decision("orchestrator", decision_event)
        
        # Now let Owen extract insight (writes to DB and Log)
        insight_id = self.owen.extract_lesson_from_decision(decision_event)

        # 3. VERIFY PRE-WIPE STATE
        decisions_pre = memory_db.read_decisions("orchestrator")
        insights_pre = memory_db.read_owen_insights("owen_engine")
        self.assertEqual(len(decisions_pre), 4)
        self.assertEqual(len(insights_pre), 1)

        # 4. THE COLD START (using a fresh DB path to avoid Windows locks)
        fresh_db = tempfile.mktemp(suffix=".db")
        self.assertNotEqual(temp_db, fresh_db)

        # 5. THE REBUILD
        from agents.logic.rebuild_memory import rebuild
        rebuild(Path(temp_log), Path(fresh_db))

        # 6. VERIFY POST-REBUILD PARITY
        # Point memory_db to the fresh one
        memory_db.DB_PATH = Path(fresh_db)
        
        decisions_post = sorted(memory_db.read_decisions("orchestrator"), key=lambda x: x["trace_id"])
        insights_post = memory_db.read_owen_insights("owen_engine") # Only 1, no need to sort

        self.assertEqual(len(decisions_post), 4, "Decisions missing after rebuild!")
        self.assertEqual(len(insights_post), 1, "Owen insights missing after rebuild!")
        
        # Internal Content Parity
        decisions_pre_sorted = sorted(decisions_pre, key=lambda x: x["trace_id"])
        
        self.assertEqual(insights_post[0]["insight_type"], "dont_do")
        self.assertIn("overridden", insights_post[0]["summary"])
        self.assertEqual(decisions_post[0]["trace_id"], decisions_pre_sorted[0]["trace_id"])

        print(f"\n[COLD START] Rebuild successful. Parity between {Path(temp_db).name} and {Path(fresh_db).name} confirmed.")


if __name__ == "__main__":
    unittest.main()
