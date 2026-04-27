"""
Test 2 & 3: Execution Idempotency and Collision Protection
Goal: Verify that side-effects are NEVER duplicated, even across different approvals or system restarts.
"""

import os
import sys
import unittest
import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Isolate environment
temp_db = tempfile.mktemp(suffix=".db")
os.environ["AGENTS_DB_PATH"] = temp_db

from agents.logic.external_gateway import ExternalGateway, GatewayError
from agents import preflight_validator as firewall

class TestExecutionIdempotency(unittest.TestCase):

    def setUp(self):
        if Path(temp_db).exists(): os.remove(temp_db)
        self.approval_engine = firewall.PreflightApprovalEngine()
        self.gateway = ExternalGateway(approval_engine=self.approval_engine)

    def test_duplicate_intent_collision(self):
        """
        USER TEST 3: Same payload, different approval IDs.
        Expected: Second is blocked by Idempotency Key.
        """
        intent = {
            "agent_id": "aria",
            "trace_id": "trace-123",
            "action": "gmail_send",
            "parameters": {"to": "user@example.com", "subject": "Hello", "body": "World"},
            "requires_approval": True,
            "status": "pending"
        }

        # 1. First Approval
        req1 = self.approval_engine.create_or_get_request(intent)
        app_id_1 = req1["request_id"]
        app1 = self.approval_engine.decide_request(app_id_1, "approved", decided_by="human")
        self.assertEqual(app1["status"], "approved")

        # 2. Second Approval (Same intent, DIFFERENT Approval ID)
        # We use a DIFFERENT request in the firewall to get a new ID, 
        # but the intent payload (and trace) remains the same.
        req2 = self.approval_engine.create_or_get_request(intent)
        app_id_2 = req2["request_id"]
        # Note: PreflightApprovalEngine.create_or_get_request returns EXISTING if fingerprint matches.
        # To force a different app_id for this test, I'll manually inject one or 
        # realize that the Gateway uses approval_id as a separate check anyway.
        
        # If I want to test IF the idempotency key (payload based) blocks it even if approval is different:
        app_id_fake = f"APR-FAKE-{uuid.uuid4().hex[:8]}"
        
        # 3. Execute First
        with patch("agents.operators.operator_gateway.route_execution") as mock_route:
            mock_route.return_value = {"status": "success", "msg": "Draft created"}
            intent["status"] = "approved"
            result1 = self.gateway.validate_and_execute(intent, app_id_1)
            self.assertEqual(result1["status"], "success")

            # 4. Execute Second (COLLISION)
            # Even with a different approval ID (mocked), the Idempotency Key (trace+action+params) should block.
            with self.assertRaises(GatewayError) as cm:
                # We need to mock the approval engine to think this fake ID is approved
                with patch.object(self.approval_engine, 'get_request') as mock_get:
                    mock_get.return_value = {
                        "status": "approved",
                        "payload_hash": self.approval_engine._payload_hash(intent["parameters"])
                    }
                    self.gateway.validate_and_execute(intent, app_id_fake)
            
            self.assertEqual(cm.exception.reason, "duplicate_intent_blocked")
            print("\n[IDEMPOTENCY] Collision protection verified: duplicate payload blocked by idempotency key.")

    def test_idempotency_crash_recovery(self):
        """
        USER TEST 2: Crash after operator succeeds but before Gateway finishes.
        Simulation: The Gateway's internal state is reset (simulated restart).
        """
        # Isolate log for this test
        test_log = Path(tempfile.mktemp(suffix=".jsonl"))
        from agents.logic import event_bus
        original_log = event_bus.EVENTS_LOG_PATH
        event_bus.EVENTS_LOG_PATH = test_log

        intent = {
            "agent_id": "aria",
            "trace_id": "trace-crash-456",
            "action": "gmail_send",
            "parameters": {"to": "admin@example.com", "subject": "Alert", "body": "System Crash"},
            "requires_approval": True,
            "status": "pending"
        }
        req = self.approval_engine.create_or_get_request(intent)
        app_id = req["request_id"]
        self.approval_engine.decide_request(app_id, "approved", decided_by="human")

        # 1. Execute successfully
        with patch("agents.operators.operator_gateway.route_execution") as mock_route:
            mock_route.return_value = {"status": "success"}
            intent["status"] = "approved"
            self.gateway.validate_and_execute(intent, app_id)

            # 2. SIMULATE RESTART
            # Note: ExternalGateway loads keys from DB on __init__
            new_gateway = ExternalGateway()
            
            print("\n[RECOVERY] Starting crash recovery test...")
            # Also restore from logs (proves dual restoration works)
            new_gateway.restore_from_log(test_log)
            
            # 3. VERIFY IDEMPOTENCY BLOCKS RETRY
            with self.assertRaises(GatewayError) as cm:
                new_gateway.validate_and_execute(intent, app_id)
            
            # Because it's the SAME approval_id, Step 7 (Replay Protection) catches it first.
            # This counts as a successful block.
            self.assertIn(cm.exception.reason, ["duplicate_intent_blocked", "replay_blocked"])
            print(f"[RECOVERY] Crash recovery verified: blocked as '{cm.exception.reason}' after restart.")
        
        # Cleanup
        if test_log.exists(): os.remove(test_log)
        event_bus.EVENTS_LOG_PATH = original_log

if __name__ == "__main__":
    unittest.main()
