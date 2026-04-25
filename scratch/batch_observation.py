import subprocess
import time

issues = [
    ("Broken guardrail at Level 5 stairs", 500, 0),
    ("Late delivery of structural steel beams", 2000, 2),
    ("Rain delay on slab pour", 3000, 1),
    ("Electrical subcontractor no-show for rough-in", 0, 1),
    ("Discovery of unknown underground utility pipe", 10000, 4),
    ("Spalling concrete on Column C-12", 4500, 1),
    ("Client request to move partition wall 200mm", 1500, 0),
    ("Asbestos found in demolition debris", 25000, 7),
    ("Sprinkler pipe clashing with air-con duct", 0, 0),
    ("Broken guardrail on Level 5 stairs", 500, 0),
]

for issue, cost, days in issues:
    print(f"\n--- RUNNING: {issue} ---")
    # Using 'log_issue.py' with auto-approval logic bypassed (we will approve manually or via stdin)
    # Actually, we can provide stdin 'y\ny\ny\ny\nbatch run' for each.
    
    cmd = ["python", "log_issue.py", issue, str(cost), str(days)]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
    
    # We provide the responses
    # Note: Approval thresholds might differ, so we just spam 'y'
    responses = "y\ny\ny\ny\nbatch observation run\n"
    
    try:
        # Wait a bit for the prompt
        # In reality, the orchestrator and agents take ~30-60s
        # process.communicate(input=responses) 
        # But we want to see output? No, just run it.
        # Actually communicate is better.
        stdout, stderr = process.communicate(input=responses, timeout=300)
        print(f"--- FINISHED: {issue} ---")
    except subprocess.TimeoutExpired:
        process.kill()
        print(f"--- TIMEOUT: {issue} ---")
    except Exception as e:
        print(f"--- ERROR: {e} ---")
