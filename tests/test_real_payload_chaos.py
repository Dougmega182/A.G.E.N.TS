"""
Chaos Harness — Stress tests the A.G.E.N.T.S. External Gateway and Operators
against malformed, malicious, and "messy" real-world inputs.
"""

import unittest
import json
from agents.logic.external_gateway import ExternalGateway, GatewayError
from agents.operators.gmail_operator import OperatorValidationError

import os
import tempfile
from pathlib import Path

# Dummy DB setup for testing
temp_db = tempfile.mktemp(suffix=".db")

class TestRealPayloadChaos(unittest.TestCase):
    def setUp(self):
        if Path(temp_db).exists(): os.remove(temp_db)
        
        # We don't need real Auth for chaos testing since validation happens before side-effects
        from agents.preflight_validator import PreflightApprovalEngine
        from unittest.mock import MagicMock, patch
        
        from agents.logic import memory_db
        # Isolate DB for this test
        patcher_db = patch("agents.logic.memory_db.DB_PATH", Path(temp_db))
        patcher_db.start()
        self.addCleanup(patcher_db.stop)

        self.approval_engine = PreflightApprovalEngine()
        self.gateway = ExternalGateway(approval_engine=self.approval_engine)
        
        # Default mock: Assume approved with matching hash
        self.mock_approval = patch.object(self.approval_engine, 'get_request')
        self.mock_get = self.mock_approval.start()
        
    def tearDown(self):
        self.mock_approval.stop()

    def test_null_byte_payload(self):
        """Simulate a null-byte injection which often crashes string processors."""
        intent = {
            "agent_id": "aria",
            "trace_id": "trace-chaos-1",
            "action": "gmail_draft",
            "parameters": {"to": "user@example.com", "subject": "Null\x00Byte", "body": "Exploit"},
            "requires_approval": True,
            "status": "approved"
        }
        # Mock approval found
        self.mock_get.return_value = {
            "status": "approved",
            "payload_hash": self.approval_engine._payload_hash(intent["parameters"])
        }
        
        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, "APR-123")
        
        # Should be caught by operator validation AFTER passing gateway
        self.assertEqual(cm.exception.reason, "operator_failure")
        self.assertIn("encoding_violation", str(cm.exception.details))
        print("[CHAOS] Null-byte injection correctly blocked.")

    def test_excessive_payload_size(self):
        """Simulate a massive multi-megabyte body."""
        massive_body = "A" * 1000000 # 1MB string
        intent = {
            "agent_id": "aria",
            "trace_id": "trace-chaos-2",
            "action": "gmail_draft",
            "parameters": {"to": "user@example.com", "subject": "Massive", "body": massive_body},
            "requires_approval": True,
            "status": "approved"
        }
        # Mock approval
        self.mock_get.return_value = {
            "status": "approved",
            "payload_hash": self.approval_engine._payload_hash(intent["parameters"])
        }
        
        try:
            from unittest.mock import patch
            with patch("agents.operators.operator_gateway.route_execution") as mock_route:
                mock_route.return_value = {"status": "success"}
                self.gateway.validate_and_execute(intent, "APR-MASSIVE")
                print("[CHAOS] Large payload (1MB) handled without crashing.")
        except Exception as e:
            self.fail(f"Large payload caused crash: {e}")

    def test_garbage_parameters(self):
        """Simulate missing required fields and wrong types."""
        bad_intents = [
            {"to": None, "subject": 123, "body": {}}, # Wrong types
            {"to": "only-to"}, # Missing subject/body
        ]

        for i, params in enumerate(bad_intents):
            intent = {
                "agent_id": "aria",
                "trace_id": f"trace-chaos-trash-{i}",
                "action": "gmail_draft",
                "parameters": params,
                "requires_approval": True,
                "status": "approved"
            }
            # Mock approval found
            self.mock_get.return_value = {
                "status": "approved",
                "payload_hash": self.approval_engine._payload_hash(intent["parameters"])
            }
            
            with self.assertRaises(GatewayError) as cm:
                self.gateway.validate_and_execute(intent, f"APR-BAD-{i}")
            
            self.assertTrue(cm.exception.reason in ["invalid_intent_schema", "operator_failure"])
            print(f"[CHAOS] Garbage input {i} correctly rejected.")

    def test_emoji_and_non_ascii(self):
        """Ensure emojis and UTF-8 characters are handled safely in normalization."""
        intent = {
            "agent_id": "aria",
            "trace_id": "trace-emoji",
            "action": "gmail_send",
            "parameters": {
                "to": "dale@example.com", 
                "subject": "🔥🔥🔥 URGENT 🔥🔥🔥", 
                "body": "こんにちは 世界! 🚀"
            },
            "requires_approval": True,
            "status": "approved"
        }
        # Mock approval
        self.mock_get.return_value = {
            "status": "approved",
            "payload_hash": self.approval_engine._payload_hash(intent["parameters"])
        }
        
        from unittest.mock import patch
        with patch("agents.operators.operator_gateway.route_execution") as mock_route:
            mock_route.return_value = {"status": "success"}
            res = self.gateway.validate_and_execute(intent, "APR-EMOJI")
            self.assertEqual(res["status"], "success")
            print("[CHAOS] Emoji and UTF-8 handled successfully.")

if __name__ == "__main__":
    unittest.main()
