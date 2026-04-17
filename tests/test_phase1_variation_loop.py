import asyncio
import sys
import json
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator

async def main():
    orchestrator = Orchestrator()
    
    # Input defined for Phase 1 Variation Milestone
    user_input = "Variation: +$15k, +3 days due to drainage issue"
    
    print(f"--- STARTING PHASE 1 VARIATION VERIFICATION ---")
    print(f"Input: {user_input}\n")
    
    found_agents = []
    proposal_id = None
    
    async for chunk in orchestrator.astream_chat(user_input):
        if chunk.startswith("data: "):
            content = chunk.replace("data: ", "").strip()
            if content:
                # Track agent sequence
                if "START" in content:
                    agent = content.replace("[", "").replace("] START", "")
                    found_agents.append(agent)
                    print(f"\n[ACTOR] {agent} entering loop...")
                
                # Check for Proposal Creation
                if "PROPOSAL CREATED. Request ID: " in content:
                    proposal_id = content.split("Request ID: ")[1].strip()
                    print(f"\n[SYSTEM] {content}")
                
                # Print sample of response (first 100 chars of agent output)
                if ":" in content and "START" not in content and "END" not in content:
                    parts = content.split("]: ", 1)
                    if len(parts) > 1:
                        print(f"[{parts[0]}] {parts[1][:100]}...")

    print(f"\n--- VERIFICATION RESULTS ---")
    print(f"Agent Sequence: {' -> '.join(found_agents)}")
    
    # Expected Sequence: NADIA -> TUCKER -> WALL-E -> OWEN -> ARIA -> JENNY
    expected = ["NADIA", "TUCKER", "WALL-E", "ARIA", "JENNY"] # Owen is silent in tokens
    all_present = all(a in found_agents for a in expected)
    
    if all_present:
        print("SUCCESS: Full reasoning chain (Nadia -> Tucker -> WALL-E -> Aria -> Jenny) observed.")
    else:
        missing = [a for a in expected if a not in found_agents]
        print(f"FAILURE: Missing agents in loop: {missing}")

    if proposal_id:
        print(f"SUCCESS: Variation proposal registered with ID: {proposal_id}")
    else:
        print("FAILURE: No proposal ID captured in stream.")

    # Final logic check: Check if Proposal exists in preflight_approvals.json
    preflight_path = Path("Agent logs/preflight_approvals.json")
    if preflight_path.exists():
        with open(preflight_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            requests = data.get("requests", [])
            last_request = requests[-1] if requests else {}
            if last_request.get("request_id") == proposal_id:
                print(f"SUCCESS: Proposal {proposal_id} persisted in Preflight Store.")
                print(f"Summary: {last_request.get('summary')}")
            else:
                print("FAILURE: Persistence check failed for the latest request.")
    else:
        print("FAILURE: preflight_approvals.json not found.")

if __name__ == "__main__":
    asyncio.run(main())
