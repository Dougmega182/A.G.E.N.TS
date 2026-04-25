import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


EVENTS_PATH = Path("Agent logs/events.log.jsonl")
PATTERN_PATH = Path("Agent logs/pattern_registry.log.jsonl")


def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-04-22", help="ISO date prefix to analyze")
    args = parser.parse_args()

    events = [r for r in load_jsonl(EVENTS_PATH) if str(r.get("timestamp", "")).startswith(args.date)]
    patterns = [r for r in load_jsonl(PATTERN_PATH) if str(r.get("timestamp", "")).startswith(args.date)]

    outcome_updates = [r for r in patterns if r.get("record_type") == "outcome_quality_update"]
    pattern_rows = [r for r in patterns if r.get("record_type") == "pattern_observed"]

    traces = {}
    approval_to_trace = {}

    for row in pattern_rows:
        traces.setdefault(row["trace_id"], {
            "scenario": row.get("scenario", "unknown"),
            "sample_input": row.get("sample_input", ""),
            "decision": row.get("workflow_shape", {}).get("final_decision", ""),
            "pattern_logged": True,
            "approval_decided": False,
            "approved": False,
            "execution_attempted": False,
            "outcome_finalized": False,
            "request_ids": set(),
        })

    for row in events:
        trace_id = row.get("trace_id")
        event_type = row.get("type")
        meta = row.get("metadata", {})

        if event_type == "DECISION_FINALIZED_V1":
            traces.setdefault(trace_id, {
                "scenario": row.get("scenario", "unknown"),
                "sample_input": "",
                "decision": meta.get("final_decision", ""),
                "pattern_logged": False,
                "approval_decided": False,
                "approved": False,
                "execution_attempted": False,
                "outcome_finalized": False,
                "request_ids": set(),
            })

        if event_type in {"APPROVAL_REQUESTED", "APPROVAL_DECIDED", "LOOP_COMPLETE"} and meta.get("request_id"):
            approval_to_trace[meta["request_id"]] = trace_id
            if trace_id in traces:
                traces[trace_id]["request_ids"].add(meta["request_id"])

        if event_type == "APPROVAL_DECIDED" and trace_id in traces:
            traces[trace_id]["approval_decided"] = True
            traces[trace_id]["approved"] = str(meta.get("decision", "")).lower() == "approved"

        if event_type in {"EXECUTION_STARTED", "EXTERNAL_ACTION_EXECUTED", "EXECUTION_FAILED"} and trace_id in traces:
            traces[trace_id]["execution_attempted"] = True

        if event_type in {"TASK_EXECUTION_STARTED", "TASK_EXECUTION_COMPLETED", "TASK_EXECUTION_FAILED"}:
            original_trace = approval_to_trace.get(meta.get("request_id")) or approval_to_trace.get(trace_id)
            if original_trace in traces:
                traces[original_trace]["execution_attempted"] = True

        if event_type == "POST_EXECUTION_REVIEW_V1" and trace_id in traces:
            traces[trace_id]["outcome_finalized"] = True

    for row in outcome_updates:
        trace_id = row.get("trace_id")
        if trace_id in traces:
            traces[trace_id]["outcome_finalized"] = True

    stage_counter = Counter()
    missing_combo_counter = Counter()
    report_rows = []

    for trace_id, data in traces.items():
        stage_counter["decision_created"] += 1
        if data["pattern_logged"]:
            stage_counter["pattern_logged"] += 1
        if data["approval_decided"]:
            stage_counter["approval_decided"] += 1
        if data["execution_attempted"]:
            stage_counter["execution_attempted"] += 1
        if data["outcome_finalized"]:
            stage_counter["outcome_finalized"] += 1

        missing = []
        if not data["pattern_logged"]:
            missing.append("PATTERN_LOGGED")
        if not data["approval_decided"]:
            missing.append("APPROVAL_DECIDED")
        if data["approved"] and not data["execution_attempted"]:
            missing.append("EXECUTION_ATTEMPTED")
        if data["approved"] and not data["outcome_finalized"]:
            missing.append("OUTCOME_FINALIZED")

        if missing:
            missing_combo_counter[tuple(missing)] += 1
            report_rows.append({
                "trace_id": trace_id,
                "scenario": data["scenario"],
                "decision": data["decision"],
                "missing": missing,
                "sample_input": data["sample_input"],
            })

    print(f"Trace completeness report for {args.date}")
    print()
    print(f"Total decision traces: {len(traces)}")
    print(f"DECISION_CREATED: {stage_counter['decision_created']}/{len(traces)}")
    print(f"PATTERN_LOGGED: {stage_counter['pattern_logged']}/{len(traces)}")
    print(f"APPROVAL_DECIDED: {stage_counter['approval_decided']}/{len(traces)}")
    approved_count = sum(1 for d in traces.values() if d["approved"])
    print(f"EXECUTION_ATTEMPTED (approved only): {stage_counter['execution_attempted']}/{approved_count}")
    print(f"OUTCOME_FINALIZED (approved only): {stage_counter['outcome_finalized']}/{approved_count}")
    print()
    print("Missing stage combinations:")
    for combo, count in missing_combo_counter.most_common():
        print(f"- {', '.join(combo)}: {count}")
    print()
    print("Per-trace gaps:")
    for row in sorted(report_rows, key=lambda r: (r["scenario"], r["trace_id"])):
        print(f"- {row['trace_id']} | {row['scenario']} | {row['decision']} | missing={', '.join(row['missing'])}")
        print(f"  {row['sample_input'][:160]}")


if __name__ == "__main__":
    main()
