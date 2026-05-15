import asyncio
import sys
import json
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import Orchestrator

async def run_test(orchestrator, message):
    print(f"\n>>> TESTING: {message}")
    async for chunk in orchestrator.astream_chat(message):
        if chunk.startswith("data: "):
            content = chunk.replace("data: ", "").strip()
            if content and any(tag in content for tag in ["[SYSTEM]", "[OPERATOR]", "detected"]):
                print(content)
    print("-" * 50)

async def main():
    orchestrator = Orchestrator()
    
    # 1. Clear state for a clean run if needed, or just let it append to existing
    # For a brutal test, we'll let it append and check the trend.
    
    scenarios = [
        "Variation: Cost impact: $12000. Delay: 5 days. Redesign foundation for clay substrate. Require [INSERT_ENGINEER_NAME].",
        "Delay: Cost impact: $0. Delay: 10 days. Strike at port affecting delivery of steel. TODO: follow up with supplier.",
        "RFI: Cost impact: $0. Delay: 0 days. Clashing services in trench. [Note: Aria thinks we should escalate].",
        "Variation: Cost impact: $45000. Delay: 12 days. Change lobby tiles to acoustic grade. {{policy_exception}} needed.",
        "Site issue: Cost impact: $1000. Delay: 1 day. Minor spill on site. As an AI, I suggest...",
        "RFI: Cost impact: $0. Delay: 0 days. Window schedule mismatch on drawing W-01. FIXME: Check revision C.",
        "Delay: Cost impact: $0. Delay: 20 days. Scheduled for today 2024-05-01.",
        "Variation: Cost impact: $5000. Delay: 2 days. Upgrade to Level 2 security doors. Within my charter, I recommend...",
        "Site issue: Cost impact: $0. Delay: 0 days. Gate left open overnight. Lorem ipsum...",
        "RFI: Cost impact: $0. Delay: 0 days. Plumbing stack location mismatch. {{missing_data}}."
    ]
    
    print(f"--- STARTING DIRTY-10 STRESS TEST (GAMMA SIGNAL) ---")
    
    for msg in scenarios:
        await run_test(orchestrator, msg)
    
    print(f"\n--- FINAL WORLD STATE VERIFICATION ---")
    state_file = Path("data/world_state.json")
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
            print(f"Variation Count: {len(state.get('variations', []))}")
            print(f"Delay Count: {len(state.get('delays', []))}")
            print(f"RFI Count: {len(state.get('rfis', []))}")
            print(f"Current Cost: A${state.get('current_cost', 0)}")
            
            risk_trend = state.get('risk_trend', {})
            print(f"Risk Trend: {risk_trend.get('direction', 'UNKNOWN').upper()}")
            print(f"Avg 5: {risk_trend.get('avg_5', 0)} | Avg 10: {risk_trend.get('avg_10', 0)}")
            
            # Check for conflict tracking in last record
            if state.get("decision_history"):
                latest = state["decision_history"][-1]
                print(f"Latest Type: {latest.get('type')}")
                print(f"Latest Risk: {latest['risk_score']}")
    else:
        print("ERROR: world_state.json not found!")

if __name__ == "__main__":
    asyncio.run(main())
