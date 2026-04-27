"""
Stress Test 2: Replay Attack (Security)
Goal: Ensure an approved intent can't be reused after execution.
"""

import sys
import os
import unittest
from pathlib import Path

import tempfile
os.environ["AGENTS_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_PREFLIGHT_STORE"] = tempfile.mktemp(suffix=".json")

sys.path.append(str(Path(__file__).parent.parent))

from agents.logic.external_gateway import ExternalGateway, GatewayError
from agents.preflight_validator import PreflightApprovalEngine


class TestReplayAttack(unittest.TestCase):

    def setUp(self):
        self.gateway = ExternalGateway()
        self.approval_engine = PreflightApprovalEngine()

    def test_double_execution_blocked(self):
        """Submitting the exact same approved payload twice must be blocked."""
        intent = {
            "action": "gmail_draft",
            "agent_id": "jenny",
            "parameters": {"to": "victim@example.com", "subject": "Invoice", "body": "Pay now."},
            "trace_id": "trace-replay-1",
            "requires_approval": True,
            "status": "approved"
        }

        # 1. Create and approve
        request = self.approval_engine.create_or_get_request(intent)
        approval_id = request["request_id"]
        self.approval_engine.decide_request(approval_id, "approve")

        # 2. First execution — should succeed
        outcome = self.gateway.validate_and_execute(intent, approval_id)
        self.assertEqual(outcome["status"], "success")

        # 3. Second execution — MUST be blocked
        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, approval_id)

        self.assertEqual(cm.exception.reason, "replay_blocked")
        self.assertIn("already been executed", cm.exception.details["reason"])

    def test_different_approval_same_payload_allowed(self):
        """A new approval for the same payload should be treated as a new execution."""
        params = {"to": "legit@example.com", "subject": "Report", "body": "Monthly update."}

        # First intent + approval
        intent1 = {
            "action": "gmail_draft", "agent_id": "jenny",
            "parameters": params, "trace_id": "trace-replay-2a",
            "requires_approval": True, "status": "approved"
        }
        req1 = self.approval_engine.create_or_get_request(intent1)
        self.approval_engine.decide_request(req1["request_id"], "approve")
        self.gateway.validate_and_execute(intent1, req1["request_id"])

        # Second intent with NEW trace_id + NEW approval
        intent2 = {
            "action": "gmail_draft", "agent_id": "jenny",
            "parameters": params, "trace_id": "trace-replay-2b",
            "requires_approval": True, "status": "approved"
        }
        req2 = self.approval_engine.create_or_get_request(intent2)
        self.approval_engine.decide_request(req2["request_id"], "approve")

        # Should succeed — different approval ID
        outcome = self.gateway.validate_and_execute(intent2, req2["request_id"])
        self.assertEqual(outcome["status"], "success")

    def test_replay_with_modified_trace_id_still_blocked(self):
        """Changing the trace_id but reusing the same approval_id is still blocked."""
        intent = {
            "action": "gmail_draft", "agent_id": "jenny",
            "parameters": {"to": "a@b.com", "subject": "X", "body": "Y"},
            "trace_id": "trace-replay-3",
            "requires_approval": True, "status": "approved"
        }

        req = self.approval_engine.create_or_get_request(intent)
        self.approval_engine.decide_request(req["request_id"], "approve")
        self.gateway.validate_and_execute(intent, req["request_id"])

        # Try replaying with a different trace_id but same approval
        intent["trace_id"] = "trace-replay-3-FORGED"
        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, req["request_id"])
        self.assertEqual(cm.exception.reason, "replay_blocked")


if __name__ == "__main__":
    unittest.main()
