"""
Decision Finalizer Verification — Phase 2.3: Canonical Decision Layer

Tests:
    1. Clean pass-through (no overrides)
    2. Contract failure → forced ESCALATE
    3. CRITICAL governance override → APPROVE becomes ESCALATE
    4. Safety gate override → APPROVE becomes ESCALATE
    5. Stacked overrides (CRITICAL + safety)
    6. Conflict detection (WALL-E REJECT + Aria APPROVE)
    7. Reasoning quality warnings
    8. DECISION_FINALIZED_V1 event payload structure
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.logic.decision_finalizer import finalize_decision, FinalizedDecision
from agents.logic.governance_engine import evaluate_governance


def _make_decision(decision="APPROVE", justification="Test justification with governance flag and past history reference"):
    return {
        "decision": decision,
        "justification": justification,
        "conditions": ["condition_1"],
        "impact": {"cost": 5000, "days": 2, "risk_delta": 0.05}
    }


def test_clean_passthrough():
    """No overrides, no warnings → decision passes through unchanged."""
    print("\n--- TEST 1: Clean Pass-Through ---")

    flags = evaluate_governance("variation", cost=5000, days=2, risk_score=0.3)
    result = finalize_decision(
        decision_data=_make_decision("APPROVE"),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=flags,
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="test-001",
        scenario_type="variation",
    )

    assert result.final_decision == "APPROVE"
    assert result.original_decision == "APPROVE"
    assert result.was_overridden is False
    assert result.was_system_forced is False
    assert len(result.override_chain) == 0
    print("  OK Clean pass-through: APPROVE unchanged")
    print("  OK All pass-through tests PASSED")


def test_contract_failure():
    """Invalid contract → forced ESCALATE."""
    print("\n--- TEST 2: Contract Failure Override ---")

    flags = evaluate_governance("variation", cost=5000, days=2, risk_score=0.3)
    result = finalize_decision(
        decision_data={},
        decision_valid=False,
        decision_error_reason="invalid_json",
        risk_score=0.3,
        governance_flags=flags,
        critique_data=None,
        memory_count=0,
        trace_id="test-002",
        scenario_type="variation",
    )

    assert result.final_decision == "ESCALATE"
    assert result.was_system_forced is True
    assert "CONTRACT_VALIDATION_FAILURE" in result.override_chain
    assert result.primary_override_reason == "contract_failure"
    print("  OK Contract failure → ESCALATE (forced)")
    print("  OK All contract failure tests PASSED")


def test_governance_critical_override():
    """CRITICAL governance flag + APPROVE → forced ESCALATE."""
    print("\n--- TEST 3: Governance CRITICAL Override ---")

    flags = evaluate_governance("variation", cost=60000, days=2, risk_score=0.3)
    result = finalize_decision(
        decision_data=_make_decision("APPROVE"),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=flags,
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="test-003",
        scenario_type="variation",
    )

    assert result.final_decision == "ESCALATE"
    assert result.original_decision == "APPROVE"
    assert result.was_overridden is True
    assert "GOVERNANCE_CRITICAL_OVERRIDE" in result.override_chain
    assert result.has_critical_governance is True
    print(f"  OK Governance CRITICAL override: APPROVE -> ESCALATE")
    print(f"  OK Override chain: {result.override_chain}")
    print("  OK All governance override tests PASSED")


def test_safety_gate_override():
    """Risk >= 0.85 + APPROVE → forced ESCALATE."""
    print("\n--- TEST 4: Safety Gate Override ---")

    flags = evaluate_governance("variation", cost=5000, days=2, risk_score=0.9)
    result = finalize_decision(
        decision_data=_make_decision("APPROVE"),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.9,
        governance_flags=flags,
        critique_data={"recommendation": "REJECT"},
        memory_count=0,
        trace_id="test-004",
        scenario_type="variation",
    )

    assert result.final_decision == "ESCALATE"
    assert result.original_decision == "APPROVE"
    assert result.was_overridden is True
    # SAFETY_GATE_ACTIVE is a CRITICAL flag, so governance fires first
    assert "GOVERNANCE_CRITICAL_OVERRIDE" in result.override_chain
    print(f"  OK Safety gate override: APPROVE -> ESCALATE")
    print(f"  OK Override chain: {result.override_chain}")
    print("  OK All safety gate tests PASSED")


def test_conflict_detection():
    """WALL-E says REJECT, Aria says APPROVE → conflict detected."""
    print("\n--- TEST 5: Conflict Detection ---")

    flags = evaluate_governance("variation", cost=5000, days=2, risk_score=0.3)
    result = finalize_decision(
        decision_data=_make_decision("APPROVE"),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=flags,
        critique_data={"recommendation": "REJECT"},
        memory_count=0,
        trace_id="test-005",
        scenario_type="variation",
    )

    assert result.conflict_detected is True
    assert "WALL-E" in result.conflict_detail
    # Decision passes through (no override for conflict, it's informational)
    assert result.final_decision == "APPROVE"
    print(f"  OK Conflict detected: {result.conflict_detail}")
    print("  OK Conflict does NOT override (informational only)")
    print("  OK All conflict detection tests PASSED")


def test_reasoning_quality_warnings():
    """Missing governance/memory references → warnings emitted."""
    print("\n--- TEST 6: Reasoning Quality Warnings ---")

    flags = evaluate_governance("variation", cost=15000, days=2, risk_score=0.3)
    result = finalize_decision(
        decision_data=_make_decision("APPROVE", "I approve this because reasons."),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=flags,
        critique_data={"recommendation": "PROCEED"},
        memory_count=3,  # Memory exists
        trace_id="test-006",
        scenario_type="variation",
    )

    assert "MISSING_GOVERNANCE_REFERENCE" in result.reasoning_quality_warnings
    assert "MISSING_MEMORY_REFERENCE" in result.reasoning_quality_warnings
    print(f"  OK Warnings: {result.reasoning_quality_warnings}")
    print("  OK All reasoning quality tests PASSED")


def test_event_payload_structure():
    """DECISION_FINALIZED_V1 payload has all required fields."""
    print("\n--- TEST 7: Event Payload Structure ---")

    flags = evaluate_governance("variation", cost=60000, days=2, risk_score=0.3)
    result = finalize_decision(
        decision_data=_make_decision("APPROVE"),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=flags,
        critique_data={"recommendation": "PROCEED"},
        memory_count=2,
        trace_id="test-007",
        scenario_type="variation",
    )

    payload = result.to_event_payload()
    required_keys = {
        "final_decision", "original_decision", "override_chain",
        "primary_override_reason", "risk_score", "governance_flags",
        "governance_flag_count", "has_critical_governance",
        "conflict_detected", "conflict_detail",
        "reasoning_quality_warnings", "was_overridden", "was_system_forced",
        "final_justification", "original_justification",
    }
    missing = required_keys - set(payload.keys())
    assert len(missing) == 0, f"Missing keys: {missing}"
    print(f"  OK All {len(required_keys)} required keys present")
    print(f"  OK final_decision={payload['final_decision']}")
    print(f"  OK override_chain={payload['override_chain']}")
    print(f"  OK primary_reason={payload['primary_override_reason']}")
    print("  OK All payload structure tests PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print(" A.G.E.N.T.S. — DECISION FINALIZER VERIFICATION")
    print("=" * 60)

    test_clean_passthrough()
    test_contract_failure()
    test_governance_critical_override()
    test_safety_gate_override()
    test_conflict_detection()
    test_reasoning_quality_warnings()
    test_event_payload_structure()

    print("\n" + "=" * 60)
    print(" ALL DECISION FINALIZER TESTS PASSED")
    print("=" * 60)
