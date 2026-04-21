"""
Verification Script — Verify Phase 2.5 Memory Infrastructure.
Tests SQLite integrity, Owen's briefing generation, and boundary contract.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.logic import memory_db
from agents.logic.owen_engine import OwenEngine
from agents.logic.memory_contract import MemoryBoundaryViolation, MemoryDomain

def verify():
    print("--- 1. Boundary Contract Test ---")
    try:
        memory_db.write_decision("illegal_component", {})
        print("FAIL: Boundary contract did not block illegal writer.")
    except MemoryBoundaryViolation as e:
        print(f"PASS: {e}")
    except Exception as e:
         print(f"FAIL: Unexpected error in boundary test: {e}")

    print("\n--- 2. Database Content Test ---")
    decisions = memory_db.read_decisions("orchestrator", limit=5)
    print(f"Found {len(decisions)} decisions in SQLite.")
    for d in decisions:
        print(f" - [{d['timestamp']}] {d['scenario']}: {d['final_decision']} (Trace: {d['trace_id'][:8]})")

    print("\n--- 3. Owen Briefing Test ---")
    owen = OwenEngine()
    briefing = owen.generate_intelligence_briefing("variation")
    print(f"Owen Briefing for 'variation':")
    print(f" - Sample size: {briefing['metrics']['sample_size']}")
    print(f" - Net score: {briefing['metrics']['net_outcome_score']}")
    
    prompt_text = owen.format_briefing_for_prompt(briefing)
    print("\nPrompt Text Preview:")
    print(prompt_text)

if __name__ == "__main__":
    verify()
