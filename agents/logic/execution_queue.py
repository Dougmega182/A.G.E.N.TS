"""
Execution Queue — In-Memory buffer with failure tracking and crash recovery.
Phase 3A Hardened.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class ExecutionQueue:
    """
    Hardened queue with:
    - Failure tracking (mark_failed for crash recovery)
    - Depth query (for rate/flood protection)
    - History of executed + failed items (audit trail)
    """

    def __init__(self):
        self._queue: List[Dict[str, Any]] = []
        self._executing: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []  # completed + failed items

    @property
    def depth(self) -> int:
        """Current number of pending items in the queue."""
        return len(self._queue)

    @property
    def in_flight(self) -> int:
        """Number of items currently being executed."""
        return len(self._executing)

    def push(self, intent: Dict[str, Any]):
        """Push an approved intent into the queue."""
        if intent.get("status") != "approved":
            raise ValueError(f"Intent {intent.get('trace_id')} is not approved.")

        item = {
            "intent": intent,
            "queued_at": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        self._queue.append(item)

    def peek(self) -> Optional[Dict[str, Any]]:
        """Look at the next item without removing it."""
        if not self._queue:
            return None
        return self._queue[0]

    def pop(self) -> Optional[Dict[str, Any]]:
        """Get the next pending item, moving it to executing state."""
        if not self._queue:
            return None

        item = self._queue.pop(0)
        item["status"] = "executing"
        item["started_at"] = datetime.utcnow().isoformat()

        intent_id = item["intent"].get("trace_id")
        self._executing[intent_id] = item
        return item

    def mark_executed(self, intent_id: str, outcome: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Mark as successfully executed."""
        if intent_id in self._executing:
            item = self._executing.pop(intent_id)
            item["status"] = "executed"
            item["finished_at"] = datetime.utcnow().isoformat()
            item["outcome"] = outcome
            self._history.append(item)
            return item
        return None

    def mark_failed(self, intent_id: str, error: str) -> Optional[Dict[str, Any]]:
        """Mark as failed. Item moves to history but stays retryable."""
        if intent_id in self._executing:
            item = self._executing.pop(intent_id)
            item["status"] = "failed"
            item["finished_at"] = datetime.utcnow().isoformat()
            item["error"] = error
            self._history.append(item)
            # Re-queue for retry
            retry_item = {
                "intent": item["intent"],
                "queued_at": datetime.utcnow().isoformat(),
                "status": "pending",
                "retry_of": intent_id
            }
            self._queue.append(retry_item)
            return item
        return None

    def drain(self) -> List[Dict[str, Any]]:
        """Get all pending items (for inspection/testing). Non-destructive."""
        return list(self._queue)


# Singleton instance for Phase 3A
queue = ExecutionQueue()
