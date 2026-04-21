"""
Migration Script — Backfill SQLite decision database from events.log.jsonl.
Used to transition Phase 2 data into the Phase 2.5 structured memory layer.
"""

import json
import sys
from pathlib import Path

# Add project root to path so we can import agents modules
sys.path.append(str(Path(__file__).parent.parent))

from agents.logic import memory_db
from agents.logic.owen_engine import OwenEngine

EVENTS_LOG_PATH = Path("Agent logs/events.log.jsonl")

def migrate():
    if not EVENTS_LOG_PATH.exists():
        print(f"No events log found at {EVENTS_LOG_PATH}")
        return

    print(f"Starting migration from {EVENTS_LOG_PATH}...")
    
    owen = OwenEngine()
    count = 0
    lessons = 0

    with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                event_type = event.get("type")
                
                if event_type in ["DECISION_FINALIZED_V1", "DECISION_MADE"]:
                    # If legacy DECISION_MADE, transform to finalized schema
                    if event_type == "DECISION_MADE":
                        meta = event.get("metadata", {})
                        # Map keys
                        finalized_meta = {
                            "final_decision": meta.get("decision", "UNKNOWN").upper(),
                            "original_decision": meta.get("original_decision", meta.get("decision", "UNKNOWN")).upper(),
                            "was_overridden": meta.get("governance_overridden") == "true",
                            "was_system_forced": meta.get("forced_by_system") == "true",
                            "risk_score": meta.get("risk_score", 0.0),
                            "impact": meta.get("impact", {}),
                            "outcome_score": meta.get("outcome_score", 0),
                            "final_justification": meta.get("justification", ""),
                            "trace_id": event.get("trace_id", "no_trace")
                        }
                        event["metadata"] = finalized_meta
                    
                    # 1. Write to SQLite
                    memory_db.write_decision("migration_scripts", event)
                    
                    # 2. Extract intelligence
                    lesson_id = owen.extract_lesson_from_decision(event)
                    if lesson_id:
                        lessons += 1
                    
                    count += 1
            except Exception as e:
                print(f"Error parsing event: {e}")
                continue

    print(f"Migration complete.")
    print(f"Decisions processed: {count}")
    print(f"Initial lessons/patterns extracted by Owen: {lessons}")

if __name__ == "__main__":
    migrate()
