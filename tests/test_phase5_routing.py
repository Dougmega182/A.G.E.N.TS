import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator

def test_routing():
    orc = Orchestrator()
    
    test_cases = [
        {
            "input": "Hey Owen, analyze the last week's traffic data.",
            "expected_contains": ["owen"]
        },
        {
            "input": "Marcus, veto any spending over $1000.",
            "expected_contains": ["marcus"]
        },
        {
            "input": "I'm feeling very overwhelmed and scattered today.",
            "expected_contains": ["eli"]
        },
        {
            "input": "What is our 5-year vision for the A.G.E.N.T.S. network?",
            "expected_contains": ["aria", "nadia"]
        }
    ]
    
    print("\n--- A.G.E.N.T.S. ROUTING VERIFICATION ---")
    
    for case in test_cases:
        print(f"\nQUERY: {case['input']}")
        routed = orc._route_message(case['input'])
        print(f"ROUTED TO: {routed}")
        
        # Check if at least one expected agent is in the routed list
        passed = any(expected in routed for expected in case['expected_contains'])
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"STATUS: {status}")

if __name__ == "__main__":
    test_routing()
