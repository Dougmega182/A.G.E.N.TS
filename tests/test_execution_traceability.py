"""
Verification Test 3: Execution Traceability
Goal: Proves that every side-effect is linked back to its reasoning trace via an execution_trace_id.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# PRE-IMPORT ENV SETUP
import tempfile
os.environ["AGENTS_DB_PATH"] = tempfile.mktemp(suffix=".db")

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.logic.external_gateway import ExternalGateway
from agents.preflight_validator import PreflightApprovalEngine
from agents.logic import event_bus

class TestExecutionTraceability(unittest.TestCase):

    def setUp(self):
        self.gateway = ExternalGateway()
        self.approval_engine = PreflightApprovalEngine()

    def test_trace_linkage_in_events(self):
        """Verifies that the gateway correctly links the execution trace to the parent trace."""
        parent_trace_id = "trace-reasoning-999"
        intent = {
            "action": "gmail_draft",
            "agent_id": "jenny",
            "parameters": {"to": "audit@example.com", "subject": "Audit Check", "body": "Logged."},
            "trace_id": parent_trace_id,
            "requires_approval": True,
            "status": "approved"
        }
        
        # 1. Create and APPROVE the request
        request = self.approval_engine.create_or_get_request(intent)
        approval_id = request["request_id"]
        self.approval_engine.decide_request(approval_id, "approve")

        # 2. Mock event_bus.emit_event to capture audit logs
        with patch('agents.logic.event_bus.emit_event') as mock_emit:
            # Execute
            outcome = self.gateway.validate_and_execute(intent, approval_id)
            
            # 3. Assertions on captured events
            # We expect:
            # - EXECUTION_STARTED
            # - EXTERNAL_SIDE_EFFECT_V1 (from operator)
            # - EXECUTION_COMPLETED
            
            calls = mock_emit.call_args_list
            
            # Find the side-effect event
            side_effect_event = next((c for c in calls if c[0][0] == "EXTERNAL_SIDE_EFFECT_V1"), None)
            self.assertIsNotNone(side_effect_event, "EXTERNAL_SIDE_EFFECT_V1 not emitted")
            
            # Side-effect event should be keyed by [execution_trace_id]
            execution_trace_id = side_effect_event[0][1]
            self.assertTrue(execution_trace_id.startswith("EXE-"))
            
            # Started/Completed events should be keyed by [parent_trace_id] and include execution_trace_id in metadata
            started_event = next((c for c in calls if c[0][0] == "EXECUTION_STARTED"), None)
            self.assertEqual(started_event[0][1], parent_trace_id)
            self.assertEqual(started_event[1]["metadata"]["execution_trace_id"], execution_trace_id)

            completed_event = next((c for c in calls if c[0][0] == "EXECUTION_COMPLETED"), None)
            self.assertEqual(completed_event[0][1], parent_trace_id)
            self.assertEqual(completed_event[1]["metadata"]["execution_trace_id"], execution_trace_id)

if __name__ == "__main__":
    unittest.main()
