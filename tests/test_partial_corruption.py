"""
Stress Test 3: Partial Corruption (Data Integrity)
Goal: Catch real-world payload corruption at both gateway AND operator levels.
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
from agents.firewall import PreflightApprovalEngine
from agents.operators.gmail_operator import _validate_parameters, OperatorValidationError


class TestPartialCorruption(unittest.TestCase):

    def setUp(self):
        self.gateway = ExternalGateway()
        self.approval_engine = PreflightApprovalEngine()

    # --- Operator-level validation tests ---

    def test_missing_field_rejected_at_operator(self):
        """Operator must reject payload with missing required fields."""
        with self.assertRaises(OperatorValidationError) as cm:
            _validate_parameters({"to": "a@b.com", "subject": "Test"})  # missing 'body'
        self.assertEqual(cm.exception.reason, "missing_required_fields")
        self.assertIn("body", cm.exception.details["missing"])

    def test_empty_field_rejected_at_operator(self):
        """Operator must reject payload with empty string values."""
        with self.assertRaises(OperatorValidationError) as cm:
            _validate_parameters({"to": "a@b.com", "subject": "  ", "body": "Hello"})
        self.assertEqual(cm.exception.reason, "empty_field")

    def test_null_byte_injection_rejected(self):
        """Operator must reject payload with null bytes (encoding attack)."""
        with self.assertRaises(OperatorValidationError) as cm:
            _validate_parameters({"to": "a@b.com", "subject": "Normal", "body": "Hello\x00World"})
        self.assertEqual(cm.exception.reason, "encoding_violation")

    def test_unexpected_fields_rejected(self):
        """Operator must reject payload with unexpected/injected fields."""
        with self.assertRaises(OperatorValidationError) as cm:
            _validate_parameters({
                "to": "a@b.com", "subject": "Test", "body": "OK",
                "execute_command": "rm -rf /"  # injected field
            })
        self.assertEqual(cm.exception.reason, "unexpected_fields")

    def test_wrong_type_rejected_at_operator(self):
        """Operator must reject payload where fields are wrong type."""
        with self.assertRaises(OperatorValidationError) as cm:
            _validate_parameters({"to": 12345, "subject": "Test", "body": "OK"})
        self.assertEqual(cm.exception.reason, "invalid_field_type")

    def test_non_dict_rejected_at_operator(self):
        """Operator must reject non-dict parameters."""
        with self.assertRaises(OperatorValidationError) as cm:
            _validate_parameters("not a dict")
        self.assertEqual(cm.exception.reason, "invalid_parameters_type")

    # --- Gateway-level corruption tests ---

    def test_corrupted_intent_schema_blocked(self):
        """Gateway must block intents that fail schema validation."""
        bad_intent = {
            "action": "gmail_draft",
            # missing agent_id, parameters, trace_id, etc.
        }
        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(bad_intent, "APR-FAKE123")
        self.assertEqual(cm.exception.reason, "invalid_intent_schema")

    def test_corrupted_parameters_blocked_end_to_end(self):
        """
        Even if gateway passes validation, operator catches corruption.
        Simulates a subtle corruption: valid schema but bad field content.
        """
        intent = {
            "action": "gmail_draft",
            "agent_id": "jenny",
            "parameters": {"to": "a@b.com", "subject": "Test", "body": "OK", "execute_command": "INJECTED"},
            "trace_id": "trace-corrupt-e2e",
            "requires_approval": True,
            "status": "approved"
        }

        req = self.approval_engine.create_or_get_request(intent)
        self.approval_engine.decide_request(req["request_id"], "approve")

        # Operator-level validation should catch the unexpected field
        with self.assertRaises(GatewayError) as cm:
            self.gateway.validate_and_execute(intent, req["request_id"])
        self.assertEqual(cm.exception.reason, "operator_failure")
        self.assertIn("unexpected_fields", cm.exception.details["error"])


if __name__ == "__main__":
    unittest.main()
