import json
from pathlib import Path

WORLD_STATE_PATH = Path("data/world_state.json")

def migrate():
    if not WORLD_STATE_PATH.exists():
        print("No world_state.json found. Nothing to migrate.")
        return
    
    with open(WORLD_STATE_PATH, "r", encoding="utf-8") as f:
        state = json.load(f)
    
    # Keys to remove
    to_remove = ["decision_history", "risk_trend", "approved_variations", "rejected_variations"]
    for key in to_remove:
        if key in state:
            state.pop(key)
            print(f"Removed legacy key: {key}")
            
    with open(WORLD_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    print("Migration complete. world_state.json is now clean.")

if __name__ == "__main__":
    migrate()
