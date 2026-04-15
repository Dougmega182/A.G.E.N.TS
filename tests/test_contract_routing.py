import asyncio
import os
import sys
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator
from agents.roster import AGENTS, fast

async def verify_contract_routing():
    orc = Orchestrator()
    
    test_cases = [
        {
            "name": "Morning Brief (Jenny)",
            "message": "Jenny, get me my morning brief.",
            "contract_expected": True,
            "required_format": "morning_brief_v1"
        },
        {
            "name": "Email Draft",
            "message": "Draft an email to Bob about the contract.",
            "contract_expected": True,
            "required_format": "email_draft_v1"
        },
        {
            "name": "Plan Creation",
            "message": "Plan: Upgrade the Ollama nodes.",
            "contract_expected": True,
            "required_format": "plan_v1"
        },
        {
            "name": "Tool Call",
            "message": "Tool: list directory agents",
            "contract_expected": True,
            "required_format": "tool_call_v1"
        },
        {
            "name": "Normal Chat (Aria)",
            "message": "Aria, what is our strategy?",
            "contract_expected": False,
            "required_format": None
        }
    ]
    
    print("\n--- CONTRACT ROUTING VERIFICATION ---")
    
    for case in test_cases:
        print(f"\nTEST CASE: {case['name']}")
        print(f"MESSAGE: {case['message']}")
        
        # We don't actually need to wait for the LLM to respond if we just want to see the routing prints
        # But we'll run it and catch the output.
        # Note: This will actually call the local Ollama if running live.
        
        try:
            async for chunk in orc.astream_chat(case['message']):
                # We just need to trigger the logic
                if "CONNECTION ERROR" in chunk:
                    print(f"  [NOTE] {chunk.strip()}")
                pass
        except Exception as e:
            print(f"  [ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(verify_contract_routing())
