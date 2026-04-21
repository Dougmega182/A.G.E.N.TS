"""
Stress Test 5: Human-in-the-Loop Break Test
Goal: Ensure approval is truly required — fake, missing, and expired approvals all blocked.
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
from agents.firewall import PreflightApprovalEngine


def _make_intent(trace_id):
    return {
        "action": "gmail_draft",
        "agent_id": "jenny",
        "parameters": {"to": "test@example.com", "subject": "HITL Test", "body": "Testing."},
        "trace_id": trace_id,
        "requires_approval": True,
        "status": "approved"
    }


class TestHumanInTheLoopBreak(unittest.TestCase):

    def setUp(self):
        self.gateway = ExternalGateway()
        self.approval_engine = PreflightApprovalEngine()

    def test_fake_approval_id_blocked(self):
        """A completely fabricated approval ID must be rejected."""
        intent = _make_intent("trace-hitl-fake")

        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, "APR-FAKE12345678")

        self.assertEqual(cm.exception.reason, "approval_not_found")

    def test_missing_approval_id_blocked(self):
        """Empty approval ID must be rejected."""
        intent = _make_intent("trace-hitl-missing")

        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, "")

        self.assertEqual(cm.exception.reason, "approval_not_found")

    def test_rejected_approval_blocked(self):
        """An approval that was explicitly REJECTED must block execution."""
        intent = _make_intent("trace-hitl-rejected")

        req = self.approval_engine.create_or_get_request(intent)
        approval_id = req["request_id"]
        # Human explicitly rejects
        self.approval_engine.decide_request(approval_id, "reject", reason="Too risky")

        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, approval_id)

        self.assertEqual(cm.exception.reason, "intent_not_approved")
        self.assertEqual(cm.exception.details["status"], "rejected")

    def test_pending_approval_blocked(self):
        """An approval that is still pending (not yet decided) must block execution."""
        intent = _make_intent("trace-hitl-pending")

        req = self.approval_engine.create_or_get_request(intent)
        approval_id = req["request_id"]
        # Intentionally NOT deciding — remains pending

        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, approval_id)

        self.assertEqual(cm.exception.reason, "intent_not_approved")
        self.assertEqual(cm.exception.details["status"], "pending")

    def test_approval_for_wrong_payload_blocked(self):
        """An approval for a different payload must not authorize this intent."""
        # Create approval for payload A
        intent_a = _make_intent("trace-hitl-wrong-a")
        intent_a["parameters"]["subject"] = "Original Subject"
        req = self.approval_engine.create_or_get_request(intent_a)
        approval_id = req["request_id"]
        self.approval_engine.decide_request(approval_id, "approve")

        # Try to execute payload B with approval for A
        intent_b = _make_intent("trace-hitl-wrong-b")
        intent_b["parameters"]["subject"] = "TAMPERED Subject"

        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent_b, approval_id)

        self.assertEqual(cm.exception.reason, "payload_integrity_violation")


if __name__ == "__main__":
    unittest.main()
