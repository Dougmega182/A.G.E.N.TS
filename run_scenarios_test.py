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
        "Variation: +10k, +2 days, structural change",
        "Delay: 3 days, heavy rain",
        "RFI: missing footing detail"
    ]
    
    print(f"--- STARTING MULTI-SCENARIO PLATFORM TEST (PHASE 3) ---")
    
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
            print(f"Current Cost: A${state['current_cost']}")
            print(f"Risk Trend: {state['risk_trend']['direction'].upper()}")
            print(f"Avg 5: {state['risk_trend']['avg_5']} | Avg 10: {state['risk_trend']['avg_10']}")
            
            # Check for conflict tracking in last record
            if state.get("decision_history"):
                latest = state["decision_history"][-1]
                print(f"Latest Type: {latest.get('type')}")
                print(f"Latest Risk: {latest['risk_score']}")
    else:
        print("ERROR: world_state.json not found!")

if __name__ == "__main__":
    asyncio.run(main())
