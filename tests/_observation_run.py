"""Phase 6 observation runner \u2014 three representative construction variations.

Purpose
-------
Exercise the live orchestrator loop through `log_issue.py` with real LLM calls
so `events.log.jsonl` + `decision_cache` accumulate real telemetry. Every run
rejects the approval prompt so no Gmail draft or Calendar event is actually
created. Feedback prompts are all skipped (blank) so no noise lands in
`Agent logs/usage_feedback.jsonl` unless the operator chooses to log some.

Three scenarios are chosen to exercise:
  Scenario 1: baseline rain delay \u2014 first MISS, populates cache.
  Scenario 2: pluralization variant in same bucket \u2014 STRICT+ should collide
              and produce a CACHE_HIT (skipping Nadia \u2192 Aria).
  Scenario 3: structurally different issue in a different cost bucket \u2014
              CACHE_MISS expected.

After the run, the events log is tail-scanned for CACHE_* events and
DECISION_FINALIZED_V1 decision_phase_ms values so the operator can see the
observation snapshot immediately.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYTHON = str(ROOT / ".venv" / "Scripts" / "python.exe")
LOG_ISSUE = str(ROOT / "log_issue.py")
EVENTS_LOG = ROOT / "Agent logs" / "events.log.jsonl"


# (issue_text, cost_usd, days)
SCENARIOS = [
    ("Rain delay slab pour", "12000", "3"),
    ("Rain delays slab pour", "13000", "3"),
    ("Concrete supplier short-shipped 2m3 mix", "4500", "1"),
]

# Stdin for each run:
#   line 1: approval prompt      -> "n" (reject, no gateway side-effects)
#   lines 2-5: feedback prompts  -> blank (skip each; blank => no entry logged)
CANNED_STDIN = "n\n\n\n\n\n"


def run_one(issue: str, cost: str, days: str, idx: int, total: int) -> None:
    header = f"[{idx}/{total}] {issue}  (${cost}, {days}d)"
    print("\n" + "=" * 80)
    print(header)
    print("=" * 80)
    result = subprocess.run(
        [PYTHON, LOG_ISSUE, issue, cost, days],
        input=CANNED_STDIN,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300,  # 5-minute cap per scenario
    )
    # Print the full stream output so the operator can see the reasoning + WHY line
    print(result.stdout)
    if result.returncode != 0:
        print(f"\n[STDERR]\n{result.stderr}")
        print(f"[exit code: {result.returncode}]")


def tail_events_since(start_line: int) -> list:
    if not EVENTS_LOG.exists():
        return []
    with EVENTS_LOG.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines[start_line:] if line.strip()]


def event_count(events: list, event_type: str) -> int:
    return sum(1 for e in events if e.get("type") == event_type)


def summarize(events: list) -> None:
    print("\n" + "=" * 80)
    print("OBSERVATION SNAPSHOT \u2014 events produced by this batch")
    print("=" * 80)

    hit_count = event_count(events, "CACHE_HIT")
    miss_count = event_count(events, "CACHE_MISS")
    bypass_count = event_count(events, "CACHE_BYPASS")
    finalized = [e for e in events if e.get("type") == "DECISION_FINALIZED_V1"]

    total_cache = hit_count + miss_count
    hit_rate = (hit_count / total_cache * 100) if total_cache else 0.0

    print(f"  CACHE_HIT    : {hit_count}")
    print(f"  CACHE_MISS   : {miss_count}")
    print(f"  CACHE_BYPASS : {bypass_count}")
    print(f"  hit_rate     : {hit_rate:.1f}%  (from this batch only)")

    if finalized:
        print("\n  DECISION_FINALIZED_V1 timings (decision_phase_ms, served_from_cache):")
        for e in finalized:
            m = e.get("metadata", {})
            print(f"    - trace={e.get('trace_id', '')[:8]}  "
                  f"ms={m.get('decision_phase_ms', '?'):>6}  "
                  f"cached={m.get('served_from_cache')}  "
                  f"distrust={m.get('distrust_level')}  "
                  f"why={m.get('why', '')[:72]}")

    bypass_reasons: dict = {}
    for e in events:
        if e.get("type") == "CACHE_BYPASS":
            r = e.get("metadata", {}).get("reason", "?")
            bypass_reasons[r] = bypass_reasons.get(r, 0) + 1
    if bypass_reasons:
        print("\n  CACHE_BYPASS reasons:")
        for r, c in sorted(bypass_reasons.items(), key=lambda kv: -kv[1]):
            print(f"    - {r}: {c}")

    # Miss latency vs hit latency (from this batch)
    if finalized:
        miss_times = [e["metadata"].get("decision_phase_ms", 0) for e in finalized
                      if not e["metadata"].get("served_from_cache")]
        hit_times = [e["metadata"].get("decision_phase_ms", 0) for e in finalized
                     if e["metadata"].get("served_from_cache")]

        def _avg(xs):
            return sum(xs) / len(xs) if xs else 0

        avg_miss = _avg(miss_times)
        avg_hit = _avg(hit_times)
        print(f"\n  avg(decision_phase_ms | MISS) : {avg_miss:.0f}ms  (n={len(miss_times)})")
        print(f"  avg(decision_phase_ms | HIT)  : {avg_hit:.0f}ms  (n={len(hit_times)})")
        if miss_times and hit_times:
            savings = avg_miss - avg_hit
            pct = (savings / avg_miss * 100) if avg_miss > 0 else 0
            print(f"  effective_savings_ms          : {savings:.0f}ms  ({pct:.0f}%)")


def main() -> int:
    # Record starting position in events log so we only summarize this batch
    start_line = 0
    if EVENTS_LOG.exists():
        with EVENTS_LOG.open("r", encoding="utf-8") as f:
            start_line = sum(1 for _ in f)

    print(f"Observation run starting. Events log: {EVENTS_LOG}")
    print(f"Baseline line count: {start_line}")
    print(f"Scenarios to run: {len(SCENARIOS)}")

    for i, (issue, cost, days) in enumerate(SCENARIOS, 1):
        run_one(issue, cost, days, i, len(SCENARIOS))

    events = tail_events_since(start_line)
    summarize(events)

    print("\n[observation run complete]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
