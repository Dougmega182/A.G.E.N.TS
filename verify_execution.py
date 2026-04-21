import time
import json
import logging
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from agents.logic import memory_db, event_bus
from agents.operators.gmail_operator import read_draft, verify_draft_state
from agents.operators.calendar_operator import read_event, verify_event_state

logger = logging.getLogger("agents.verify_execution")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Operator action routing
OPERATOR_MAP = {
    "gmail_draft": {
        "read": read_draft,
        "verify": verify_draft_state,
        "extract_fields": lambda expected, actual: {
            "subject": [expected.get("subject", ""), _get_header(actual, "subject")],
            "to": [expected.get("to", ""), _get_header(actual, "to")]
        }
    },
    "calendar_event": {
        "read": read_event,
        "verify": verify_event_state,
        "extract_fields": lambda expected, actual: {
            "title": [expected.get("summary", ""), actual.get("summary", "")],
            "start": [expected.get("start", {}).get("date") or expected.get("start", {}).get("dateTime"), actual.get("start", {}).get("date") or actual.get("start", {}).get("dateTime")],
            "end": [expected.get("end", {}).get("date") or expected.get("end", {}).get("dateTime"), actual.get("end", {}).get("date") or actual.get("end", {}).get("dateTime")]
        }
    }
}

def _get_header(actual_obj: dict, header_name: str) -> str:
    if not actual_obj: return ""
    headers = actual_obj.get("message", {}).get("payload", {}).get("headers", [])
    for h in headers:
        if h.get("name", "").lower() == header_name.lower():
            return h.get("value", "")
    return ""

def generate_diff(action_type: str, expected_state: dict, actual_obj: dict) -> dict:
    """Generates a clean representation of the drift difference."""
    try:
        extractor = OPERATOR_MAP[action_type]["extract_fields"]
        raw_diff = extractor(expected_state, actual_obj)
        
        # Only keep differing fields
        diff = {}
        for key, vals in raw_diff.items():
            if str(vals[0]).strip().lower() != str(vals[1]).strip().lower():
                diff[key] = vals
        return diff
    except Exception as e:
        return {"error": f"Failed to extract diff: {e}"}

def process_queue():
    jobs = memory_db.get_due_verification_jobs("system_daemon", limit=20)
    if not jobs:
        return 0
        
    logger.info(f"Picked up {len(jobs)} pending verification jobs...")
    
    for job in jobs:
        job_id = job["id"]
        action_type = job["action_type"]
        external_id = job["external_id"]
        attempts = job.get("attempts", 0)
        expected_state = json.loads(job["expected_state"])
        
        if action_type not in OPERATOR_MAP:
            logger.error(f"Unknown action_type {action_type} for job {job_id}")
            memory_db.update_verification_job("system_daemon", job_id, "failed")
            continue
            
        operator = OPERATOR_MAP[action_type]
        logger.info(f"Verifying {action_type} -> ID: {external_id} (Attempt {attempts + 1})")
        
        try:
            # 1. READ-BACK
            actual_obj = operator["read"](external_id)
            
            # IF Object Not Found -> TRANSIENT or TRUE_FAILURE
            if not actual_obj:
                if attempts < 2:
                    new_sched = (datetime.utcnow() + timedelta(seconds=300)).isoformat()
                    memory_db.update_verification_job("system_daemon", job_id, "transient", scheduled_at=new_sched)
                    logger.warning(f"[{job_id}] TRANSIENT FAILURE: External ID not found. Retrying in 5m.")
                else:
                    memory_db.update_verification_job("system_daemon", job_id, "true_failure")
                    event_payload = {
                        "job_id": job_id,
                        "action_type": action_type,
                        "classification": "TRUE_FAILURE",
                        "verification_source": "system_check",
                        "expected": expected_state,
                        "actual": None,
                        "reason": f"{action_type} {external_id} was successfully reported by API but completely missing on verification."
                    }
                    event_bus.emit_event("EXECUTION_DRIFT_DETECTED", "N/A", agent_id="system_daemon", metadata=event_payload)
                    from agents.logic.owen_engine import OwenEngine
                    OwenEngine().ingest_execution_failure(event_payload)
                    logger.error(f"[{job_id}] TRUE FAILURE: External ID completely dropped from reality.")
                continue
                
            # 2. SEMANTIC MATCH
            is_match = operator["verify"](actual_obj, expected_state)
            
            if is_match:
                # If it matched, but required retries, it's a degraded success
                if attempts > 0:
                    status = "degraded_success"
                    classification = "DEGRADED_SUCCESS"
                    logger.warning(f"[{job_id}] DEGRADED SUCCESS: Matched eventually, but required {attempts} retries.")
                else:
                    status = "verified"
                    classification = "VERIFIED_SUCCESS"
                    logger.info(f"[{job_id}] VERIFIED: Reality perfectly matches expectation.")

                memory_db.update_verification_job("system_daemon", job_id, status)
                event_bus.emit_event("EXECUTION_VERIFIED", "N/A", agent_id="system_daemon", metadata={
                    "job_id": job_id,
                    "action_type": action_type,
                    "classification": classification,
                    "verification_source": "system_check"
                })
            else:
                # Semantic mismatch means actual Drift
                diff = generate_diff(action_type, expected_state, actual_obj)
                memory_db.update_verification_job("system_daemon", job_id, "drift_confirmed")
                
                event_payload = {
                    "job_id": job_id,
                    "action_type": action_type,
                    "classification": "DRIFT_CONFIRMED",
                    "verification_source": "system_check",
                    "diff": diff,
                    "expected": expected_state,
                    "reason": "Object exists but properties drifted from exact execution intent."
                }
                
                event_bus.emit_event("EXECUTION_DRIFT_DETECTED", "N/A", agent_id="system_daemon", metadata=event_payload)
                from agents.logic.owen_engine import OwenEngine
                OwenEngine().ingest_execution_failure(event_payload)
                logger.error(f"[{job_id}] DRIFT CONFIRMED: Differences detected -> {diff}")

        except Exception as e:
            logger.exception(f"Unexpected verification crash on {job_id}: {e}")
            
    return len(jobs)

def main():
    logger.info("Starting Execution Drift Daemon...")
    while True:
        try:
            processed = process_queue()
            # Sleep 60 seconds. In our demo, queue items are set to +120s on success.
            # Daemon acts like a lightweight cron.
            time.sleep(30)
        except KeyboardInterrupt:
            logger.info("Shutting down daemon.")
            break
        except Exception as e:
            logger.error(f"Daemon error loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
