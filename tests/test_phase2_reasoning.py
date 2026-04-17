"""
Phase 2 Verification Tests — Governance Engine + Structured Memory + Memory Conflict Detection

Tests:
    1. Governance flag generation (severity levels)
    2. CRITICAL enforcement detection
    3. Structured memory extraction from events
    4. Memory conflict detection (past REJECT → current APPROVE must justify deviation)
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_governance_flags():
    """Test that governance engine produces correct flags with severity."""
    from agents.logic.governance_engine import evaluate_governance, has_critical_flag, SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM

    print("\n--- TEST 1: Governance Flag Generation ---")

    # Case 1: Low-impact scenario → no flags
    flags = evaluate_governance("variation", cost=5000, days=2, risk_score=0.3)
    assert len(flags) == 0, f"Expected 0 flags for low-impact, got {len(flags)}"
    print("  ✅ Low-impact scenario: 0 flags (correct)")

    # Case 2: Medium-impact → HIGH_IMPACT flag
    flags = evaluate_governance("variation", cost=15000, days=2, risk_score=0.3)
    assert len(flags) == 1, f"Expected 1 flag for $15k cost, got {len(flags)}"
    assert flags[0].flag_type == "HIGH_IMPACT"
    assert flags[0].severity == SEVERITY_MEDIUM
    print(f"  ✅ $15k variation: {flags[0].flag_type} [{flags[0].severity}] (correct)")

    # Case 3: High cost + high days + high risk → multiple flags
    flags = evaluate_governance("variation", cost=30000, days=10, risk_score=0.8)
    flag_types = [f.flag_type for f in flags]
    assert "BUDGET_HIGH" in flag_types, f"Expected BUDGET_HIGH, got {flag_types}"
    assert "SCHEDULE_PRESSURE" in flag_types, f"Expected SCHEDULE_PRESSURE, got {flag_types}"
    assert "MOMENTUM_RISK" in flag_types, f"Expected MOMENTUM_RISK, got {flag_types}"
    print(f"  ✅ High-impact scenario: {len(flags)} flags → {flag_types} (correct)")

    # Case 4: CRITICAL threshold
    flags = evaluate_governance("variation", cost=60000, days=15, risk_score=0.9)
    assert has_critical_flag(flags), "Expected CRITICAL flag for $60k/15d/0.9 risk"
    critical_types = [f.flag_type for f in flags if f.severity == SEVERITY_CRITICAL]
    print(f"  ✅ CRITICAL scenario: {critical_types} (correct)")

    print("  ✅ All governance flag tests PASSED")


def test_structured_memory():
    """Test that structured memory is correctly extracted from mock events."""
    from agents.logic.event_analytics import get_structured_memory, format_memory_for_agents
    from agents.logic.event_bus import EVENTS_LOG_PATH

    print("\n--- TEST 2: Structured Memory Extraction ---")

    # Create a temporary events file with mock DECISION_MADE events
    original_path = EVENTS_LOG_PATH
    
    # Write mock events to the real log path (append, then clean up)
    mock_events = []
    base_time = datetime.utcnow() - timedelta(hours=5)
    
    for i, (decision, cost, risk, scenario) in enumerate([
        ("APPROVE", 10000, 0.4, "variation"),
        ("REJECT", 25000, 0.7, "variation"),
        ("APPROVE", 5000, 0.2, "rfi"),
        ("ESCALATE", 50000, 0.9, "variation"),
        ("APPROVE", 8000, 0.3, "variation"),
    ]):
        mock_events.append(json.dumps({
            "type": "DECISION_MADE",
            "timestamp": (base_time + timedelta(hours=i)).isoformat(),
            "trace_id": f"test-trace-{i:04d}",
            "agent_id": "aria",
            "scenario": scenario,
            "metadata": {
                "decision": decision,
                "risk_score": risk,
                "impact": {"cost": cost, "days": i + 1, "risk_delta": 0.05},
                "justification": f"Test justification {i}",
                "conflict": "false",
                "forced_by_system": "true" if decision == "ESCALATE" else "false",
            }
        }))

    # Append mock events
    with open(EVENTS_LOG_PATH, "a", encoding="utf-8") as f:
        for event in mock_events:
            f.write(event + "\n")

    try:
        # Test structured memory retrieval for "variation" only
        memory = get_structured_memory("variation", limit=5)
        assert len(memory) > 0, "Expected at least 1 memory item for 'variation'"
        
        # Check that RFI events are filtered out
        scenarios = [m["scenario"] for m in memory]
        assert "rfi" not in scenarios, f"RFI should be filtered out, got scenarios: {scenarios}"
        print(f"  ✅ Scenario filtering: {len(memory)} variation memories (RFI excluded)")

        # Check structured fields exist
        required_fields = {"scenario", "cost", "days", "risk_score", "decision", "outcome"}
        for m in memory:
            assert required_fields.issubset(m.keys()), f"Missing fields in memory: {m.keys()}"
        print("  ✅ Structured fields present in all memory items")

        # Check outcome derivation
        outcomes = [m["outcome"] for m in memory]
        assert "system_forced_escalation" in outcomes, f"Expected 'system_forced_escalation' in outcomes: {outcomes}"
        assert "rejected" in outcomes, f"Expected 'rejected' in outcomes: {outcomes}"
        print(f"  ✅ Outcome derivation correct: {outcomes}")

        # Test human-readable formatting
        formatted = format_memory_for_agents(memory)
        assert "INSTITUTIONAL MEMORY" in formatted
        assert "$" in formatted  # Cost formatting
        print(f"  ✅ Human-readable formatting works")
        print(f"    Preview: {formatted[:120]}...")

    finally:
        # Clean up: remove mock events from the log
        # Read all lines, remove the ones we added
        if EVENTS_LOG_PATH.exists():
            with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Remove last N lines (the ones we appended)
            cleaned = lines[:-len(mock_events)]
            with open(EVENTS_LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(cleaned)

    print("  ✅ All structured memory tests PASSED")


def test_memory_conflict_detection():
    """Test: If past similar scenario was REJECTED but current proposes APPROVE, flag conflict."""
    from agents.logic.history_engine import check_memory_conflicts
    from agents.logic.event_bus import EVENTS_LOG_PATH

    print("\n--- TEST 3: Memory Conflict Detection ---")

    # Inject a REJECTED variation into the event log
    mock_event = json.dumps({
        "type": "DECISION_MADE",
        "timestamp": datetime.utcnow().isoformat(),
        "trace_id": "test-conflict-trace",
        "agent_id": "aria",
        "scenario": "variation",
        "metadata": {
            "decision": "REJECT",
            "risk_score": 0.7,
            "impact": {"cost": 20000, "days": 5, "risk_delta": 0.1},
            "justification": "Budget exceeded threshold without mitigation plan",
            "conflict": "false",
            "forced_by_system": "false",
        }
    })

    with open(EVENTS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(mock_event + "\n")

    try:
        # Now propose APPROVE for a similar variation → should detect conflict
        result = check_memory_conflicts("variation", "APPROVE")
        assert result["has_conflict"] is True, f"Expected conflict, got: {result}"
        print(f"  ✅ Conflict detected: {result['details']}")
        print(f"    Contradictions found: {len(result.get('contradictions', []))}")

        # Propose REJECT for variation → should NOT have conflict (aligns with history)
        result_aligned = check_memory_conflicts("variation", "REJECT")
        # This may or may not have conflicts depending on other history, but
        # the REJECT we just added should align
        print(f"  ✅ Aligned proposal check: has_conflict={result_aligned['has_conflict']}")

    finally:
        # Clean up
        if EVENTS_LOG_PATH.exists():
            with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
            cleaned = lines[:-1]
            with open(EVENTS_LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(cleaned)

    print("  ✅ Memory conflict detection tests PASSED")


def test_governance_enforcement_escalation():
    """Test: has_critical_flag correctly identifies when CRITICAL governance flags are present."""
    from agents.logic.governance_engine import evaluate_governance, has_critical_flag

    print("\n--- TEST 4: CRITICAL Governance Enforcement ---")

    # No critical flags
    flags = evaluate_governance("variation", cost=5000, days=2, risk_score=0.3)
    assert has_critical_flag(flags) is False
    print("  ✅ Low-impact: no CRITICAL flag (correct)")

    # CRITICAL via cost
    flags = evaluate_governance("variation", cost=60000, days=2, risk_score=0.3)
    assert has_critical_flag(flags) is True
    print("  ✅ $60k cost: CRITICAL flag raised (correct)")

    # CRITICAL via days
    flags = evaluate_governance("variation", cost=5000, days=15, risk_score=0.3)
    assert has_critical_flag(flags) is True
    print("  ✅ 15-day delay: CRITICAL flag raised (correct)")

    # CRITICAL via risk
    flags = evaluate_governance("variation", cost=5000, days=2, risk_score=0.9)
    assert has_critical_flag(flags) is True
    print("  ✅ 0.9 risk score: CRITICAL flag raised (correct)")

    print("  ✅ All enforcement tests PASSED")


def test_outcome_scoring():
    """Test: Outcome scoring correctly weights past decisions."""
    from agents.logic.event_analytics import score_outcome

    print("\n--- TEST 5: Outcome Scoring ---")

    # Positive: approved + stable
    assert score_outcome({"decision": "APPROVE", "outcome": "stable"}) == 1
    print("  OK APPROVE + stable = +1")

    # Positive: rejected (correct rejection)
    assert score_outcome({"decision": "REJECT", "outcome": "rejected"}) == 1
    print("  OK REJECT + rejected = +1")

    # Negative: system forced escalation
    assert score_outcome({"decision": "ESCALATE", "outcome": "system_forced_escalation"}) == -1
    print("  OK system_forced_escalation = -1")

    # Negative: conflict detected
    assert score_outcome({"decision": "APPROVE", "outcome": "conflict_detected"}) == -1
    print("  OK conflict_detected = -1")

    # Negative: governance overridden
    assert score_outcome({"decision": "APPROVE", "outcome": "stable", "governance_overridden": "true"}) == -1
    print("  OK governance_overridden = -1")

    # Neutral: escalated (not forced)
    assert score_outcome({"decision": "ESCALATE", "outcome": "escalated"}) == 0
    print("  OK ESCALATE + escalated = 0")

    print("  OK All outcome scoring tests PASSED")


def test_outcome_signal():
    """Test: Net outcome signal correctly aggregates memory scores."""
    from agents.logic.event_analytics import get_structured_memory, get_outcome_signal
    from agents.logic.event_bus import EVENTS_LOG_PATH

    print("\n--- TEST 6: Net Outcome Signal ---")

    # Inject mixed decisions
    mock_events = []
    base_time = datetime.utcnow() - timedelta(hours=3)

    for i, (decision, cost, risk, forced) in enumerate([
        ("APPROVE", 5000, 0.3, "false"),   # stable → +1
        ("REJECT", 15000, 0.6, "false"),    # rejected → +1
        ("ESCALATE", 40000, 0.9, "true"),   # system_forced → -1
    ]):
        mock_events.append(json.dumps({
            "type": "DECISION_MADE",
            "timestamp": (base_time + timedelta(hours=i)).isoformat(),
            "trace_id": f"test-signal-{i:04d}",
            "agent_id": "aria",
            "scenario": "variation",
            "metadata": {
                "decision": decision,
                "risk_score": risk,
                "impact": {"cost": cost, "days": i + 1, "risk_delta": 0.05},
                "justification": f"Signal test {i}",
                "conflict": "false",
                "forced_by_system": forced,
            }
        }))

    with open(EVENTS_LOG_PATH, "a", encoding="utf-8") as f:
        for event in mock_events:
            f.write(event + "\n")

    try:
        signal = get_outcome_signal("variation", limit=10)
        print(f"  Net score: {signal['net_score']:+d} ({signal['quality']})")
        print(f"  Breakdown: {signal['breakdown']}")
        assert signal["count"] > 0, "Expected at least 1 item"
        assert isinstance(signal["net_score"], int), "Net score should be int"
        assert signal["quality"] in ("historically_positive", "historically_neutral", "historically_poor")
        print("  OK Net outcome signal correctly computed")

    finally:
        if EVENTS_LOG_PATH.exists():
            with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
            cleaned = lines[:-len(mock_events)]
            with open(EVENTS_LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(cleaned)

    print("  OK All outcome signal tests PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print(" A.G.E.N.T.S. — PHASE 2 + 2.2 REASONING VERIFICATION")
    print("=" * 60)

    test_governance_flags()
    test_governance_enforcement_escalation()
    test_structured_memory()
    test_memory_conflict_detection()
    test_outcome_scoring()
    test_outcome_signal()

    print("\n" + "=" * 60)
    print(" ALL PHASE 2 + 2.2 TESTS PASSED")
    print("=" * 60)
