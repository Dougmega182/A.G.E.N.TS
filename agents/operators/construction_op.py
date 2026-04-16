import json
import os
from datetime import datetime
from pathlib import Path

WORLD_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "world_state.json"
AUDIT_LOG_DIR = Path(__file__).parent.parent.parent / "data" / "audit_logs"

class ConstructionOperator:
    """
    Handles critical state mutations and audit logging for the construction loop.
    'If it didn't update state, it didn't happen.'
    """

    @staticmethod
    def load_state():
        if not WORLD_STATE_PATH.exists():
            return {
                "project_id": "P001",
                "current_cost": 0,
                "current_duration": 0,
                "variations": [],
                "rfis": [],
                "delays": []
            }
        with open(WORLD_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def save_state(state):
        WORLD_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(WORLD_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    @staticmethod
    def handle_tool_call(tool_json):
        """
        Interprets tool_call_v1 and mutates world_state.json
        Example tool_json: { "trace_id": "uuid", "tool_calls": [...] }
        """
        state = ConstructionOperator.load_state()
        from ..logic.event_bus import emit_event

        
        try:
            if isinstance(tool_json, str):
                tool_data = json.loads(tool_json)
            else:
                tool_data = tool_json
            
            trace_id = tool_data.get("trace_id", "N/A")

            for call in tool_data.get("tool_calls", []):
                tool = call.get("tool")
                args = call.get("arguments", {})
                
                if tool == "update_entity":
                    entity_type = args.get("type", "variation") # variation, rfi, delay
                    entity_data = args.get("data", {})
                    
                    # Standard fields
                    cost = entity_data.get("cost", 0)
                    days = entity_data.get("days", 0)
                    status = entity_data.get("status", "pending")
                    
                    entry = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "cost": cost,
                        "days": days,
                        "status": status,
                        "reason": entity_data.get("reason", "No reason provided"),
                        "risk_score": args.get("risk_score", 0)
                    }

                    # Route to correct bucket
                    state_key = entity_type + "s" # variations, rfis, delays
                    state.setdefault(state_key, []).append(entry)

                    if status == "approved" and entity_type == "variation":
                        state["current_cost"] += cost
                        state["current_duration"] += days

            ConstructionOperator.save_state(state)
            print(f"[OPERATOR] State updated.")
            
            # Emit mutation + execution confirmation events
            mutation_metadata = {
                "scenario": entity_type if 'entity_type' in locals() else "unknown",
                "status": status if 'status' in locals() else "unknown"
            }
            emit_event("STATE_MUTATED", trace_id, metadata=mutation_metadata)
            emit_event("ACTION_EXECUTED", trace_id, metadata=mutation_metadata)
            return True

        except Exception as e:
            print(f"[OPERATOR ERROR] Failed to update state: {e}")
            return False

    @staticmethod
    def log_to_sentinel(step, agent, input_data, output_data):
        """
        Writes a formal audit entry for Sentinel to process or log.
        """
        AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "step": step,
            "agent": agent,
            "input": input_data,
            "output": output_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        log_file = AUDIT_LOG_DIR / f"sentinel_{datetime.utcnow().date()}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[SENTINEL] Logged step: {step} by {agent}")
