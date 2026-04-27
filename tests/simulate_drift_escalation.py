import asyncio
import json
import sqlite3
import sys
import random
import string
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator
from agents.preflight_validator import decide_request, execute_task, get_request
from agents.logic.memory_db import DB_PATH
from verify_execution import process_queue

def inject_noise(state: dict) -> dict:
    """Inject randomized noise into the state to simulate messy real-world drift."""
    noise_type = random.choice(["field_drop", "corruption", "none", "none"])
    
    if noise_type == "field_drop":
        # Randomly drop a required field
        field_to_drop = random.choice(["subject", "to", "body"])
        if field_to_drop in state:
            del state[field_to_drop]
            print(f"  [NOISE] Injected noise: DROPPED FIELD '{field_to_drop}'")
            
    elif noise_type == "corruption":
        # Simulate encoding/corruption issues
        if "subject" in state:
            subj = list(state["subject"])
            for _ in range(2):
                idx = random.randint(0, len(subj)-1)
                subj[idx] = random.choice(string.punctuation)
            state["subject"] = "".join(subj)
            print(f"  [NOISE] Injected noise: CORRUPTED SUBJECT")
    
    return state

def force_drift_in_db(is_degraded: bool = False, force_false_verified: bool = False):
    """Mutate pending verification jobs to simulate drift or degraded success."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM execution_verification_queue WHERE status='pending'")
    jobs = cursor.fetchall()
    
    for job in jobs:
        if force_false_verified:
            # Simulate API lying (returning success when it actually failed)
            print("  [NOISE] Injected noise: FORCED FALSE VERIFIED (API Lying)")
            cursor.execute("UPDATE execution_verification_queue SET status = 'verified' WHERE id=?", (job["id"],))
            continue

        if is_degraded:
            # Simulate degraded success by increasing attempts
            cursor.execute("UPDATE execution_verification_queue SET attempts = 1 WHERE id=?", (job["id"],))
        else:
            # Force semantic drift by messing up the expected payload
            state = json.loads(job["expected_state"])
            
            # Apply Noise
            state = inject_noise(state)
            
            # Application-level drift logic
            if job["action_type"] == "gmail_draft":
                if "subject" in state:
                    state["subject"] += " [DRIFT_INJECTED]"
                else:
                    state["subject"] = "Completely New Subject"
            
            cursor.execute("UPDATE execution_verification_queue SET expected_state=? WHERE id=?", (json.dumps(state), job["id"]))
    
    conn.commit()
    conn.close()

results_log = []

async def run_turn(run_num: int, input_text: str, drift_type: str = "drift"):
    """Run a single iteration of the loop."""
    print(f"\n{'='*60}")
    print(f"RUN #{run_num}: {drift_type.upper()}")
    print(f"{'='*60}")
    
    orchestrator = Orchestrator()
    request_id = None
    final_metadata = {}
    
    print("Orchestrating (LLM executing)...")
    async for chunk in orchestrator.astream_chat(input_text):
        if chunk.startswith("data: "):
            content = chunk.replace("data: ", "").strip()
            if "Request ID: APR-" in content:
                import re
                match = re.search(r"Request ID: (APR-[A-Z0-9]+)", content)
                if match:
                    request_id = match.group(1)
            
            # Show Reliability Alerts if they appear
            if "SYSTEM RELIABILITY ALERTS" in content:
                print(f"\n[INTELLIGENCE ALERT DETECTED IN BRIEFING]:\n{content}\n")
            
    if not request_id:
        print("[!] No request ID found. System auto-escalated.")
        # Retrieve the escalated decision
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT final_decision, primary_override_reason, justification, metadata FROM decisions ORDER BY timestamp DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        
        if row:
            meta = json.loads(row["metadata"])
            results_log.append({
                "run": run_num,
                "type": drift_type,
                "decision": row["final_decision"],
                "base_conf": meta.get("confidence_score", 0),
                "penalty": meta.get("confidence_penalty", 0),
                "threshold": meta.get("confidence_threshold", 0.6),
                "dpi": meta.get("drift_pressure_index", 0),
                "reason": row["primary_override_reason"]
            })
            print(f"> DECISION: {row['final_decision']}")
            print(f"> REASON  : {row['primary_override_reason']}")
            print(f"> DPI     : {meta.get('drift_pressure_index', 0):.2f}")
            
        return "escalated"
        
    request = get_request(request_id)
    intent = request.get("original_action_intent", {})
    metadata = intent.get("metadata", {})
    params = intent.get("parameters", {})
    
    # Decoded from metadata in decision_finalizer
    dpi = metadata.get("drift_pressure_index", 0)
    penalty = metadata.get("confidence_penalty", 0)
    threshold = metadata.get("confidence_threshold", 0.6)
    base_conf = metadata.get("confidence_score", 1.0) # Original Aria score

    results_log.append({
        "run": run_num,
        "type": drift_type,
        "decision": metadata.get("final_decision", "UNKNOWN"),
        "base_conf": base_conf,
        "penalty": penalty,
        "threshold": threshold,
        "dpi": dpi,
        "reason": "N/A"
    })

    print(f"Decision:  {metadata.get('final_decision')}")
    print(f"DPI:       {dpi:.2f} (Penalty: {penalty:.2f} / Threshold: {threshold:.2f})")

    if metadata.get("final_decision") == "ESCALATE":
        return "escalated"
        
    print(f"Approving {request_id} for execution...")
    decide_request(request_id, "approve", decided_by="cli_gatekeeper", reason="CLI Approval")
    
    result = await execute_task(request_id)
    print(f"Execution completed. Result: {result.get('status')}")
    
    # Force DB mutation
    force_false = (random.random() < 0.1) # 10% chance of API lying
    if drift_type == "clean":
        pass
    elif drift_type == "degraded":
        force_drift_in_db(is_degraded=True)
    else:
        force_drift_in_db(force_false_verified=force_false)
        
    # Run Verifier
    print("Running Verification Daemon...")
    processed = process_queue()
    print(f"Daemon processed {processed} jobs.")
    
    return "executed"

async def main():
    # Clear history
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM owen_negative_patterns")
    conn.execute("DELETE FROM execution_verification_queue")
    conn.execute("DELETE FROM decisions")
    conn.commit()
    conn.close()
    
    input_text = "Variation: +$12000, +2 days, Concrete delay slab. Notify pmo@construction-corp.com"
    
    # Run sequence
    sequence = ["clean", "drift", "drift", "degraded", "drift", "drift"]
    
    for i, d_type in enumerate(sequence, 1):
        res = await run_turn(i, input_text, d_type)
        if res == "escalated":
            # If we hit auto-escalation, we might want to see if one more run stays blocked
            if i < len(sequence):
                print("\n[MONEY TEST] Auto-escalation reached! Running one final check to confirm persistent blockage...")
                await run_turn(i+1, input_text, sequence[i])
            break

    # Final Table Output
    print("\n\n" + "="*80)
    print(f"{'RUN':<5} | {'TYPE':<10} | {'DECISION':<10} | {'BASE':<6} | {'PENALTY':<7} | {'THR':<5} | {'DPI':<5}")
    print("-" * 80)
    for r in results_log:
        print(f"{r['run']:<5} | {r['type']:<10} | {r['decision']:<10} | {r['base_conf']:<6.2f} | {r['penalty']:<7.2f} | {r['threshold']:<5.2f} | {r['dpi']:<5.2f}")
    print("="*80)
    print("DPI (Drift Pressure Index) = Penalty / Threshold. Higher index = greater system skepticism.")

if __name__ == "__main__":
    asyncio.run(main())
