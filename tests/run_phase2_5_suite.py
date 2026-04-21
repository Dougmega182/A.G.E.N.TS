"""
SYSTEM INTEGRITY GATE: Phase 2.5 Test Suite Runner
Goal: Execute all behavioral tests in sequence and enforce the Integrity Clearance sign-off.
"""

import subprocess
import sys
import time
from pathlib import Path

TESTS = [
    "tests/test_memory_contract.py",
    "tests/test_event_db_sync.py",
    "tests/test_owen_determinism.py",
    "tests/test_owen_memory_drift.py",
    "tests/test_governance_override.py",
    "tests/test_full_construction_loop.py",
    "tests/test_replay_consistency.py",
    "tests/test_loop_latency.py",
    "tests/test_partial_failure_resilience.py"
]

def run_suite():
    print("="*60)
    print("      A.G.E.N.T.S. SYSTEM INTEGRITY GATE (Phase 2.5)")
    print("="*60)
    print(f"Targeting: Memory Integrity, Owen Intelligence, Governance enforcement.")
    print("-"*60)

    failed = []
    skipped = []
    
    start_time = time.time()

    for test_path in TESTS:
        print(f"RUNNING: {test_path}...", end="", flush=True)
        
        try:
            # Use same python executable as current process
            result = subprocess.run(
                [sys.executable, test_path],
                capture_output=True,
                text=True,
                timeout=60 # 1 minute per test max
            )
            
            if result.returncode == 0:
                print(" [PASS]")
            else:
                print(" [FAIL]")
                print(f"\n--- ERROR OUTPUT ({test_path}) ---")
                print(result.stdout)
                print(result.stderr)
                failed.append(test_path)
                # Stop on first failure as per user recommendation
                break
                
        except subprocess.TimeoutExpired:
            print(" [TIMEOUT]")
            failed.append(test_path)
            break
        except Exception as e:
            print(f" [ERROR] {e}")
            failed.append(test_path)
            break

    duration = time.time() - start_time
    print("-"*60)
    print(f"Suite completed in {duration:.2f} seconds.")
    
    if not failed:
        print("\n" + "#"*60)
        print("    INTEGRITY CLEARANCE: PASS")
        print("    STATUS: System is safe for Phase 3 External Integration.")
        print("#"*60 + "\n")
        sys.exit(0)
    else:
        print("\n" + "!"*60)
        print("    INTEGRITY CLEARANCE: FAIL")
        print(f"    FAILED TEST: {failed[0]}")
        print("    BLOCKER: Fixed architecture drift before proceeding.")
        print("!"*60 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    run_suite()
