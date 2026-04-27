"""
Stress Test 4: Rate Limit / Flood Test
Goal: Prove the queue buffers safely under flood, no intents dropped, rate limit enforced.
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
from agents.logic.execution_queue import ExecutionQueue
from agents.preflight_validator import PreflightApprovalEngine


class TestRateLimitFlood(unittest.TestCase):

    def setUp(self):
        self.queue = ExecutionQueue()

    def test_queue_buffers_50_intents_no_drops(self):
        """50 intents pushed rapidly — none should be dropped."""
        for i in range(50):
            intent = {
                "action": "gmail_draft", "agent_id": "jenny",
                "parameters": {"to": f"user{i}@test.com", "subject": f"Flood {i}", "body": "Test"},
                "trace_id": f"trace-flood-{i}",
                "requires_approval": True, "status": "approved"
            }
            self.queue.push(intent)

        self.assertEqual(self.queue.depth, 50, "Queue dropped intents!")

        # Drain and verify all 50 are intact
        items = self.queue.drain()
        self.assertEqual(len(items), 50)

        # Verify ordering preserved
        for i, item in enumerate(items):
            self.assertEqual(item["intent"]["trace_id"], f"trace-flood-{i}")

    def test_queue_rejects_unapproved_intents(self):
        """Queue must reject intents that aren't approved."""
        bad_intent = {
            "action": "gmail_draft", "agent_id": "jenny",
            "parameters": {"to": "a@b.com", "subject": "X", "body": "Y"},
            "trace_id": "trace-flood-bad",
            "requires_approval": True, "status": "pending"  # NOT approved
        }
        with self.assertRaises(ValueError):
            self.queue.push(bad_intent)

        self.assertEqual(self.queue.depth, 0)

    def test_gateway_rate_limit_enforced(self):
        """Gateway must block execution after exceeding rate limit."""
        # Create a gateway with a very low limit (3 per minute)
        gateway = ExternalGateway(max_executions_per_minute=3)
        approval_engine = PreflightApprovalEngine()

        executed_count = 0
        blocked = False

        for i in range(5):
            intent = {
                "action": "gmail_draft", "agent_id": "jenny",
                "parameters": {"to": f"rate{i}@test.com", "subject": f"Rate {i}", "body": "Test"},
                "trace_id": f"trace-rate-{i}",
                "requires_approval": True, "status": "approved"
            }
            req = approval_engine.create_or_get_request(intent)
            approval_engine.decide_request(req["request_id"], "approve")

            try:
                gateway.validate_and_execute(intent, req["request_id"])
                executed_count += 1
            except GatewayError as e:
                if e.reason == "rate_limit_exceeded":
                    blocked = True
                    break
                raise

        self.assertTrue(blocked, "Rate limit was never triggered!")
        self.assertEqual(executed_count, 3, f"Expected 3 executions before limit, got {executed_count}")

    def test_queue_pop_order_fifo(self):
        """Queue must process in FIFO order."""
        for i in range(5):
            self.queue.push({
                "action": "gmail_draft", "agent_id": "jenny",
                "parameters": {"to": "a@b.com", "subject": "X", "body": "Y"},
                "trace_id": f"trace-fifo-{i}",
                "requires_approval": True, "status": "approved"
            })

        for i in range(5):
            item = self.queue.pop()
            self.assertEqual(item["intent"]["trace_id"], f"trace-fifo-{i}")


if __name__ == "__main__":
    unittest.main()
