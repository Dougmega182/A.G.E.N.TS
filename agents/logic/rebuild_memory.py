"""
Cold Start Rebuild Utility — Reconstruction from Event Source of Truth.
This script rebuilds the SQLite memory database strictly from events.log.jsonl.
"""

import json
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from agents.logic import memory_db
from agents.logic.event_bus import EVENTS_LOG_PATH

logger = logging.getLogger("rebuild_memory")
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def rebuild(log_path: Path, db_path: Path):
    """
    1. Wipe/Initialize DB
    2. Read JSONL events
    3. Re-persist relevant records
    """
    logger.info(f"Starting Cold Start Rebuild...")
    logger.info(f"Source Log: {log_path}")
    logger.info(f"Target DB: {db_path}")

    REBUILD_COMPONENT = "migration_scripts"

    # 1. Reset Database
    if db_path.exists():
        logger.info("Wiping existing database...")
        os.remove(db_path)
    
    # Initialize schema
    memory_db.DB_PATH = db_path
    # This call to get_conn will trigger schema creation if DB is fresh
    with memory_db._get_conn() as conn:
        logger.info(f"Source Log: {log_path}")
    logger.info(f"Target DB: {db_path}")

    # Set DB Path for memory_db
    from agents.logic import memory_db
    memory_db.DB_PATH = db_path

    # Fresh Start
    try:
        # Load all events first for sorting and validation
        events = []
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        
        # 1. STRICT REPLAY ORDERING (as per user advice)
        events.sort(key=lambda e: e.get("timestamp", ""))
        
        counts = {
            "DECISION_FINALIZED_V1": 0,
            "OWEN_INSIGHT_EXTRACTED": 0
        }

        logger.info("Schema initialized. Starting replay...")
        
        for event in events:
            etype = event.get("type")
            meta = event.get("metadata", {})

            if etype == "DECISION_FINALIZED_V1":
                memory_db.write_decision("migration_scripts", event)
                counts["DECISION_FINALIZED_V1"] += 1

            elif etype == "OWEN_INSIGHT_EXTRACTED":
                memory_db.write_owen_insight(
                    "migration_scripts",
                    insight_type=meta.get("insight_type", "unknown"),
                    summary=meta.get("summary", ""),
                    scenario_type=event.get("scenario"),
                    evidence=meta.get("evidence"),
                    confidence=meta.get("confidence", 0.5),
                    deterministic_key=meta.get("deterministic_key")
                )
                counts["OWEN_INSIGHT_EXTRACTED"] += 1

        logger.info("Rebuild complete.")
        for etype, count in counts.items():
            if count > 0:
                logger.info(f"  - {etype}: {count}")

    except Exception as e:
        logger.error(f"Rebuild failed: {e}")
        raise


if __name__ == "__main__":
    # Default paths
    log_file = EVENTS_LOG_PATH
    db_file = memory_db.DB_PATH
    
    rebuild(log_file, db_file)
