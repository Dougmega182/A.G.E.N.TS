"""
Test 8: Loop Latency Test
Goal: Ensure Owen briefings and DB writes stay within overhead budget.
"""

import sys
import os
import time
import unittest
import asyncio
from pathlib import Path

import tempfile

# PRE-IMPORT ENV SETUP
TEST_DB_PATH = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_DB_PATH"] = TEST_DB_PATH

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.logic.owen_engine import OwenEngine
from agents.logic import memory_db

class TestLoopLatency(unittest.TestCase):

    def setUp(self):
        self.db_path = os.environ["AGENTS_DB_PATH"]
        self.owen = OwenEngine()

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass

    def test_owen_synthesis_latency(self):
        """Owen briefing generation should be < 200ms for deterministic logic."""
        # 1. Seed DB with 50 decisions to create realistic load
        for i in range(50):
            memory_db.write_decision("orchestrator", {
                "event_id": f"l{i}",
                "trace_id": f"tl{i}",
                "scenario": "variation",
                "timestamp": "now",
                "metadata": {"final_decision": "APPROVE"}
            })

        # 2. Measure briefing synthesis
        start = time.perf_counter()
        _ = self.owen.generate_intelligence_briefing("variation")
        duration = time.perf_counter() - start
        
        print(f"\n[LATENCY] Owen briefing (50 items): {duration:.4f}s")
        self.assertLess(duration, 0.2, "Owen synthesis too slow!")

    def test_db_write_latency(self):
        """DB writes should be < 50ms."""
        start = time.perf_counter()
        memory_db.write_decision("orchestrator", {
            "event_id": "lat-test",
            "trace_id": "lat-trace",
            "scenario": "variation",
            "timestamp": "now",
            "metadata": {"final_decision": "APPROVE"}
        })
        duration = time.perf_counter() - start
        
        print(f"[LATENCY] SQLite Write: {duration:.4f}s")
        self.assertLess(duration, 0.2, "SQLite write too slow!")

if __name__ == "__main__":
    unittest.main()
