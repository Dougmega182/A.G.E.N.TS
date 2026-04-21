"""
Stress Test 6: Out-of-Order Execution Test
Goal: Ensure sequence integrity — dependent intents cannot execute before their prerequisites.
"""

import sys
import os
import unittest
from pathlib import Path

import tempfile
os.environ["AGENTS_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_PREFLIGHT_STORE"] = tempfile.mktemp(suffix=".json")

sys.path.append(str(Path(__file__).parent.parent))

from agents.logic.execution_queue import ExecutionQueue


class TestOutOfOrderExecution(unittest.TestCase):

    def setUp(self):
        self.queue = ExecutionQueue()

    def test_fifo_ordering_enforced(self):
        """Queue must never allow out-of-order pops."""
        # Push 3 dependent intents in order
        for i in range(3):
            self.queue.push({
                "action": "gmail_draft", "agent_id": "jenny",
                "parameters": {"to": "a@b.com", "subject": f"Step {i}", "body": "Y"},
                "trace_id": f"trace-order-{i}",
                "requires_approval": True, "status": "approved"
            })

        # Pop must return in order
        item0 = self.queue.pop()
        self.assertEqual(item0["intent"]["trace_id"], "trace-order-0")

        item1 = self.queue.pop()
        self.assertEqual(item1["intent"]["trace_id"], "trace-order-1")

        item2 = self.queue.pop()
        self.assertEqual(item2["intent"]["trace_id"], "trace-order-2")

    def test_executing_item_blocks_re_pop(self):
        """An item being executed should not appear in the queue again."""
        self.queue.push({
            "action": "gmail_draft", "agent_id": "jenny",
            "parameters": {"to": "a@b.com", "subject": "X", "body": "Y"},
            "trace_id": "trace-order-block",
            "requires_approval": True, "status": "approved"
        })

        item = self.queue.pop()
        self.assertEqual(self.queue.depth, 0)
        self.assertEqual(self.queue.in_flight, 1)

        # Pop again should return None, not the same item
        self.assertIsNone(self.queue.pop())

    def test_completed_item_not_retryable(self):
        """Once marked executed, the item should not be in the queue or in_flight."""
        self.queue.push({
            "action": "gmail_draft", "agent_id": "jenny",
            "parameters": {"to": "a@b.com", "subject": "X", "body": "Y"},
            "trace_id": "trace-order-done",
            "requires_approval": True, "status": "approved"
        })

        self.queue.pop()
        self.queue.mark_executed("trace-order-done", {"status": "success"})

        self.assertEqual(self.queue.depth, 0)
        self.assertEqual(self.queue.in_flight, 0)
        self.assertEqual(len(self.queue._history), 1)
        self.assertEqual(self.queue._history[0]["status"], "executed")

    def test_peek_does_not_consume(self):
        """Peek must show the next item without removing it."""
        self.queue.push({
            "action": "gmail_draft", "agent_id": "jenny",
            "parameters": {"to": "a@b.com", "subject": "Peek", "body": "Y"},
            "trace_id": "trace-order-peek",
            "requires_approval": True, "status": "approved"
        })

        peeked = self.queue.peek()
        self.assertIsNotNone(peeked)
        self.assertEqual(self.queue.depth, 1, "Peek consumed the item!")

        # Pop should still return the same item
        popped = self.queue.pop()
        self.assertEqual(popped["intent"]["trace_id"], "trace-order-peek")


if __name__ == "__main__":
    unittest.main()
