import sqlite3
from pathlib import Path

# Try both locations
PATHS = [Path("agents_memory.db"), Path("data/agents_memory.db")]

def check_db():
    for DB_PATH in PATHS:
        print(f"\n--- Checking {DB_PATH} ---")
        if not DB_PATH.exists():
            print("  ❌ Not found.")
            continue
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"  Tables: {tables}")
        
        if ('decision_cache',) in [t for t in tables]:
            cursor.execute("SELECT count(*) FROM decision_cache")
            count = cursor.fetchone()[0]
            print(f"  decision_cache count: {count}")
            
            cursor.execute("SELECT cache_key, scenario_type, normalized_issue, policy_version FROM decision_cache LIMIT 5")
            rows = cursor.fetchall()
            for r in rows:
                print(f"    - {r}")
        else:
            print("  ❌ decision_cache table not found.")
            
        conn.close()

if __name__ == "__main__":
    check_db()
