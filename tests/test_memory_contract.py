"""
Test 1: Memory Contract Integrity Test (CRITICAL)
Goal: Ensure only allowed systems can write/read memory.
"""

import sys
import os
import unittest
from pathlib import Path

import tempfile
import time

# PRE-IMPORT ENV SETUP
TEST_DB_PATH = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_DB_PATH"] = TEST_DB_PATH
os.environ["REDIS_PREFIX"] = f"test_{int(time.time())}:"

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.logic import memory_db
from agents.logic import memory_cache
from agents.logic.memory_contract import MemoryBoundaryViolation, MemoryDomain

# Setup test environment
class TestMemoryContract(unittest.TestCase):

    def setUp(self):
        # The env var is already set, but we store the path for cleanup
        self.db_path = os.environ["AGENTS_DB_PATH"]

    def tearDown(self):
        # Attempt cleanup
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass # Ignore lock on Windows during fast cleanup

    def test_unauthorized_write_blocked(self):
        """Verifies that agents cannot write directly to SQLite."""
        test_event = {"event_id": "test", "metadata": {}}
        
        # Aria is NOT a permitted writer for decisions
        with self.assertRaises(MemoryBoundaryViolation) as cm:
            memory_db.write_decision("aria", test_event)
        
        self.assertIn("BOUNDARY VIOLATION", str(cm.exception))
        self.assertIn("aria attempted write on decisions", str(cm.exception))

    def test_unauthorized_read_blocked(self):
        """Verifies that unauthorized readers are blocked."""
        # 'tucker' is not a permitted reader for OWEN_INSIGHTS
        with self.assertRaises(MemoryBoundaryViolation) as cm:
            memory_db.read_owen_insights("tucker")
        
        self.assertIn("BOUNDARY VIOLATION", str(cm.exception))
        self.assertIn("tucker attempted read on owen_insights", str(cm.exception))

    def test_authorized_write_pass(self):
        """Verifies that only orchestrator/owen_engine/event_bus can write."""
        test_event = {
            "event_id": "trace-1", 
            "trace_id": "trace-1", 
            "scenario": "variation", 
            "timestamp": "now",
            "metadata": {"final_decision": "APPROVE"}
        }
        
        # Orchestrator should pass
        try:
            memory_db.write_decision("orchestrator", test_event)
        except MemoryBoundaryViolation:
            self.fail("Orchestrator should be allowed to write decisions")

    def test_cache_integrity(self):
        """Verifies cache write boundaries."""
        with self.assertRaises(MemoryBoundaryViolation):
             memory_cache.cache_reasoning_context("nadia", "trace-1", {})

if __name__ == "__main__":
    unittest.main()
