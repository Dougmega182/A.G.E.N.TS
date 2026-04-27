"""
Verification Test 2: Intent Immutability (Hash-based)
Goal: Proves that altering the payload after approval triggers a hash mismatch and blocks execution.
"""

import sys
import os
import unittest
from pathlib import Path

# PRE-IMPORT ENV SETUP
import tempfile
os.environ["AGENTS_DB_PATH"] = tempfile.mktemp(suffix=".db")

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.logic.external_gateway import ExternalGateway, GatewayError
from agents.preflight_validator import PreflightApprovalEngine

class TestIntentImmutabilityHash(unittest.TestCase):

    def setUp(self):
        self.gateway = ExternalGateway()
        self.approval_engine = PreflightApprovalEngine()

    def test_payload_tampering_blocked(self):
        """Gateway must detect if the payload has been changed since human approval."""
        intent = {
            "action": "gmail_draft",
            "agent_id": "jenny",
            "parameters": {
                "to": "user@example.com", 
                "subject": "Original Subject", 
                "body": "Original Body"
            },
            "trace_id": "trace-immutability-1",
            "requires_approval": True,
            "status": "approved"
        }
        
        # 1. Create and APPROVE the request
        request = self.approval_engine.create_or_get_request(intent)
        approval_id = request["request_id"]
        self.approval_engine.decide_request(approval_id, "approve")

        # 2. TAMPER with the intent before execution
        tampered_intent = intent.copy()
        tampered_intent["parameters"] = intent["parameters"].copy()
        tampered_intent["parameters"]["subject"] = "TAMPERED Subject"

        # 3. Try to execute
        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(tampered_intent, approval_id)
        
        self.assertEqual(cm.exception.reason, "payload_integrity_violation")
        self.assertNotEqual(cm.exception.details["actual"], request.get("payload_hash"))

    def test_parameters_ordering_immutability(self):
        """Gateway should be resilient to dict key ordering as long as values are identical."""
        intent = {
            "action": "gmail_draft",
            "agent_id": "jenny",
            "parameters": {
                "to": "user@example.com", 
                "subject": "Stable", 
                "body": "Order doesn't matter"
            },
            "trace_id": "trace-immutability-2",
            "requires_approval": True,
            "status": "approved"
        }
        
        # 1. Create and APPROVE the request
        request = self.approval_engine.create_or_get_request(intent)
        approval_id = request["request_id"]
        self.approval_engine.decide_request(approval_id, "approve")

        # 2. Re-order keys but keep content same
        # Python 3.7+ dicts preserve order, but we reconstruct to ensure a potential difference
        reordered_params = {
            "body": "Order doesn't matter",
            "subject": "Stable",
            "to": "user@example.com"
        }
        tampered_intent = intent.copy()
        tampered_intent["parameters"] = reordered_params

        # 3. Try to execute - SHOULD PASS because Firewall._payload_hash uses sort_keys=True
        try:
            outcome = self.gateway.validate_and_execute(tampered_intent, approval_id)
            self.assertEqual(outcome["status"], "success")
        except GatewayError as e:
            self.fail(f"Gateway failed on reordered keys: {e.reason}")

if __name__ == "__main__":
    unittest.main()
