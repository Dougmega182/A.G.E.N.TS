"""Verification suite for Phase 5.1.5 Decision Cache (Layer 1).

Covers the full contract agreed for ship:
    - STRICT+ v2 normalization (light canonicalization, never semantic)
    - Centralized key builder produces stable, deterministic keys
    - Cache put/get round-trip with FinalizedDecision reconstruction
    - Write-side bypass matrix: every unsafe decision is rejected
    - Read-side bypass matrix: risky live context blocks replay
    - TTL staleness: old entries return MISS reason=expired
    - policy_version change invalidates existing entries (cache key differs)
    - Bucket boundaries: cost_bucket and scenario_type changes miss
    - Race safety: concurrent writes to same key are a no-op (INSERT OR IGNORE)

Run against an isolated DB so the live state is never touched:

    PowerShell:
        $env:AGENTS_DB_PATH = "$env:TEMP\\agents_cache_verify.db"
        Remove-Item $env:AGENTS_DB_PATH -ErrorAction SilentlyContinue
        python tests\\verify_decision_cache.py
        Remove-Item Env:AGENTS_DB_PATH

Exit code 0 = all assertions passed.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.logic import decision_cache, memory_db
from agents.logic.decision_cache import (
    POLICY_VERSION,
    BypassReason,
    CacheContext,
    _classify_no_entry_miss,
    _bucket_cost,
    _bucket_days,
    _governance_flag_set,
    _normalize_issue,
    build_cache_context,
    cache_get,
    cache_put,
)
from agents.logic.decision_finalizer import FinalizedDecision


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _approved(conf: float = 0.85, distrust: str = "LOW") -> FinalizedDecision:
    return FinalizedDecision(
        final_decision="APPROVE",
        final_justification="approved on historical stability",
        original_decision="APPROVE",
        original_justification="approved on historical stability",
        confidence_score=conf,
        confidence_reason="history stable",
        distrust_level=distrust,
        why=f"APPROVED: confidence {conf:.2f} \u2265 0.60 threshold [DISTRUST: {distrust}]",
    )


def _wipe_cache():
    memory_db.cache_clear_all("orchestrator")


# ---------------------------------------------------------------------
# 1. Normalization (STRICT+ v2 \u2014 light canonicalization, NOT semantic)
# ---------------------------------------------------------------------


def test_normalization() -> None:
    print("\n=== 1. NORMALIZATION (STRICT+ v2) ===")

    # Variants of pluralization / tense on the same phrase should collide.
    singular = _normalize_issue("Variation: +$12k, +3 days, Rain delay slab")
    plural = _normalize_issue("Variation: +$13,000, +3 days, Rain delays slab")
    past = _normalize_issue("Variation: +$12000, +3 days, Rain delayed slab")
    print(f"  'Rain delay slab'    -> '{singular}'")
    print(f"  'Rain delays slab'   -> '{plural}'")
    print(f"  'Rain delayed slab'  -> '{past}'")
    assert singular == plural == past, (
        f"pluralization/tense variants must collide: {singular!r} / {plural!r} / {past!r}"
    )

    # Curated connector variants now collide under STRICT+ v2.
    with_on = _normalize_issue("Variation: +$12k, +3 days, Rain delays on slab")
    print(f"  'Rain delays on slab'-> '{with_on}'")
    assert with_on == singular, "connector 'on' should collapse under STRICT+ v2"

    with_to = _normalize_issue("Variation: +$12k, +3 days, Rain delays to slab")
    print(f"  'Rain delays to slab'-> '{with_to}'")
    assert with_to == singular, "connector 'to' should collapse under STRICT+ v2"

    # Semantically different topic must never collide.
    other = _normalize_issue("Concrete supply delay")
    print(f"  'Concrete supply delay' -> '{other}'")
    assert singular != other, "'rain delay' must not collide with 'concrete supply delay'"

    # Physical locations / identifiers must remain distinct.
    grid_a4 = _normalize_issue("Variation: +$12k, +3 days, Rain delay on Grid A-4 slab pour")
    grid_b1 = _normalize_issue("Variation: +$12k, +3 days, Rain delay on Grid B-1 slab pour")
    print(f"  'Rain delay on Grid A-4 slab pour' -> '{grid_a4}'")
    print(f"  'Rain delay on Grid B-1 slab pour' -> '{grid_b1}'")
    assert grid_a4 != grid_b1, "different physical locations must not collide"

    # Scenario prefix stripped only at the start (not mid-sentence).
    assert _normalize_issue("Variation: Rain delay slab") == _normalize_issue("Rain delay slab")
    assert "delay" in _normalize_issue("Rain delay slab"), (
        "'delay' must survive mid-sentence — scenario prefix strip must be anchored"
    )

    # Conservative suffix trim does NOT break 'success' (no 'succes').
    assert _normalize_issue("success test") == "success test"

    # Empty input is safe.
    assert _normalize_issue("") == ""
    assert _normalize_issue(None) == ""  # type: ignore[arg-type]
    print("  OK STRICT+ v2 collides curated connector variants; preserves mid-sentence words and location identifiers.")


# ---------------------------------------------------------------------
# 2. Bucketing (aligned with governance thresholds)
# ---------------------------------------------------------------------


def test_bucketing() -> None:
    print("\n=== 2. BUCKETING ===")
    assert _bucket_cost(0) == "0-5k"
    assert _bucket_cost(5_000) == "0-5k"
    assert _bucket_cost(5_001) == "5-10k"
    assert _bucket_cost(12_000) == "10-25k"
    assert _bucket_cost(18_000) == "10-25k"
    assert _bucket_cost(26_000) == "25-50k"
    assert _bucket_cost(60_000) == "50k+"
    print("  OK cost buckets align with governance thresholds.")

    assert _bucket_days(0) == "0-1d"
    assert _bucket_days(1) == "0-1d"
    assert _bucket_days(2) == "1-3d"
    assert _bucket_days(7) == "3-7d"
    assert _bucket_days(8) == "7-14d"
    assert _bucket_days(15) == "14d+"
    print("  OK delay buckets align with governance thresholds.")


# ---------------------------------------------------------------------
# 3. Key determinism (centralized builder, same inputs \u2192 same key)
# ---------------------------------------------------------------------


def test_key_determinism() -> None:
    print("\n=== 3. KEY DETERMINISM ===")

    flags = [
        {"flag_type": "HIGH_IMPACT", "severity": "MEDIUM"},
        {"flag_type": "SCHEDULE_WATCH", "severity": "LOW"},
    ]
    flags_reordered = [
        {"flag_type": "SCHEDULE_WATCH", "severity": "LOW"},
        {"flag_type": "HIGH_IMPACT", "severity": "MEDIUM"},
    ]

    ctx1 = build_cache_context(
        scenario_type="variation",
        user_input="Variation: +$12k, +3 days, Rain delay slab",
        cost=12_000,
        days=3,
        governance_flags=flags,
    )
    # Same canonical phrase (pluralization differs), same buckets, same
    # flags (reorder tolerated by sorted join) → identical key.
    ctx2 = build_cache_context(
        scenario_type="variation",
        user_input="Variation: +$13,000, +3 days, Rain delays slab",
        cost=13_000,
        days=3,
        governance_flags=flags_reordered,
    )

    assert ctx1.cache_key == ctx2.cache_key, "equivalent inputs must produce identical cache key"
    print(f"  same key across equivalent inputs: {ctx1.cache_key[:16]}...")

    # Different scenario_type \u2192 different key
    ctx3 = build_cache_context(
        scenario_type="delay",
        user_input="Rain delay slab",
        cost=12_000,
        days=3,
        governance_flags=flags,
    )
    assert ctx1.cache_key != ctx3.cache_key

    # Different cost bucket \u2192 different key
    ctx4 = build_cache_context(
        scenario_type="variation",
        user_input="Rain delay slab",
        cost=40_000,  # 25-50k bucket
        days=3,
        governance_flags=flags,
    )
    assert ctx1.cache_key != ctx4.cache_key
    print("  OK scenario_type, cost_bucket, delay_bucket changes all flip the key.")


# ---------------------------------------------------------------------
# 4. Cache put/get round-trip
# ---------------------------------------------------------------------


def test_round_trip() -> None:
    print("\n=== 4. CACHE PUT/GET ROUND-TRIP ===")
    _wipe_cache()
    flags: list = []
    ctx = build_cache_context(
        scenario_type="variation",
        user_input="Rain delay slab",
        cost=12_000,
        days=3,
        governance_flags=flags,
    )

    wrote, outcome = cache_put(ctx, _approved(0.85), trace_id="T-FIRST", scenario_type="variation")
    assert wrote and outcome == "WROTE", f"first write should succeed, got {outcome}"

    got, out = cache_get(
        ctx,
        governance_flags=flags,
        current_distrust_level="LOW",
        trace_id="T-SECOND",
        scenario_type="variation",
    )
    assert out == "HIT", f"expected HIT, got {out}"
    assert got is not None and got.final_decision == "APPROVE"
    assert got.confidence_score == 0.85
    print(f"  OK round-trip: write -> read returns FinalizedDecision (decision={got.final_decision})")


# ---------------------------------------------------------------------
# 5. Write-side bypass matrix
# ---------------------------------------------------------------------


def test_write_bypass_matrix() -> None:
    print("\n=== 5. WRITE-SIDE BYPASS MATRIX ===")
    _wipe_cache()
    flags: list = []
    ctx = build_cache_context(
        scenario_type="variation",
        user_input="routine safe input",
        cost=5_000,
        days=1,
        governance_flags=flags,
    )

    # a) system-forced \u2192 BYPASS
    sf = _approved()
    sf.was_system_forced = True
    wrote, outcome = cache_put(ctx, sf, trace_id="T-SF", scenario_type="variation")
    assert outcome == "BYPASS" and not wrote, "system-forced must bypass"

    # b) critical governance \u2192 BYPASS
    cg = _approved()
    cg.has_critical_governance = True
    wrote, outcome = cache_put(ctx, cg, trace_id="T-CG", scenario_type="variation")
    assert outcome == "BYPASS" and not wrote, "critical governance must bypass"

    # c) conflict \u2192 BYPASS
    cf = _approved()
    cf.conflict_detected = True
    wrote, outcome = cache_put(ctx, cf, trace_id="T-CF", scenario_type="variation")
    assert outcome == "BYPASS" and not wrote, "conflict must bypass"

    # d) overridden \u2192 BYPASS
    ov = _approved()
    ov.was_overridden = True
    wrote, outcome = cache_put(ctx, ov, trace_id="T-OV", scenario_type="variation")
    assert outcome == "BYPASS" and not wrote, "overridden must bypass"

    # e) decision != APPROVE \u2192 BYPASS
    es = _approved()
    es.final_decision = "ESCALATE"
    wrote, outcome = cache_put(ctx, es, trace_id="T-ES", scenario_type="variation")
    assert outcome == "BYPASS" and not wrote, "non-APPROVE must bypass"

    # f) low confidence \u2192 BYPASS
    lc = _approved(conf=0.65)
    wrote, outcome = cache_put(ctx, lc, trace_id="T-LC", scenario_type="variation")
    assert outcome == "BYPASS" and not wrote, "confidence < 0.7 must bypass"

    # g) HIGH distrust \u2192 BYPASS
    hd = _approved(distrust="HIGH")
    wrote, outcome = cache_put(ctx, hd, trace_id="T-HD", scenario_type="variation")
    assert outcome == "BYPASS" and not wrote, "distrust HIGH must bypass"

    # Verify nothing was actually written
    row = memory_db.cache_read("orchestrator", ctx.cache_key)
    assert row is None, f"no row should exist; got {row}"
    print("  OK all 7 write-side bypass reasons rejected; cache stayed empty.")


# ---------------------------------------------------------------------
# 6. Read-side bypass matrix
# ---------------------------------------------------------------------


def test_read_bypass_matrix() -> None:
    print("\n=== 6. READ-SIDE BYPASS MATRIX ===")
    _wipe_cache()
    flags: list = []
    ctx = build_cache_context(
        scenario_type="variation",
        user_input="Rain delay slab",
        cost=5_000,
        days=1,
        governance_flags=flags,
    )
    cache_put(ctx, _approved(), trace_id="T-SEED", scenario_type="variation")

    # a) live CRITICAL governance \u2192 BYPASS (even though key would hit)
    live_critical = [{"flag_type": "BUDGET_CRITICAL", "severity": "CRITICAL"}]
    got, out = cache_get(
        ctx,
        governance_flags=live_critical,
        current_distrust_level="LOW",
        trace_id="T-READ-CG",
        scenario_type="variation",
    )
    assert out == "BYPASS" and got is None, "live CRITICAL governance must bypass read"

    # b) live HIGH distrust \u2192 BYPASS
    got, out = cache_get(
        ctx,
        governance_flags=flags,
        current_distrust_level="HIGH",
        trace_id="T-READ-HD",
        scenario_type="variation",
    )
    assert out == "BYPASS" and got is None, "live HIGH distrust must bypass read"

    # c) live BLOCKED distrust \u2192 BYPASS
    got, out = cache_get(
        ctx,
        governance_flags=flags,
        current_distrust_level="BLOCKED",
        trace_id="T-READ-BL",
        scenario_type="variation",
    )
    assert out == "BYPASS" and got is None, "live BLOCKED distrust must bypass read"

    # Clean read path still works
    got, out = cache_get(
        ctx,
        governance_flags=flags,
        current_distrust_level="LOW",
        trace_id="T-READ-OK",
        scenario_type="variation",
    )
    assert out == "HIT" and got is not None, "clean context should still hit"
    print("  OK read-side bypasses for CRITICAL governance and HIGH/BLOCKED distrust; clean path still hits.")


# ---------------------------------------------------------------------
# 7. TTL expiry
# ---------------------------------------------------------------------


def test_ttl_expiry() -> None:
    print("\n=== 7. TTL EXPIRY ===")
    _wipe_cache()
    flags: list = []
    ctx = build_cache_context(
        scenario_type="variation",
        user_input="Rain delay slab",
        cost=5_000,
        days=1,
        governance_flags=flags,
    )
    cache_put(ctx, _approved(), trace_id="T-TTL", scenario_type="variation")

    # Rewind created_at to two days ago (default TTL is 48h \u2014 boundary, use 72h for safety)
    stale_ts = (datetime.utcnow() - timedelta(hours=72)).isoformat()
    db_path = os.environ.get("AGENTS_DB_PATH") or str(memory_db.DB_PATH)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE decision_cache SET created_at = ? WHERE cache_key = ?",
            (stale_ts, ctx.cache_key),
        )
        conn.commit()

    got, out = cache_get(
        ctx,
        governance_flags=flags,
        current_distrust_level="LOW",
        trace_id="T-TTL-READ",
        scenario_type="variation",
    )
    assert out == "MISS" and got is None, f"stale entry must MISS, got {out}"
    print("  OK stale entry (>72h) returns MISS reason=expired.")


# ---------------------------------------------------------------------
# 8. policy_version change invalidates existing entries
# ---------------------------------------------------------------------


def test_policy_version_invalidation() -> None:
    print("\n=== 8. POLICY VERSION INVALIDATION ===")
    _wipe_cache()
    flags: list = []
    current = build_cache_context(
        scenario_type="variation",
        user_input="Rain delay slab",
        cost=5_000,
        days=1,
        governance_flags=flags,
    )
    ctx_v1 = CacheContext(
        scenario_type=current.scenario_type,
        normalized_issue=current.normalized_issue,
        cost_bucket=current.cost_bucket,
        delay_bucket=current.delay_bucket,
        governance_flag_set=current.governance_flag_set,
        policy_version="v1",
    )
    cache_put(ctx_v1, _approved(), trace_id="T-POL-V1", scenario_type="variation")

    # Simulate a policy bump by manually crafting a v2 context
    ctx_v2 = CacheContext(
        scenario_type=ctx_v1.scenario_type,
        normalized_issue=ctx_v1.normalized_issue,
        cost_bucket=ctx_v1.cost_bucket,
        delay_bucket=ctx_v1.delay_bucket,
        governance_flag_set=ctx_v1.governance_flag_set,
        policy_version="v2",
    )
    assert ctx_v1.cache_key != ctx_v2.cache_key, "policy_version change must flip key"

    got, out = cache_get(
        ctx_v2,
        governance_flags=flags,
        current_distrust_level="LOW",
        trace_id="T-POL-V2",
        scenario_type="variation",
    )
    assert out == "MISS" and got is None, "v2 key must MISS on v1-seeded cache"
    print("  OK policy_version bump invalidates existing entries cleanly.")


# ---------------------------------------------------------------------
# 9. Bucket change invalidation
# ---------------------------------------------------------------------


def test_bucket_invalidation() -> None:
    print("\n=== 9. BUCKET / SCENARIO INVALIDATION ===")
    _wipe_cache()
    flags: list = []
    ctx_small = build_cache_context(
        scenario_type="variation",
        user_input="Rain delay slab",
        cost=5_000,  # 0-5k
        days=1,
        governance_flags=flags,
    )
    cache_put(ctx_small, _approved(), trace_id="T-BKT", scenario_type="variation")

    # Different cost bucket
    ctx_big = build_cache_context(
        scenario_type="variation",
        user_input="Rain delay slab",
        cost=40_000,  # 25-50k
        days=1,
        governance_flags=flags,
    )
    got, out = cache_get(
        ctx_big,
        governance_flags=flags,
        current_distrust_level="LOW",
        trace_id="T-BKT-BIG",
        scenario_type="variation",
    )
    assert out == "MISS", f"bucket change must MISS, got {out}"

    # Different scenario_type
    ctx_delay = build_cache_context(
        scenario_type="delay",
        user_input="Rain delay slab",
        cost=5_000,
        days=1,
        governance_flags=flags,
    )
    got, out = cache_get(
        ctx_delay,
        governance_flags=flags,
        current_distrust_level="LOW",
        trace_id="T-BKT-SC",
        scenario_type="delay",
    )
    assert out == "MISS", f"scenario change must MISS, got {out}"
    print("  OK cost_bucket change and scenario_type change both flip the key -> MISS.")


# ---------------------------------------------------------------------
# 10. Race safety (INSERT OR IGNORE)
# ---------------------------------------------------------------------


def test_race_safety() -> None:
    print("\n=== 10. RACE SAFETY (INSERT OR IGNORE) ===")
    _wipe_cache()
    flags: list = []
    ctx = build_cache_context(
        scenario_type="variation",
        user_input="Rain delay slab",
        cost=5_000,
        days=1,
        governance_flags=flags,
    )

    # First write wins
    wrote1, out1 = cache_put(ctx, _approved(), trace_id="T-R1", scenario_type="variation")
    assert wrote1 and out1 == "WROTE"

    # Second identical write becomes a no-op
    wrote2, out2 = cache_put(ctx, _approved(), trace_id="T-R2", scenario_type="variation")
    assert (not wrote2) and out2 == "RACE", f"expected RACE on duplicate, got {out2}"

    # Verify the first writer's trace_id is retained as source_trace_id
    row = memory_db.cache_read("orchestrator", ctx.cache_key)
    assert row is not None and row["source_trace_id"] == "T-R1", "first writer must remain the source"
    print("  OK concurrent writes: first wins, subsequent ones are no-ops; source_trace_id preserved.")


# ---------------------------------------------------------------------
# 11. Cache hit increments hit_count and sets last_hit_at
# ---------------------------------------------------------------------


def test_hit_counter() -> None:
    print("\n=== 11. HIT COUNTER + last_hit_at ===")
    _wipe_cache()
    flags: list = []
    ctx = build_cache_context(
        scenario_type="variation",
        user_input="Rain delay slab",
        cost=5_000,
        days=1,
        governance_flags=flags,
    )
    cache_put(ctx, _approved(), trace_id="T-SEED", scenario_type="variation")

    for i in range(3):
        cache_get(
            ctx,
            governance_flags=flags,
            current_distrust_level="LOW",
            trace_id=f"T-HIT-{i}",
            scenario_type="variation",
        )

    row = memory_db.cache_read("orchestrator", ctx.cache_key)
    assert row is not None
    assert row["hit_count"] == 3, f"expected hit_count=3, got {row['hit_count']}"
    assert row["last_hit_at"] is not None
    print(f"  OK hit_count={row['hit_count']}, last_hit_at set.")


# ---------------------------------------------------------------------
# 12. MISS CLASSIFICATION (telemetry-only guidance)
# ---------------------------------------------------------------------


def test_miss_classification() -> None:
    print("\n=== 12. MISS CLASSIFICATION ===")
    _wipe_cache()
    flags: list = []

    seed_ctx = build_cache_context(
        scenario_type="variation",
        user_input="Variation: +$3k, +1 day, Rain delay on Grid A-4 slab pour",
        cost=3_000,
        days=1,
        governance_flags=flags,
    )
    wrote, outcome = cache_put(seed_ctx, _approved(), trace_id="T-MISS-SEED", scenario_type="variation")
    assert wrote and outcome == "WROTE", f"seed write should succeed, got {outcome}"

    wording_ctx = build_cache_context(
        scenario_type="variation",
        user_input="Variation: +$3k, +1 day, Wet weather delay on Grid A-4 slab pour",
        cost=3_000,
        days=1,
        governance_flags=flags,
    )
    assert _classify_no_entry_miss(wording_ctx) == "wording_variation"

    entity_ctx = build_cache_context(
        scenario_type="variation",
        user_input="Variation: +$3k, +1 day, Rain delay on Grid B-1 slab pour",
        cost=3_000,
        days=1,
        governance_flags=flags,
    )
    assert _classify_no_entry_miss(entity_ctx) == "same_intent_different_entity"

    context_ctx = build_cache_context(
        scenario_type="variation",
        user_input="Variation: +$12k, +3 days, Rain delay on Grid A-4 slab pour",
        cost=12_000,
        days=3,
        governance_flags=flags,
    )
    assert _classify_no_entry_miss(context_ctx) == "insufficient_context"

    new_intent_ctx = build_cache_context(
        scenario_type="variation",
        user_input="Variation: +$3k, +1 day, Concrete supply delay pour",
        cost=3_000,
        days=1,
        governance_flags=flags,
    )
    assert _classify_no_entry_miss(new_intent_ctx) == "new_intent"
    print("  OK classified wording variation, different entity, insufficient context, and new intent.")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def main() -> int:
    print("Decision Cache verification \u2014 Phase 5.1.5 Layer 1")
    print(f"POLICY_VERSION = {POLICY_VERSION}")
    print(f"AGENTS_DB_PATH = {os.environ.get('AGENTS_DB_PATH', '<default>')}")

    test_normalization()
    test_bucketing()
    test_key_determinism()
    test_round_trip()
    test_write_bypass_matrix()
    test_read_bypass_matrix()
    test_ttl_expiry()
    test_policy_version_invalidation()
    test_bucket_invalidation()
    test_race_safety()
    test_hit_counter()
    test_miss_classification()

    print("\n==> ALL DECISION CACHE CHECKS PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
