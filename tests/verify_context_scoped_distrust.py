"""Verification suite for context-scoped adaptive distrust (Phase 5.1).

Covers:
    - Why-line formatting across every override branch
    - Distrust-level label on every decision
    - Adaptive-distrust sequence: a 0.85-confidence decision gets blocked
      purely by accumulated scenario-scoped failure history
    - Cross-scenario isolation: drift in scenario X does NOT escalate
      unrelated scenario Y (pure scoping contract)
    - Global fallback: scenarios with no history inherit 'global' patterns
    - Exact-match wins: when a scenario has history, 'global' is ignored

Run with an isolated DB so the live state is never touched:

    PowerShell:
        $env:AGENTS_DB_PATH = "$env:TEMP\\agents_distrust_verify.db"
        Remove-Item $env:AGENTS_DB_PATH -ErrorAction SilentlyContinue
        python tests\\verify_context_scoped_distrust.py
        Remove-Item Env:AGENTS_DB_PATH

    bash:
        AGENTS_DB_PATH=/tmp/agents_distrust_verify.db \\
            python tests/verify_context_scoped_distrust.py

Exit code 0 = all assertions passed. Non-zero = contract violated.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.logic.decision_finalizer import finalize_decision
from agents.logic.governance_engine import evaluate_governance
from agents.logic.memory_db import upsert_negative_pattern


def d(decision="APPROVE", conf=0.9, just="Approve because governance flag and history"):
    return {
        "decision": decision,
        "justification": just,
        "confidence_score": conf,
        "confidence_reason": "demo",
        "conditions": ["x"],
        "impact": {"cost": 5000, "days": 2},
    }


def main() -> int:
    # 1. Clean APPROVE (high confidence, no drift)
    f1 = finalize_decision(
        decision_data=d("APPROVE", 0.9),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=evaluate_governance("variation", 5000, 2, 0.3),
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="t1",
        scenario_type="variation",
    )
    print("1. CLEAN APPROVE  ->", f1.why)

    # 2. Contract failure -> system-forced
    f2 = finalize_decision(
        decision_data={},
        decision_valid=False,
        decision_error_reason="invalid_json",
        risk_score=0.3,
        governance_flags=[],
        critique_data=None,
        memory_count=0,
        trace_id="t2",
        scenario_type="variation",
    )
    print("2. CONTRACT FAIL  ->", f2.why)

    # 3. CRITICAL governance flag (budget > $50k)
    f3 = finalize_decision(
        decision_data=d("APPROVE", 0.9),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=evaluate_governance("variation", 60000, 2, 0.3),
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="t3",
        scenario_type="variation",
    )
    print("3. GOV CRITICAL   ->", f3.why)

    # 4. Aria self-escalates (no override triggered)
    f4 = finalize_decision(
        decision_data=d("ESCALATE", 0.5),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.4,
        governance_flags=evaluate_governance("variation", 5000, 2, 0.4),
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="t4",
        scenario_type="variation",
    )
    print("4. ARIA ESCALATE  ->", f4.why)

    # 5. Confidence gate with drift patterns (scoped to 'variation')
    for _ in range(4):
        upsert_negative_pattern("owen_engine", "gmail_draft", "subject", "variation")
    for _ in range(2):
        upsert_negative_pattern("owen_engine", "gmail_draft", "body", "variation")
    f5 = finalize_decision(
        decision_data=d("APPROVE", 0.72),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=evaluate_governance("variation", 5000, 2, 0.3),
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="t5",
        scenario_type="variation",
    )
    print("5. CONFIDENCE GATE->", f5.why)
    print("   top_patterns   ->", f5.top_failure_patterns)

    # 6. APPROVE under drift (high enough conf to pass)
    f6 = finalize_decision(
        decision_data=d("APPROVE", 0.95),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=evaluate_governance("variation", 5000, 2, 0.3),
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="t6",
        scenario_type="variation",
    )
    print("6. APPROVE+DRIFT  ->", f6.why)

    # 7. Event payload must contain all new keys
    payload = f5.to_event_payload()
    required = (
        "why",
        "confidence_penalty",
        "confidence_adjusted",
        "confidence_threshold",
        "drift_pressure_index",
        "top_failure_patterns",
    )
    for k in required:
        assert k in payload, f"missing key: {k}"
    print("7. EVENT PAYLOAD  -> all new keys present")

    # 8. Adaptive-distrust sequence:
    #    Hold confidence at 0.85 and watch the system start escalating
    #    purely because of accumulated failure history.
    print("\n=== ADAPTIVE DISTRUST SEQUENCE (conf fixed at 0.85) ===")

    # Wipe patterns so the sequence starts clean
    import sqlite3, os
    db_path = os.environ.get("AGENTS_DB_PATH")
    if db_path and Path(db_path).exists():
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM owen_negative_patterns")
            conn.commit()

    def run_at(conf, label):
        res = finalize_decision(
            decision_data=d("APPROVE", conf),
            decision_valid=True,
            decision_error_reason=None,
            risk_score=0.3,
            governance_flags=evaluate_governance("variation", 5000, 2, 0.3),
            critique_data={"recommendation": "PROCEED"},
            memory_count=0,
            trace_id=f"seq-{label}",
            scenario_type="variation",
        )
        print(
            f"  {label} -> {res.final_decision:<8} "
            f"penalty={res.confidence_penalty:.2f} "
            f"threshold={res.confidence_threshold:.2f} "
            f"adj_conf={res.confidence_adjusted:.2f} "
            f"DPI={res.drift_pressure_index:.2f}"
        )
        print(f"       WHY: {res.why}")
        return res

    # Run 1: baseline, no drift
    r1 = run_at(0.85, "Run 1 (baseline)")
    assert r1.final_decision == "APPROVE", "Baseline should APPROVE"

    # Inject 2 failures on 'subject'  -> penalty = 0.10 (scoped to 'variation')
    for _ in range(2):
        upsert_negative_pattern("owen_engine", "gmail_draft", "subject", "variation")
    r2 = run_at(0.85, "Run 2 (2 failures)")

    # Inject 2 more failures on 'subject' -> count=4, penalty=0.20, threshold lifts to 0.70
    for _ in range(2):
        upsert_negative_pattern("owen_engine", "gmail_draft", "subject", "variation")
    r3 = run_at(0.85, "Run 3 (4 failures)")

    # Add a second failure key 'body' -> cross-key drift
    for _ in range(3):
        upsert_negative_pattern("owen_engine", "gmail_draft", "body", "variation")
    r4 = run_at(0.85, "Run 4 (4 subj + 3 body)")

    # Pile on more -> penalty saturates, threshold at 0.80
    for _ in range(4):
        upsert_negative_pattern("owen_engine", "gmail_draft", "subject", "variation")
    for _ in range(3):
        upsert_negative_pattern("owen_engine", "gmail_draft", "body", "variation")
    r5 = run_at(0.85, "Run 5 (saturated)")

    # Verdict: the whole point of the sequence is that a high-confidence
    # decision (0.85) eventually gets blocked purely by history.
    escalated = [r.final_decision for r in (r2, r3, r4, r5)].count("ESCALATE")
    print(f"\n  Adaptive escalations under conf=0.85: {escalated}/4 later runs")
    assert r5.final_decision == "ESCALATE", (
        "Adaptive distrust failed: saturated penalty should escalate at conf=0.85"
    )
    print("  OK Adaptive distrust proven: history alone escalated a 0.85-confidence run.")

    # Distrust label sanity: should climb with DPI and be surfaced in the WHY line
    assert "[DISTRUST:" in r5.why, "distrust_level suffix missing from WHY line"
    assert r1.distrust_level == "LOW", f"expected LOW at baseline, got {r1.distrust_level}"
    assert r5.distrust_level in {"HIGH", "BLOCKED"}, (
        f"expected HIGH or BLOCKED at saturation, got {r5.distrust_level}"
    )
    print(f"  OK distrust_level climbs: r1={r1.distrust_level}, r5={r5.distrust_level}")

    # 9. Cross-scenario isolation (the whole point of context-scoping)
    print("\n=== CROSS-SCENARIO ISOLATION (drift in 'variation' must not affect 'delay') ===")
    _wipe_patterns()
    for _ in range(4):
        upsert_negative_pattern("owen_engine", "gmail_draft", "subject", "variation")

    iso = finalize_decision(
        decision_data=d("APPROVE", 0.85),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=evaluate_governance("delay", 5000, 2, 0.3),
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="iso",
        scenario_type="delay",  # <- different scenario from the drift history
    )
    print(
        f"  delay @ 0.85   -> {iso.final_decision:<8} "
        f"penalty={iso.confidence_penalty:.2f} "
        f"top_patterns={iso.top_failure_patterns}"
    )
    print(f"       WHY: {iso.why}")
    assert iso.final_decision == "APPROVE", (
        "ISOLATION FAILED: drift in 'variation' bled into 'delay' and caused escalation"
    )
    assert iso.confidence_penalty == 0.0, (
        f"ISOLATION FAILED: expected penalty=0.0 in 'delay', got {iso.confidence_penalty}"
    )
    assert iso.top_failure_patterns == [], (
        f"ISOLATION FAILED: expected no patterns in 'delay', got {iso.top_failure_patterns}"
    )
    print("  OK 'delay' saw zero drift despite 4 failures in 'variation'.")

    # 10. Global fallback (scenario has no history -> 'global' patterns apply)
    print("\n=== GLOBAL FALLBACK (scenario has no history of its own) ===")
    _wipe_patterns()
    for _ in range(4):
        upsert_negative_pattern("owen_engine", "gmail_draft", "subject", "global")

    fb = finalize_decision(
        decision_data=d("APPROVE", 0.85),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=evaluate_governance("variation", 5000, 2, 0.3),
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="fb",
        scenario_type="variation",  # no variation-scoped patterns -> fall back to global
    )
    print(
        f"  variation @ 0.85 -> {fb.final_decision:<8} "
        f"penalty={fb.confidence_penalty:.2f} "
        f"top_patterns={fb.top_failure_patterns}"
    )
    print(f"       WHY: {fb.why}")
    assert fb.confidence_penalty > 0.0, (
        "FALLBACK FAILED: expected 'global' patterns to apply when scenario has no history"
    )
    assert any(p["failure_key"] == "subject" for p in fb.top_failure_patterns), (
        "FALLBACK FAILED: expected 'subject' pattern via global fallback"
    )
    print("  OK 'global' patterns correctly filled in for a scenario with no history.")

    # 11. Exact-match wins (pure scoping: global IGNORED when scenario has history)
    print("\n=== EXACT-MATCH WINS (scenario history exists -> global is ignored) ===")
    _wipe_patterns()
    # Heavy drift in 'global' (8 failures on 'subject')
    for _ in range(8):
        upsert_negative_pattern("owen_engine", "gmail_draft", "subject", "global")
    # Light drift in 'variation' (1 failure on 'body')
    upsert_negative_pattern("owen_engine", "gmail_draft", "body", "variation")

    ex = finalize_decision(
        decision_data=d("APPROVE", 0.85),
        decision_valid=True,
        decision_error_reason=None,
        risk_score=0.3,
        governance_flags=evaluate_governance("variation", 5000, 2, 0.3),
        critique_data={"recommendation": "PROCEED"},
        memory_count=0,
        trace_id="ex",
        scenario_type="variation",
    )
    print(
        f"  variation @ 0.85 -> {ex.final_decision:<8} "
        f"penalty={ex.confidence_penalty:.2f} "
        f"top_patterns={ex.top_failure_patterns}"
    )
    print(f"       WHY: {ex.why}")
    assert all(p["failure_key"] != "subject" for p in ex.top_failure_patterns), (
        "EXACT-MATCH FAILED: 'subject' (global) leaked into variation lookup"
    )
    assert any(p["failure_key"] == "body" for p in ex.top_failure_patterns), (
        "EXACT-MATCH FAILED: 'body' (variation) should dominate"
    )
    # Penalty should be small (1 failure on 'body' = 0.05), NOT large (8 failures on 'subject' = 0.30 cap)
    assert ex.confidence_penalty < 0.15, (
        f"EXACT-MATCH FAILED: penalty leaked from global; got {ex.confidence_penalty}"
    )
    print("  OK exact-match patterns dominate; global is ignored when scenario has history.")

    print("\n==> ALL SMOKE CHECKS PASSED.")
    return 0


def _wipe_patterns():
    """Clear owen_negative_patterns between isolation tests."""
    import sqlite3, os
    from pathlib import Path as _P
    db_path = os.environ.get("AGENTS_DB_PATH")
    if db_path and _P(db_path).exists():
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM owen_negative_patterns")
            conn.commit()


if __name__ == "__main__":
    sys.exit(main())
