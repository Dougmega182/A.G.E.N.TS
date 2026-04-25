from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.logic.decision_cache import (
    _bucket_cost,
    _bucket_days,
    _governance_flag_set,
    _write_bypass_reason,
)
from agents.logic.decision_finalizer import FinalizedDecision

LOG_FILE = Path("Agent logs/events.log.jsonl")

_PREFIX_RE = re.compile(r"^\s*(?P<scenario>[a-z_ ]+?)\s*:?\s*(?P<body>.*)$", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"([+-]?)\s*\$?\s*(\d[\d,]*)(\s*k\b)?", re.IGNORECASE)
_DAYS_RE = re.compile(r"([+-]?)\s*(\d+)\s*days?\b", re.IGNORECASE)
_SUFFIX_RE = re.compile(r"(?<=\w{3})(?<!s)(es|ed|ing|s)\b")
_PUNCT_RE = re.compile(r"[^\w\s]+")
_WHITESPACE_RE = re.compile(r"\s+")
_CONNECTOR_WORDS = frozenset({"on", "of", "the", "for", "to", "at", "in"})


@dataclass
class RequestRecord:
    trace_id: str
    timestamp: str
    scenario_type: str
    user_input: str
    cost: float
    days: int
    normalized_v1: str
    normalized_v2: str
    governance_flag_set: str
    finalized: FinalizedDecision
    observed_lookup: str


def normalize_v1(raw: str) -> str:
    if not raw:
        return ""
    text = raw.lower()
    text = re.sub(r"^\s*(?:variation|delay|rfi)\s*:?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\+?\$\s*\d[\d,]*\s*k?\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\+?\s*\d[\d,]*\s*k\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\+?\s*\d+\s*days?\b", " ", text, flags=re.IGNORECASE)
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    words = [_SUFFIX_RE.sub("", w) for w in text.split(" ") if w]
    return " ".join(words)


def normalize_v2(raw: str) -> str:
    words = [w for w in normalize_v1(raw).split(" ") if w and w not in _CONNECTOR_WORDS]
    return " ".join(words)


def _parse_loop_started(event: Dict[str, object]) -> Optional[Dict[str, object]]:
    metadata = event.get("metadata", {})
    if not isinstance(metadata, dict):
        return None
    user_input = str(metadata.get("input", "")).strip()
    if not user_input:
        return None

    match = _PREFIX_RE.match(user_input)
    body = match.group("body") if match else user_input
    parts = [part.strip() for part in body.split(",", 2)]

    cost = 0.0
    days = 0
    if parts:
        amount_match = _AMOUNT_RE.search(parts[0])
        if amount_match:
            magnitude = float(amount_match.group(2).replace(",", ""))
            if amount_match.group(3):
                magnitude *= 1000
            cost = magnitude
    if len(parts) > 1:
        days_match = _DAYS_RE.search(parts[1])
        if days_match:
            days = int(days_match.group(2))

    return {
        "scenario_type": str(event.get("scenario", "")).strip().lower(),
        "user_input": user_input,
        "cost": cost,
        "days": days,
    }


def _load_records() -> List[RequestRecord]:
    traces: Dict[str, Dict[str, object]] = {}
    with LOG_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            trace_id = str(event.get("trace_id", ""))
            if not trace_id:
                continue
            trace = traces.setdefault(trace_id, {})
            event_type = event.get("type")

            if event_type == "LOOP_STARTED":
                parsed = _parse_loop_started(event)
                if parsed:
                    trace["loop"] = parsed
                    trace["timestamp"] = event.get("timestamp", "")
            elif event_type == "DECISION_FINALIZED_V1":
                metadata = event.get("metadata", {})
                if isinstance(metadata, dict):
                    trace["finalized"] = metadata
            elif event_type in {"CACHE_HIT", "CACHE_MISS"}:
                trace["lookup"] = str(event_type).replace("CACHE_", "")
            elif event_type == "CACHE_BYPASS":
                metadata = event.get("metadata", {})
                if isinstance(metadata, dict) and metadata.get("stage") == "read":
                    trace["lookup"] = "BYPASS"

    records: List[RequestRecord] = []
    for trace_id, trace in traces.items():
        if "loop" not in trace or "finalized" not in trace or "lookup" not in trace:
            continue
        loop = trace["loop"]
        finalized = FinalizedDecision.from_payload(trace["finalized"])  # type: ignore[arg-type]
        governance_flag_set = _governance_flag_set(finalized.governance_flags)
        records.append(
            RequestRecord(
                trace_id=trace_id,
                timestamp=str(trace.get("timestamp", "")),
                scenario_type=str(loop["scenario_type"]),
                user_input=str(loop["user_input"]),
                cost=float(loop["cost"]),
                days=int(loop["days"]),
                normalized_v1=normalize_v1(str(loop["user_input"])),
                normalized_v2=normalize_v2(str(loop["user_input"])),
                governance_flag_set=governance_flag_set,
                finalized=finalized,
                observed_lookup=str(trace["lookup"]),
            )
        )
    records.sort(key=lambda r: (r.timestamp, r.trace_id))
    return records


def _simulate(records: List[RequestRecord], normalizer: Callable[[RequestRecord], str]) -> Dict[str, object]:
    cache: Dict[tuple, RequestRecord] = {}
    outcomes: List[str] = []
    collisions: Dict[tuple, List[RequestRecord]] = {}

    for record in records:
        key = (
            record.scenario_type,
            normalizer(record),
            _bucket_cost(record.cost),
            _bucket_days(record.days),
            record.governance_flag_set,
        )
        bucket = collisions.setdefault(key, [])
        bucket.append(record)

        if record.observed_lookup == "BYPASS":
            outcomes.append("BYPASS")
            continue

        if key in cache:
            outcomes.append("HIT")
        else:
            outcomes.append("MISS")

        if _write_bypass_reason(record.finalized) is None:
            cache.setdefault(key, record)

    counts = Counter(outcomes)
    total_lookup = counts["HIT"] + counts["MISS"]
    hit_rate = (counts["HIT"] / total_lookup * 100.0) if total_lookup else 0.0
    return {
        "counts": counts,
        "hit_rate": hit_rate,
        "collisions": collisions,
        "outcomes": outcomes,
    }


def _find_risky_collisions(collisions: Dict[tuple, List[RequestRecord]]) -> List[List[RequestRecord]]:
    risky: List[List[RequestRecord]] = []
    for records in collisions.values():
        if len(records) < 2:
            continue
        normalized_locations = set()
        for record in records:
            tokens = set(record.normalized_v2.split())
            locationish = tuple(sorted(t for t in tokens if re.search(r"\d", t) or re.fullmatch(r"[a-z]", t)))
            normalized_locations.add(locationish)
        if len(normalized_locations) > 1:
            risky.append(records)
    return risky


def main() -> int:
    records = _load_records()
    if not records:
        print("No replayable records found.")
        return 1

    observed_counts = Counter(record.observed_lookup for record in records)
    observed_lookup_total = observed_counts["HIT"] + observed_counts["MISS"]
    observed_hit_rate = (observed_counts["HIT"] / observed_lookup_total * 100.0) if observed_lookup_total else 0.0

    sim_v1 = _simulate(records, lambda r: r.normalized_v1)
    sim_v2 = _simulate(records, lambda r: r.normalized_v2)

    print("=== DATASET ===")
    print(f"Replayable requests: {len(records)}")
    print(f"Observed lookups   : HIT={observed_counts['HIT']} MISS={observed_counts['MISS']} BYPASS={observed_counts['BYPASS']}")
    print(f"Observed hit rate  : {observed_hit_rate:.1f}%")

    print("\n=== SIMULATED HIT RATE ===")
    print(
        f"v1: HIT={sim_v1['counts']['HIT']} MISS={sim_v1['counts']['MISS']} "
        f"BYPASS={sim_v1['counts']['BYPASS']} hit_rate={sim_v1['hit_rate']:.1f}%"
    )
    print(
        f"v2: HIT={sim_v2['counts']['HIT']} MISS={sim_v2['counts']['MISS']} "
        f"BYPASS={sim_v2['counts']['BYPASS']} hit_rate={sim_v2['hit_rate']:.1f}%"
    )
    print(f"Delta: +{sim_v2['counts']['HIT'] - sim_v1['counts']['HIT']} hits, +{sim_v2['hit_rate'] - sim_v1['hit_rate']:.1f} pts")

    v1_to_v2 = []
    for record, before, after in zip(records, sim_v1["outcomes"], sim_v2["outcomes"]):
        if before == "MISS" and after == "HIT":
            v1_to_v2.append(record)

    print("\n=== NEW HITS UNLOCKED BY v2 ===")
    if not v1_to_v2:
        print("None")
    else:
        for record in v1_to_v2[:12]:
            print(f"- {record.user_input}")

    risky = _find_risky_collisions(sim_v2["collisions"])
    print("\n=== POTENTIAL LOCATION COLLISIONS ===")
    if not risky:
        print("None detected in replay set.")
    else:
        for group in risky[:10]:
            print("-")
            for record in group:
                print(f"  {record.user_input}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
