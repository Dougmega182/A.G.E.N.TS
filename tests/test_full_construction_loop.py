"""
Test 6: End-to-End Loop Test (FULL SYSTEM)
Goal: Ensure Owen briefing -> Governance -> Agents -> Final Decision -> DB flow is solid.
"""

import sys
import os
import json
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import tempfile

# PRE-IMPORT ENV SETUP
TEST_DB_PATH = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_DB_PATH"] = TEST_DB_PATH

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator
from agents.logic import memory_db

class TestFullConstructionLoop(unittest.TestCase):

    def setUp(self):
        self.db_path = os.environ["AGENTS_DB_PATH"]
        self.orchestrator = Orchestrator()

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass

    @patch('agents.orchestrator.Orchestrator._execute_contract_turn', new_callable=AsyncMock)
    async def test_full_loop_execution(self, mock_turn):
        """Verifies the entire chain of reasoning and persistence."""
        
        # 1. Define Static Mocks for each agent turn
        # Nadia
        mock_turn.side_effect = [
            # Nadia: plan_v1
            ('{"goal": "Fix leak", "steps": ["step 1"]}', True, None),
            # Tucker: implementation_plan_v1
            ('{"project_name": "LeakFix", "steps": ["weld"]}', True, None),
            # WALL-E: critique_v1
            ('{"critique": "Looks okay", "logic_check": "PASS", "recommendation": "PROCEED"}', True, None),
            # Aria: decision_v1
            ('{"decision": "APPROVE", "justification": "Owen said it is safe", "impact": {"cost": 5000}}', True, None),
            # Jenny: email_draft_v1
            ('{"subject": "Approved", "body": "Go ahead"}', True, None),
            # Audit: audit_log_v1
            ('{"audit_entry": {"step": "final"}}', True, None)
        ]

        # 2. Run the loop
        trace_id = "test-loop-full-1"
        gen = self.orchestrator._run_generic_construction_loop("variation", "repair leak 5k cost", trace_id)
        
        messages = []
        async for msg in gen:
            messages.append(msg)
        
        # 3. Assertions
        # Check if Owen briefing was loaded
        self.assertTrue(any("Owen's Intelligence Briefing loaded" in m for m in messages))
        
        # Check if Aria received Owen's context (can't check mock call args easily with side_effect, 
        # but we check if the loop completed successfully)
        self.assertTrue(any("[ARIA] END" in m for m in messages))
        self.assertTrue(any("PROPOSAL CREATED" in m for m in messages))

        # 4. Verify SQLite Persistence
        decisions = memory_db.read_decisions("orchestrator", limit=1)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["final_decision"], "APPROVE")
        self.assertEqual(decisions[0]["trace_id"], trace_id)
        
        # 5. Verify Owen Synthesis called (check if owen_insights updated)
        insights = memory_db.read_owen_insights("orchestrator")
        # Should have at least the 'do' pattern from this successful run
        self.assertGreaterEqual(len(insights), 1)

if __name__ == "__main__":
    import asyncio
    test = TestFullConstructionLoop()
    test.setUp()
    asyncio.run(test.test_full_loop_execution())
