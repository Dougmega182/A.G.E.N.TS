import subprocess
import time
import json
import os

# Scenarios to build clusters and test Layer 1 boundaries
scenarios = [
    # Cluster: Rain Delay (Testing connectors and plurals)
    ("Rain delay to slab pour", 3000, 1),
    ("Rain delay for slab pour", 3000, 1),
    ("Rain delays to slab pour", 3000, 1),
    ("Rain delay on slab pour", 3000, 1), # Potential HIT if exact match exists
    
    # Cluster: Material (Rebar)
    ("Late delivery of rebar for Level 3", 5000, 2),
    ("Late delivery of rebar - Level 3", 5000, 2),
    ("Rebar delivery delay on Level 3", 5000, 2),
    ("Delivery of rebar delayed for Level 3", 5000, 2),
    
    # Cluster: Subcontractor No-Show
    ("Plumbing sub no-show", 0, 1),
    ("Plumber failed to show up", 0, 1),
    ("Plumbing subcontractor no-show", 0, 1),
    ("No-show from plumbing subcontractor", 0, 1),
    
    # Cluster: Design Conflict (HVAC)
    ("Wall clash with HVAC duct", 0, 0),
    ("HVAC ducting clash with wall", 0, 0),
    ("Partition wall clash with ducting", 0, 0),
    ("Clash between partition wall and HVAC", 0, 0),
    
    # Varied Singletons (Domain Variation)
    ("Broken window in site office", 200, 0),
    ("Graffiti on perimeter hoarding", 1000, 0),
    ("Oversize delivery permit required", 450, 0),
    ("Temporary power outage on Level 2", 0, 0),
    ("Water leak in basement", 2500, 0),
    ("Failed concrete cylinder test", 0, 0),
    ("Missing site safety induction records", 0, 0),
    ("Faulty lift motor in Hoist 1", 5000, 1),
    ("Damaged scaffolding on Grid 4", 1200, 0),
    ("Theft of copper piping from Level 4", 8000, 1),
    ("Tree root obstruction in drain line", 3500, 2),
    ("Inaccurate survey peg at NW corner", 0, 1),
    ("Minor scratch on architectural glazing", 0, 0),
    ("Incomplete fire spray on beam B-3", 1500, 0)
]

def run_scenario(issue, cost, days):
    print(f"\n[BATCH] STARTING: '{issue}'")
    cmd = ["python", "log_issue.py", issue, str(cost), str(days)]
    # Providing 'y' for all prompts + a dummy feedback note
    responses = "y\ny\ny\ny\nbatch observation v2\n"
    
    try:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(input=responses, timeout=300)
        
        # Check for HIT in stdout
        if "CACHE_HIT" in stdout:
            print(f"[BATCH] RESULT: HIT")
        elif "CACHE_MISS" in stdout:
            print(f"[BATCH] RESULT: MISS")
        elif "CACHE_BYPASS" in stdout:
            print(f"[BATCH] RESULT: BYPASS")
        else:
            print(f"[BATCH] RESULT: COMPLETED (Unknown status)")
            
    except subprocess.TimeoutExpired:
        process.kill()
        print(f"[BATCH] RESULT: TIMEOUT")
    except Exception as e:
        print(f"[BATCH] RESULT: ERROR - {e}")

if __name__ == "__main__":
    print(f"Starting Batch Observation Run (30 scenarios)...")
    start_time = time.time()
    for i, (issue, cost, days) in enumerate(scenarios):
        print(f"\n--- Progress: {i+1}/30 ---")
        run_scenario(issue, cost, days)
    
    total_time = time.time() - start_time
    print(f"\nBatch completed in {total_time/60:.2f} minutes.")
