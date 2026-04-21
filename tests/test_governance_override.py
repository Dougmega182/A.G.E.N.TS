"""
Test 5: Governance Override Test
Goal: Ensure CRITICAL flag always triggers ESCALATE and emits correct events.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import tempfile

# PRE-IMPORT ENV SETUP
TEST_DB_PATH = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_DB_PATH"] = TEST_DB_PATH

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator
from agents.logic.governance_engine import GovernanceFlag

class TestGovernanceOverride(unittest.TestCase):

    def setUp(self):
        self.db_path = os.environ["AGENTS_DB_PATH"]
        self.orchestrator = Orchestrator()

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass

    @patch('agents.orchestrator.evaluate_governance')
    @patch('agents.orchestrator.event_bus.emit_event')
    async def test_critical_flag_forces_escalate(self, mock_emit, mock_eval):
        """If a CRITICAL flag is detected, the loop should announce it."""
        # 1. Mock a CRITICAL flag
        mock_eval.return_value = [
            GovernanceFlag(flag_type="MAX_COST_EXCEEDED", severity="CRITICAL", message="Stop!", threshold="test")
        ]
        
        # 2. Run a generator loop (partial run to check trigger)
        # We need to wrap it since it's an async generator
        trace_id = "test-crit-1"
        gen = self.orchestrator._run_generic_construction_loop("variation", "1000k cost", trace_id)
        
        found_forced = False
        async for msg in gen:
            if "CRITICAL GOVERNANCE FLAG(S) DETECTED" in msg:
                found_forced = True
            if "Decision will be forced to ESCALATE" in msg:
                 found_forced = True
        
        self.assertTrue(found_forced, "Loop did not detect/announce critical flag override")
        
        # 3. Verify event emitted
        mock_emit.assert_any_call(
            "GOVERNANCE_CRITICAL_OVERRIDE", 
            trace_id, 
            scenario="variation", 
            metadata={
                "critical_flags": "MAX_COST_EXCEEDED",
                "action": "forced_escalate"
            }
        )

if __name__ == "__main__":
    # Test runner for async
    import asyncio
    test = TestGovernanceOverride()
    test.setUp()
    asyncio.run(test.test_critical_flag_forces_escalate())
