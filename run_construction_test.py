import asyncio
import sys
import json
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import Orchestrator

async def main():
    orchestrator = Orchestrator()
    
    # Input defined by the user for High Risk testing (Risk Score: 0.9)
    user_input = "Variation: +20k, +5 days, heavy drainage issue"
    
    print(f"--- STARTING SAFETY & GOVERNANCE TEST (PHASE 2.1) ---")
    print(f"Input: {user_input}\n")
    
    async for chunk in orchestrator.run_construction_loop(user_input):
        if chunk.startswith("data: "):
            content = chunk.replace("data: ", "").strip()
            if content:
                print(content)
    
    print(f"\n--- VERIFYING SAFETY GATES & ESCALATION ---")
    state_file = Path("data/world_state.json")
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
            print(f"Project ID: {state['project_id']}")
            print(f"Current Cost: A${state['current_cost']}")
            
            if state.get("decision_history"):
                latest = state["decision_history"][-1]
                print(f"Latest Risk Score: {latest['risk_score']}")
                print(f"Latest Decision: {latest['decision']}")
                
                # Verify Hard Safety Gate
                if latest['risk_score'] >= 0.85:
                    if latest['decision'] in ["rejected", "escalated"]:
                        print(f"SUCCESS: Safety Gate enforced. High risk variation was {latest['decision']}.")
                    else:
                        print(f"FAILURE: Safety Gate bypassed! High risk variation was {latest['decision']}.")
                
                # Check for Conflict Flag in justification
                if "CONFLICT DETECTED" in latest['justification']:
                    print("AUDIT: Conflict between Sentinel and Aria was correctly flagged.")
                else:
                    print("AUDIT: No conflict detected / Sentinel and Aria agreed.")
    else:
        print("ERROR: world_state.json not found!")

if __name__ == "__main__":
    asyncio.run(main())
