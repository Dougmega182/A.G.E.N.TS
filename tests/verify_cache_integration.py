"""Integration validation for Phase 5.1.5 Decision Cache against the live orchestrator loop.

This is the automated half of the real-world validation. Wall-clock latency remains a
manual check (meaningless with mocked LLM turns); everything else is proven here.

What this proves:
  1. SKIP-EXPENSIVE-PATH. First run invokes Nadia + Tucker + WALL-E critique + Aria + Jenny +
     WALL-E audit (6 LLM turns). Second run (same input) invokes ONLY Jenny + WALL-E audit
     (2 LLM turns). Nadia / Tucker / Sentinel critique / Aria are not called.
  2. TELEMETRY. Run 1 emits CACHE_MISS; Run 2 emits CACHE_HIT. Bypass events emit
     correct reason codes.
  3. BYPASS FLIPS ON LIVE DRIFT. A previously cached key stops replaying the moment the
     scenario's distrust_level climbs to HIGH. We inject gmail_draft drift patterns for the
     scenario and verify the next read emits CACHE_BYPASS (reason=distrust_high).
  4. STRICT+ v2 BOUNDARY END-TO-END. Pluralization and curated connector variants
     collide; topic changes and distinct physical locations do not.

Run with isolated state so nothing live is touched:

    PowerShell:
        $env:AGENTS_DB_PATH = "$env:TEMP\\agents_cache_integration.db"
        Remove-Item $env:AGENTS_DB_PATH -ErrorAction SilentlyContinue
        python tests\\verify_cache_integration.py
        Remove-Item Env:AGENTS_DB_PATH

Exit code 0 = all assertions passed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

# AGENTS_DB_PATH must be set before agents.* imports so the isolated DB is used.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Redirect the events log to a temp file so we don't pollute Agent logs/events.log.jsonl.
_TMP_EVENTS = Path(tempfile.gettempdir()) / "agents_cache_integration_events.jsonl"
if _TMP_EVENTS.exists():
    _TMP_EVENTS.unlink()
_TMP_PATTERNS = Path(tempfile.gettempdir()) / "agents_pattern_registry_integration.jsonl"
if _TMP_PATTERNS.exists():
    _TMP_PATTERNS.unlink()

# --- Stub LangChain packages so the orchestrator import succeeds without the real deps.
# The real LLMs are never invoked — _execute_contract_turn is monkey-patched. These stubs
# only exist so module-level `ChatX(...)` constructor calls don't crash on import.
import types as _types  # noqa: E402


class _StubMessage:
    def __init__(self, content: str = "") -> None:
        self.content = content


class _StubLLM:
    def __init__(self, *_args, **_kwargs) -> None:
        self.model = _kwargs.get("model", "stub")

    def invoke(self, *_args, **_kwargs):
        return _StubMessage('{"stub": true}')

    async def astream(self, *_args, **_kwargs):
        if False:  # pragma: no cover — makes this an async generator
            yield


def _install_stub(name: str, attrs: Dict[str, Any]) -> None:
    if name in sys.modules:
        return
    mod = _types.ModuleType(name)
    for attr, val in attrs.items():
        setattr(mod, attr, val)
    sys.modules[name] = mod


_install_stub("langchain_anthropic", {"ChatAnthropic": _StubLLM})
_install_stub("langchain_ollama", {"ChatOllama": _StubLLM})
_install_stub("langchain_google_genai", {"ChatGoogleGenerativeAI": _StubLLM})
_install_stub("langchain_openai", {"ChatOpenAI": _StubLLM})
_install_stub("langchain_community", {})
_install_stub("langchain_community.chat_models", {"ChatOllama": _StubLLM})
_install_stub(
    "langchain_core",
    {
        "messages": _types.ModuleType("langchain_core.messages"),
    },
)
_install_stub(
    "langchain_core.messages",
    {
        "SystemMessage": _StubMessage,
        "HumanMessage": _StubMessage,
        "AIMessage": _StubMessage,
    },
)
_install_stub("dotenv", {"load_dotenv": lambda *_a, **_k: None})

from agents.logic import event_bus as _event_bus  # noqa: E402
_event_bus.EVENTS_LOG_PATH = _TMP_EVENTS

from agents.logic import decision_cache, memory_db, pattern_registry  # noqa: E402
from agents.logic.decision_cache import build_cache_context  # noqa: E402
from agents.logic.governance_engine import evaluate_governance  # noqa: E402
from agents.logic.memory_db import upsert_negative_pattern  # noqa: E402
from agents.logic.risk_engine import calculate_risk_score  # noqa: E402
from agents.orchestrator import Orchestrator  # noqa: E402

pattern_registry.PATTERN_REGISTRY_PATH = _TMP_PATTERNS


# ---------------------------------------------------------------------
# Fake LLM turn \u2014 valid contract payloads, counts calls
# ---------------------------------------------------------------------


CALL_LOG: List[Dict[str, str]] = []


async def fake_contract_turn(
    agent_key: str,
    prompt_builder,
    input_message: str,
    contract_id: str,
    execution_context: str = "",
    trace_id: str = "N/A",
):
    """Replacement for Orchestrator._execute_contract_turn.

    Returns minimum-viable JSON for each contract so the orchestrator proceeds
    without contacting a real LLM. Every call is logged so the test can assert
    which agents ran on each loop.
    """
    CALL_LOG.append({"agent": agent_key, "contract": contract_id, "trace": trace_id})

    if agent_key == "aria":
        payload = {
            "decision": "APPROVE",
            "justification": (
                "governance flags are within tolerance and institutional memory shows "
                "historically stable outcomes for this scenario type"
            ),
            "confidence_score": 0.85,
            "confidence_reason": "stable history; routine variation within budget envelope",
            "conditions": ["standard mitigation"],
            "impact": {"cost": 12000, "days": 3, "risk_delta": 0.05},
        }
        return json.dumps(payload), True, ""

    # Jenny \u2014 email draft
    if agent_key == "jenny":
        return json.dumps({"to": "pm@example.com", "subject": "variation", "body": "update"}), True, ""

    # Any other agent (nadia / tucker / wall-e) \u2014 empty JSON is fine; downstream never
    # requires content on the happy path.
    return "{}", True, ""


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


async def _drive_loop(orch: Orchestrator, user_input: str, trace_id: str) -> None:
    async for _ in orch._run_generic_construction_loop("variation", user_input, trace_id):
        pass


def _read_events() -> List[Dict[str, Any]]:
    if not _TMP_EVENTS.exists():
        return []
    with _TMP_EVENTS.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _events_for_trace(trace_id: str) -> List[Dict[str, Any]]:
    return [e for e in _read_events() if e.get("trace_id") == trace_id]


def _clear_events_log() -> None:
    if _TMP_EVENTS.exists():
        _TMP_EVENTS.unlink()
    _TMP_EVENTS.touch()


def _clear_pattern_registry() -> None:
    if _TMP_PATTERNS.exists():
        _TMP_PATTERNS.unlink()


def _read_patterns() -> List[Dict[str, Any]]:
    if not _TMP_PATTERNS.exists():
        return []
    with _TMP_PATTERNS.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _wipe_cache_and_drift():
    memory_db.cache_clear_all("orchestrator")
    # Drop any Owen negative patterns that may have leaked across tests
    db_path = os.environ.get("AGENTS_DB_PATH") or str(memory_db.DB_PATH)
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM owen_negative_patterns")
        conn.commit()


# ---------------------------------------------------------------------
# Test 1 + 2: Skip expensive path on cache hit + telemetry
# ---------------------------------------------------------------------


async def test_skip_expensive_path() -> None:
    print("\n=== 1. SKIP EXPENSIVE PATH + TELEMETRY ===")
    _wipe_cache_and_drift()
    _clear_events_log()
    _clear_pattern_registry()

    orch = Orchestrator()
    orch._execute_contract_turn = fake_contract_turn  # type: ignore[assignment]

    user_input = "Variation: +$12k, +3 days, Rain delay slab"

    # Run 1 \u2014 expected CACHE_MISS; full loop runs
    CALL_LOG.clear()
    await _drive_loop(orch, user_input, "T-RUN1")
    run1 = [c["agent"] for c in CALL_LOG]
    print(f"  Run 1 agents invoked: {run1}")

    # Run 2 \u2014 expected CACHE_HIT; Nadia/Tucker/Sentinel/Aria skipped
    CALL_LOG.clear()
    await _drive_loop(orch, user_input, "T-RUN2")
    run2 = [c["agent"] for c in CALL_LOG]
    print(f"  Run 2 agents invoked: {run2}")

    # Run 1 must have called the full decision chain
    for agent in ("nadia", "tucker", "wall-e", "aria", "jenny"):
        assert agent in run1, f"Run 1 must invoke {agent}, got {run1}"

    # Run 2 must NOT have called the decision chain
    for agent in ("nadia", "tucker", "aria"):
        assert agent not in run2, f"Run 2 must NOT invoke {agent}, got {run2}"

    # Run 2 MUST still run Jenny (design decision \u2014 email not cached) and
    # WALL-E for the audit pass.
    assert "jenny" in run2, "Run 2 must still invoke Jenny (email not cached)"
    assert "wall-e" in run2, "Run 2 must still invoke WALL-E audit"

    # Quantitative delta
    savings_pct = int(round(100 * (len(run1) - len(run2)) / max(len(run1), 1)))
    print(f"  LLM-call delta: run1={len(run1)}, run2={len(run2)}, savings={savings_pct}%")
    assert savings_pct >= 60, f"expected >=60% LLM-call reduction, got {savings_pct}%"

    # Telemetry check
    run1_events = _events_for_trace("T-RUN1")
    run2_events = _events_for_trace("T-RUN2")
    run1_types = {e["type"] for e in run1_events}
    run2_types = {e["type"] for e in run2_events}
    assert "CACHE_MISS" in run1_types, f"Run 1 must emit CACHE_MISS, got {run1_types}"
    assert "CACHE_HIT" in run2_types, f"Run 2 must emit CACHE_HIT, got {run2_types}"
    miss_evt = next(e for e in run1_events if e["type"] == "CACHE_MISS")
    assert miss_evt["metadata"].get("miss_classification") == "new_intent", (
        f"first miss should classify as new_intent, got {miss_evt['metadata']}"
    )

    # Verify the cache hit event carries the source trace id and distrust label
    hit_evt = next(e for e in run2_events if e["type"] == "CACHE_HIT")
    meta = hit_evt.get("metadata", {})
    assert meta.get("source_trace_id") == "T-RUN1", (
        f"CACHE_HIT should point back at T-RUN1, got {meta.get('source_trace_id')}"
    )
    assert meta.get("distrust_level") in {"LOW", "ELEVATED", "HIGH", "BLOCKED"}
    print(f"  OK CACHE_HIT.source_trace_id={meta.get('source_trace_id')}, distrust={meta.get('distrust_level')}")

    # Verify DECISION_FINALIZED_V1 carries served_from_cache=true on run 2
    run2_finalized = [e for e in run2_events if e["type"] == "DECISION_FINALIZED_V1"]
    assert run2_finalized, "Run 2 must still emit DECISION_FINALIZED_V1 (for analytics)"
    assert run2_finalized[0]["metadata"].get("served_from_cache") is True, (
        "DECISION_FINALIZED_V1 on cache hit must carry served_from_cache=true"
    )
    print("  OK DECISION_FINALIZED_V1 tagged served_from_cache=true on hit")

    patterns = _read_patterns()
    assert len(patterns) == 2, f"expected 2 pattern entries, got {len(patterns)}"
    assert patterns[0].get("is_repeat_pattern") is False
    assert patterns[1].get("is_repeat_pattern") is True
    assert patterns[1].get("prior_seen_count") == 1
    print("  OK pattern registry logged the repeated workflow signature")


# ---------------------------------------------------------------------
# Test 3: Bypass flips on live drift (previously cached key)
# ---------------------------------------------------------------------


async def test_bypass_flips_on_drift() -> None:
    print("\n=== 2. CACHED KEY BYPASSES WHEN DRIFT DEGRADES LIVE CONTEXT ===")
    _wipe_cache_and_drift()
    _clear_events_log()
    _clear_pattern_registry()

    orch = Orchestrator()
    orch._execute_contract_turn = fake_contract_turn  # type: ignore[assignment]

    user_input = "Variation: +$12k, +3 days, Rain delay slab"

    # Seed the cache
    CALL_LOG.clear()
    await _drive_loop(orch, user_input, "T-SEED")

    # Confirm we actually cached something. Use the SAME governance evaluation the
    # orchestrator uses (cost=$12k raises HIGH_IMPACT at MEDIUM severity) so our
    # reconstructed cache_key matches what the orchestrator wrote.
    live_risk = calculate_risk_score("variation", 12_000, 3, user_input)
    live_flags = evaluate_governance("variation", 12_000, 3, live_risk)
    ctx = build_cache_context(
        scenario_type="variation",
        user_input=user_input,
        cost=12_000,
        days=3,
        governance_flags=live_flags,
    )
    row = memory_db.cache_read("orchestrator", ctx.cache_key)
    assert row is not None, "seed run should have populated the cache"

    # Inject enough gmail_draft drift in the 'variation' scenario to push distrust to HIGH.
    # Each failure on a distinct key adds ~0.05 penalty up to 0.3 cap; we want DPI > 0.30
    # so threshold lifts to 0.8 and distrust_level becomes HIGH.
    for _ in range(4):
        upsert_negative_pattern("owen_engine", "gmail_draft", "subject", "variation")
    for _ in range(2):
        upsert_negative_pattern("owen_engine", "gmail_draft", "body", "variation")

    # Replay
    CALL_LOG.clear()
    await _drive_loop(orch, user_input, "T-DRIFTED")
    drifted_calls = [c["agent"] for c in CALL_LOG]
    print(f"  Drifted replay agents: {drifted_calls}")

    # With live distrust=HIGH, the cache must bypass even on key match.
    drifted_events = _events_for_trace("T-DRIFTED")
    drifted_types = [e["type"] for e in drifted_events]
    assert "CACHE_BYPASS" in drifted_types, (
        f"Drift escalation must trigger CACHE_BYPASS, got {drifted_types}"
    )
    bypass = next(e for e in drifted_events if e["type"] == "CACHE_BYPASS")
    reason = bypass["metadata"].get("reason")
    assert reason == "distrust_high", (
        f"bypass reason should be distrust_high, got {reason!r}"
    )

    # Because we bypassed, the full LLM chain ran again
    for agent in ("nadia", "tucker", "aria"):
        assert agent in drifted_calls, (
            f"on bypass, {agent} must be re-invoked; got {drifted_calls}"
        )
    print("  OK cached key bypassed on live distrust_high; full loop re-ran.")


# ---------------------------------------------------------------------
# Test 4: STRICT+ v2 end-to-end boundary \u2014 connector variants collide, locations do not
# ---------------------------------------------------------------------


async def test_strict_plus_boundary_end_to_end() -> None:
    print("\n=== 3. STRICT+ v2 BOUNDARY END-TO-END ===")
    _wipe_cache_and_drift()
    _clear_events_log()
    _clear_pattern_registry()

    orch = Orchestrator()
    orch._execute_contract_turn = fake_contract_turn  # type: ignore[assignment]

    # Seed with singular form
    CALL_LOG.clear()
    await _drive_loop(orch, "Variation: +$12k, +3 days, Rain delay on Grid A-4 slab pour", "T-STRICT-SEED")

    # Pluralization variant \u2014 should HIT
    CALL_LOG.clear()
    await _drive_loop(orch, "Variation: +$13,000, +3 days, Rain delays for Grid A-4 slab pour", "T-STRICT-PLURAL")
    plural_events = _events_for_trace("T-STRICT-PLURAL")
    plural_types = [e["type"] for e in plural_events]
    assert "CACHE_HIT" in plural_types, (
        f"pluralization variant must hit cache, got {plural_types}"
    )
    print("  OK 'Rain delay on Grid A-4 slab pour' == 'Rain delays for Grid A-4 slab pour'")

    # Connector variant 'on' \u2014 should HIT under STRICT+ v2.
    CALL_LOG.clear()
    await _drive_loop(orch, "Variation: +$12k, +3 days, Rain delays to Grid A-4 slab pour", "T-STRICT-STOPWORD")
    stopword_events = _events_for_trace("T-STRICT-STOPWORD")
    stopword_types = [e["type"] for e in stopword_events]
    assert "CACHE_HIT" in stopword_types, (
        f"connector variant must HIT under STRICT+ v2, got {stopword_types}"
    )
    print("  OK connector variants collapse while Grid A-4 remains intact")

    # Distinct location identifiers must remain distinct.
    CALL_LOG.clear()
    await _drive_loop(orch, "Variation: +$12k, +3 days, Rain delay on Grid B-1 slab pour", "T-STRICT-LOCATION")
    location_events = _events_for_trace("T-STRICT-LOCATION")
    location_types = [e["type"] for e in location_events]
    assert "CACHE_MISS" in location_types, (
        f"different physical location must MISS, got {location_types}"
    )
    location_miss = next(e for e in location_events if e["type"] == "CACHE_MISS")
    assert location_miss["metadata"].get("miss_classification") == "same_intent_different_entity", (
        f"location miss should classify as same_intent_different_entity, got {location_miss['metadata']}"
    )
    print("  OK 'Grid B-1' != seed location (identifier preserved)")

    # Different topic \u2014 must MISS
    CALL_LOG.clear()
    await _drive_loop(orch, "Variation: +$12k, +3 days, Concrete supply delay pour", "T-STRICT-TOPIC")
    topic_events = _events_for_trace("T-STRICT-TOPIC")
    topic_types = [e["type"] for e in topic_events]
    assert "CACHE_MISS" in topic_types, (
        f"different topic must MISS, got {topic_types}"
    )
    print("  OK 'Concrete supply delay pour' != rain delay (different topic)")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


async def main() -> int:
    print("Decision Cache integration validation \u2014 Phase 5.1.5")
    print(f"AGENTS_DB_PATH = {os.environ.get('AGENTS_DB_PATH', '<default>')}")
    print(f"events log     = {_TMP_EVENTS}")

    await test_skip_expensive_path()
    await test_bypass_flips_on_drift()
    await test_strict_plus_boundary_end_to_end()

    print("\n==> ALL INTEGRATION CHECKS PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
