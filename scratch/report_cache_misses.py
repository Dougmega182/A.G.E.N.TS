from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.logic.decision_cache import _classify_no_entry_miss, build_cache_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report CACHE_MISS no_entry classification breakdown.")
    parser.add_argument("--log", default="Agent logs/events.log.jsonl", help="Path to events log.")
    parser.add_argument("--last-events", type=int, default=0, help="Only inspect the last N log events.")
    parser.add_argument("--last-hours", type=float, default=0, help="Only inspect events from the last N hours.")
    parser.add_argument("--last-misses", type=int, default=0, help="Only inspect the last N CACHE_MISS no_entry events.")
    parser.add_argument("--samples", type=int, default=5, help="Examples to show per category.")
    parser.add_argument("--backfill-classification", action="store_true", help="Classify unclassified misses at report time without changing logs.")
    return parser.parse_args()


def parse_loop_input(raw: str) -> tuple[float, int]:
    parts = [part.strip() for part in raw.split(",", 2)]
    cost = 0.0
    days = 0
    if parts:
        m = re.search(r"([+-]?)\s*\$?\s*(\d[\d,]*)(\s*k\b)?", parts[0], flags=re.IGNORECASE)
        if m:
            cost = float(m.group(2).replace(",", ""))
            if m.group(3):
                cost *= 1000
    if len(parts) > 1:
        m = re.search(r"([+-]?)\s*(\d+)\s*days?\b", parts[1], flags=re.IGNORECASE)
        if m:
            days = int(m.group(2))
    return cost, days


args = parse_args()
log_path = Path(args.log)
if not log_path.exists():
    raise SystemExit(f"Log file not found: {log_path}")

cutoff = None
if args.last_hours > 0:
    cutoff = datetime.utcnow() - timedelta(hours=args.last_hours)

with log_path.open("r", encoding="utf-8") as f:
    lines = f.readlines()

if args.last_events > 0:
    lines = lines[-args.last_events:]

trace_inputs = {}
trace_scenarios = {}
for line in lines:
    if not line.strip():
        continue
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue
    if event.get("type") != "LOOP_STARTED":
        continue
    trace_id = str(event.get("trace_id", ""))
    metadata = event.get("metadata", {})
    user_input = str(metadata.get("input", "")).strip()
    if trace_id and user_input:
        trace_inputs[trace_id] = user_input
        trace_scenarios[trace_id] = str(event.get("scenario", "")).strip().lower()

misses = []
for line in lines:
    if not line.strip():
        continue
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue
    if event.get("type") != "CACHE_MISS":
        continue
    metadata = event.get("metadata", {})
    if metadata.get("reason") != "no_entry":
        continue
    if cutoff is not None:
        try:
            event_time = datetime.fromisoformat(str(event.get("timestamp", "")))
        except Exception:
            continue
        if event_time < cutoff:
            continue
    misses.append(event)

if args.last_misses > 0:
    misses = misses[-args.last_misses:]

counts = Counter()
samples = defaultdict(lambda: deque(maxlen=max(1, args.samples)))
total = 0
classified_total = 0
backfilled = 0

for event in misses:
    metadata = event.get("metadata", {})
    category = metadata.get("miss_classification")
    if not category:
        category = "unclassified"
        if args.backfill_classification:
            trace_id = str(event.get("trace_id", ""))
            user_input = trace_inputs.get(trace_id, "")
            scenario_type = trace_scenarios.get(trace_id, str(event.get("scenario", "")).strip().lower())
            if user_input and scenario_type:
                cost, days = parse_loop_input(user_input)
                try:
                    context = build_cache_context(
                        scenario_type=scenario_type,
                        user_input=user_input,
                        cost=cost,
                        days=days,
                        governance_flags=[],
                    )
                    category = _classify_no_entry_miss(context)
                    backfilled += 1
                except Exception:
                    category = "unclassified"

    counts[str(category)] += 1
    total += 1
    if category != "unclassified":
        classified_total += 1
    sample = trace_inputs.get(str(event.get("trace_id", ""))) or str(event.get("trace_id", "<no sample>"))
    samples[str(category)].append(sample)

print(f"Total MISS (no_entry): {total}")
print(f"Classified: {classified_total}")
print(f"Unclassified: {counts.get('unclassified', 0)}")
if args.backfill_classification:
    print(f"Backfilled in report: {backfilled}")
print()

if total == 0:
    raise SystemExit(0)

for category, count in counts.most_common():
    pct = count / total * 100
    print(f"{category}: {count} ({pct:.1f}%)")

if classified_total:
    print()
    print("--- Classified Only ---")
    for category, count in counts.most_common():
        if category == "unclassified":
            continue
        pct = count / classified_total * 100
        print(f"{category}: {count} ({pct:.1f}%)")

print("\n--- Samples ---")
for category, _count in counts.most_common():
    print()
    print(f"[{category}]")
    for sample in samples[category]:
        print(f'- "{sample}"')
