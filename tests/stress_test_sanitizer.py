import asyncio
import json
import sys
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from agents.logic.sanitizer import ContractSanitizer

async def stress_test_sanitizer():
    print("🧪 STRESS TESTING HARDENED SANITIZER")
    
    # 1. Test context-aware year rule
    # historical (should pass)
    hist_raw = """
    THINKING: Referencing the 2023 foundation report.
    ARTIFACT: {
        "justification": "The 2023 report indicated stable soil."
    }
    """
    _, success, repaired, violations = ContractSanitizer.process(hist_raw, "test")
    print(f"Historical Year Test: {'PASS' if success and not violations else 'FAIL'} (Repaired: {repaired})")
    
    # future/hallucinated (should fail/repair)
    halluc_raw = """
    THINKING: Scheduling for next year.
    ARTIFACT: {
        "justification": "The next review will be today 2024-10-27."
    }
    """
    obj, success, repaired, violations = ContractSanitizer.process(halluc_raw, "test")
    print(f"Hallucinated Year Test: success={success}, repaired={repaired}, violations={violations}")

    # 2. Test ARTIFACT parser hardening (multiple blocks)
    double_artifact = """
    THINKING: Stage 1.
    ARTIFACT: {"meta": "wrong"}
    THINKING: Stage 2.
    ARTIFACT: {"to": "dale@example.com", "subject": "Real", "body": "Clean"}
    """
    obj, success, repaired, violations = ContractSanitizer.process(double_artifact, "email_draft_v1")
    print(f"Double ARTIFACT Test: {'PASS' if success and obj.get('subject') == 'Real' else 'FAIL'}")

    # 3. Test Mandatory 2-stage structure (missing THINKING)
    missing_thinking = """
    ARTIFACT: {"goal": "no thinking"}
    """
    _, success, repaired, violations = ContractSanitizer.process(missing_thinking, "plan_v1")
    print(f"Missing THINKING Test: {'PASS' if not success and 'mandatory' in str(violations) else 'FAIL'}")

if __name__ == "__main__":
    asyncio.run(stress_test_sanitizer())
