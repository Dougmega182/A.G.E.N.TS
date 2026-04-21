import json
import sqlite3
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.logic.memory_db import DB_PATH

def alter_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all pending jobs
    cursor.execute("SELECT * FROM execution_verification_queue WHERE status='pending'")
    jobs = cursor.fetchall()
    
    if len(jobs) < 2:
        print("Need at least 2 pending jobs. Run log_issue.py first.")
        return
        
    print(f"Found {len(jobs)} jobs. Marking for immediate execution.")
    
    job1, job2 = jobs[0], jobs[1]
    
    # Leave job1 authentic, but execute NOW
    now_ts = datetime.utcnow().isoformat()
    cursor.execute("UPDATE execution_verification_queue SET scheduled_at=? WHERE id=?", (now_ts, job1["id"]))
    
    # Corrupt job2 expected_state (Force DRIFT) and execute NOW
    state2 = json.loads(job2["expected_state"])
    if job2["action_type"] == "gmail_draft":
        state2["subject"] = "Completely Wrong Subject To Force Drift"
    else:
        state2["summary"] = "Completely Wrong Summary"
        
    cursor.execute("UPDATE execution_verification_queue SET expected_state=?, scheduled_at=? WHERE id=?", (json.dumps(state2), now_ts, job2["id"]))
    
    conn.commit()
    conn.close()
    
    print(f"Job 1 ({job1['action_type']}) marked for immediate real VERIFIED test.")
    print(f"Job 2 ({job2['action_type']}) marked for immediate DRIFT test (corrupted subject).")

if __name__ == "__main__":
    alter_db()
