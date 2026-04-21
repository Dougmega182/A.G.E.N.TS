"""
Verification Test 1: Gmail Gateway Safety
Goal: Proves nothing executes without approval and 'send' is impossible in Phase 3A.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# PRE-IMPORT ENV SETUP
import tempfile
os.environ["AGENTS_DB_PATH"] = tempfile.mktemp(suffix=".db")

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.logic.external_gateway import ExternalGateway, GatewayError
from agents.firewall import PreflightApprovalEngine

class TestGmailGatewaySafety(unittest.TestCase):

    def setUp(self):
        self.gateway = ExternalGateway()
        self.approval_engine = PreflightApprovalEngine()

    def test_unapproved_intent_blocked(self):
        """Gateway must block intents that haven't been approved in the firewall."""
        intent = {
            "action": "gmail_draft",
            "agent_id": "jenny",
            "parameters": {"to": "user@example.com", "subject": "Test", "body": "Hello"},
            "trace_id": "trace-safety-1",
            "requires_approval": True,
            "status": "pending"
        }
        
        # 1. Create a request but keep it PENDING
        request = self.approval_engine.create_or_get_request(intent)
        approval_id = request["request_id"]

        # 2. Try to execute
        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, approval_id)
        
        self.assertEqual(cm.exception.reason, "intent_not_approved")

    def test_unsupported_operator_blocked(self):
        """Gateway must block actions not supported in Phase 3A (like gmail_send)."""
        intent = {
            "action": "gmail_send", # NOT supported in Phase 3A
            "agent_id": "jenny",
            "parameters": {"to": "user@example.com", "subject": "Test", "body": "Hello"},
            "trace_id": "trace-safety-2",
            "requires_approval": True,
            "status": "approved"
        }
        
        # 1. Create and APPROVE the request
        request = self.approval_engine.create_or_get_request(intent)
        approval_id = request["request_id"]
        self.approval_engine.decide_request(approval_id, "approve")

        # 2. Try to execute
        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, approval_id)
        
        # In this case, the gateway routes to operator_gateway which raises ValueError
        self.assertEqual(cm.exception.reason, "operator_failure")
        self.assertIn("Unsupported action: gmail_send", cm.exception.details["error"])

    def test_successful_approved_draft(self):
        """Gateway must successfully execute an approved gmail_draft."""
        intent = {
            "action": "gmail_draft",
            "agent_id": "jenny",
            "parameters": {"to": "user@example.com", "subject": "Verified", "body": "Logic Core is online."},
            "trace_id": "trace-safety-3",
            "requires_approval": True,
            "status": "approved"
        }
        
        # 1. Create and APPROVE the request
        request = self.approval_engine.create_or_get_request(intent)
        approval_id = request["request_id"]
        self.approval_engine.decide_request(approval_id, "approve")

        # 2. Execute
        outcome = self.gateway.validate_and_execute(intent, approval_id)
        
        self.assertEqual(outcome["status"], "success")
        self.assertIn("DRAFT-", outcome["draft_id"])

if __name__ == "__main__":
    unittest.main()
