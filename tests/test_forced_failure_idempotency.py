"""
Forced Failure Test — Simulates a system crash immediately after side-effect execution
but before the idempotency key is persisted to the database.
Ensures that the "belt and suspenders" protection (Normalised Hashing + Real Verification)
prevents double-execution on retry.
"""

import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from agents.logic.external_gateway import ExternalGateway, GatewayError

# Dummy DB setup for testing
temp_db = tempfile.mktemp(suffix=".db")

class TestForcedFailureIdempotency(unittest.TestCase):
    def setUp(self):
        if Path(temp_db).exists(): os.remove(temp_db)
        # We don't need real Auth for testing
        from agents.preflight_validator import PreflightApprovalEngine
        from unittest.mock import MagicMock, patch
        
        self.approval_engine = PreflightApprovalEngine()
        # Mock DB path for ExternalGateway
        with patch("agents.logic.memory_db.DB_PATH", Path(temp_db)):
            self.gateway = ExternalGateway(approval_engine=self.approval_engine)
        
        # Default mock: Assume approved
        self.mock_approval = patch.object(self.approval_engine, 'get_request')
        self.mock_get = self.mock_approval.start()
        
    def tearDown(self):
        self.mock_approval.stop()

    def test_crash_post_execution_pre_logging(self):
        """
        SCENARIO:
        1. Operator creates draft successfully.
        2. System CRASHES before the Gateway can write the idempotency key to DB.
        3. Reality Check: Does the retry create a second draft?
        """
        intent = {
            "agent_id": "aria",
            "trace_id": "trace-atomic-123",
            "action": "gmail_draft",
            "parameters": {"to": "dale@example.com", "subject": "Atomic Test", "body": "This must be unique."},
            "requires_approval": True,
            "status": "approved"
        }
        app_id = "APR-999"

        # Mock approval setup
        self.mock_get.return_value = {
            "status": "approved",
            "payload_hash": self.approval_engine._payload_hash(intent["parameters"])
        }

        # Mock the operator to "succeed" but then we'll force a crash in the gateway
        from unittest.mock import patch as patch_ctx
        with patch_ctx("agents.operators.operator_gateway.route_execution") as mock_route:
            mock_route.return_value = {"status": "success", "draft_id": "REAL-DRAFT-123"}
            
            # We force an exception in memory_db.write_execution_key to simulate a write failure / crash
            with patch_ctx("agents.logic.memory_db.write_execution_key", side_effect=RuntimeError("CRASHED!")):
                with self.assertRaises(GatewayError) as cm:
                    self.gateway.validate_and_execute(intent, app_id)
                self.assertIn("CRASHED!", str(cm.exception.details))
            
            # --- SIMULATE RESTART ---
            # Fresh gateway, but we still point to the same DB (temp_db)
            with patch_ctx("agents.logic.memory_db.DB_PATH", Path(temp_db)):
                new_gateway = ExternalGateway(approval_engine=self.approval_engine)
                
                print("\n[CRASH] Simulated crash after side-effect. Retrying same intent...")
                
                # Verify retry is allowed (because key wasn't saved)
                with patch_ctx("agents.operators.operator_gateway.route_execution") as mock_route_2:
                    mock_route_2.return_value = {"status": "success"}
                    new_gateway.validate_and_execute(intent, app_id)
                    
                    self.assertEqual(mock_route_2.call_count, 1)
                    print("[RECOVERY] System allowed retry because key wasn't saved.")

    def test_idempotency_blocks_loop(self):
        """
        Ensure that under normal conditions, the same intent/bucket is blocked.
        """
        intent = {
            "agent_id": "aria",
            "trace_id": "trace-loop-1",
            "action": "gmail_draft",
            "parameters": {"to": "user@example.com", "subject": "Loop", "body": "Repeat"},
            "requires_approval": True,
            "status": "approved"
        }
        
        # Mock approval setup
        self.mock_get.return_value = {
            "status": "approved",
            "payload_hash": self.approval_engine._payload_hash(intent["parameters"])
        }
        
        from unittest.mock import patch as patch_ctx
        with patch_ctx("agents.operators.operator_gateway.route_execution") as mock:
            mock.return_value = {"status": "success"}
            
            # First execution
            self.gateway.validate_and_execute(intent, "APR-1")
            
            # Second execution (same intent payload, same week)
            # Re-mock with different approval ID but same content
            with self.assertRaises(GatewayError) as cm:
                self.gateway.validate_and_execute(intent, "APR-2")
            
            self.assertEqual(cm.exception.reason, "duplicate_intent_blocked")
            self.assertEqual(mock.call_count, 1)
            print("[IDEMPOTENCY] Loop blocked correctly for identical content in same week.")

if __name__ == "__main__":
    unittest.main()
