import json
from pathlib import Path

WORLD_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "world_state.json"

def get_recent_decisions(n: int = 5) -> list:
    """Fetches the last n entries from decision_history in world_state.json."""
    if not WORLD_STATE_PATH.exists():
        return []
    
    try:
        with open(WORLD_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
            history = state.get("decision_history", [])
            return history[-n:]
    except Exception as e:
        print(f"[MEMORY] Error loading history: {e}")
        return []
