"""
Stress Test 1: Kill-Switch (Failure Safety)
Goal: Prove nothing executes if something goes wrong mid-chain.
Simulates: Gateway crash after approval but before execution completes.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import tempfile
os.environ["AGENTS_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_PREFLIGHT_STORE"] = tempfile.mktemp(suffix=".json")

sys.path.append(str(Path(__file__).parent.parent))

from agents.logic.external_gateway import ExternalGateway, GatewayError
from agents.logic.execution_queue import ExecutionQueue
from agents.firewall import PreflightApprovalEngine


def _make_intent(trace_id="trace-killswitch"):
    return {
        "action": "gmail_draft",
        "agent_id": "jenny",
        "parameters": {"to": "test@example.com", "subject": "Kill Switch", "body": "Testing failure."},
        "trace_id": trace_id,
        "requires_approval": True,
        "status": "approved"
    }


class TestKillSwitch(unittest.TestCase):

    def setUp(self):
        self.gateway = ExternalGateway()
        self.approval_engine = PreflightApprovalEngine()
        self.queue = ExecutionQueue()

    def test_crash_after_approval_before_execution(self):
        """
        If operator crashes, NO side-effect should be recorded as complete.
        The approval must NOT be marked as executed so retry is safe.
        """
        intent = _make_intent("trace-ks-1")

        # 1. Create and approve
        request = self.approval_engine.create_or_get_request(intent)
        approval_id = request["request_id"]
        self.approval_engine.decide_request(approval_id, "approve")

        # 2. Simulate operator crash by patching route_execution to raise
        with patch('agents.operators.operator_gateway.route_execution', side_effect=RuntimeError("OPERATOR CRASH")):
            with self.assertRaises(GatewayError) as cm:
                self.gateway.validate_and_execute(intent, approval_id)

            self.assertEqual(cm.exception.reason, "operator_failure")

        # 3. CRITICAL: approval must NOT be in executed set
        self.assertFalse(
            self.gateway.is_approval_executed(approval_id),
            "Approval was marked executed despite operator crash!"
        )

        # 4. Verify the execution ledger recorded the failure
        # Find the failed entry
        failed_entries = [
            v for v in self.gateway._execution_ledger.values()
            if v["state"] == "failed"
        ]
        self.assertEqual(len(failed_entries), 1)
        self.assertEqual(failed_entries[0]["approval_id"], approval_id)

    def test_retry_after_crash_succeeds(self):
        """
        After a crash, re-executing the same approval should succeed
        because the approval was NOT consumed.
        """
        intent = _make_intent("trace-ks-2")

        # 1. Create and approve
        request = self.approval_engine.create_or_get_request(intent)
        approval_id = request["request_id"]
        self.approval_engine.decide_request(approval_id, "approve")

        # 2. First attempt: crash
        with patch('agents.operators.operator_gateway.route_execution', side_effect=RuntimeError("CRASH")):
            with self.assertRaises(GatewayError):
                self.gateway.validate_and_execute(intent, approval_id)

        # 3. Second attempt: should succeed (approval not consumed)
        outcome = self.gateway.validate_and_execute(intent, approval_id)
        self.assertEqual(outcome["status"], "success")

        # 4. But now it IS marked as executed
        self.assertTrue(self.gateway.is_approval_executed(approval_id))

    def test_queue_preserves_intent_on_failure(self):
        """
        If execution fails, the queue should re-queue the intent for retry.
        """
        intent = _make_intent("trace-ks-3")
        intent["status"] = "approved"

        # 1. Push to queue
        self.queue.push(intent)
        self.assertEqual(self.queue.depth, 1)

        # 2. Pop and start executing
        item = self.queue.pop()
        self.assertEqual(self.queue.depth, 0)
        self.assertEqual(self.queue.in_flight, 1)

        # 3. Mark as failed — should re-queue
        self.queue.mark_failed("trace-ks-3", "operator crashed")
        self.assertEqual(self.queue.in_flight, 0)
        self.assertEqual(self.queue.depth, 1, "Failed item should be re-queued for retry!")

        # 4. Pop retry item — it should have retry_of marker
        retry_item = self.queue.pop()
        self.assertIsNotNone(retry_item)
        self.assertEqual(retry_item.get("retry_of"), "trace-ks-3")


if __name__ == "__main__":
    unittest.main()
