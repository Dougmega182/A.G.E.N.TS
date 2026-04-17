import json
import os
from datetime import datetime
from pathlib import Path

DEFAULT_WORLD_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "world_state.json"
DEFAULT_AUDIT_LOG_DIR = Path(__file__).parent.parent.parent / "Agent logs"

class ConstructionOperator:
    """
    Handles critical state mutations and audit logging for the construction loop.
    'If it didn't update state, it didn't happen.'
    """
    
    # Class-level overrides for testing
    WORLD_STATE_PATH = DEFAULT_WORLD_STATE_PATH
    AUDIT_LOG_DIR = DEFAULT_AUDIT_LOG_DIR

    @classmethod
    def load_state(cls):
        if not cls.WORLD_STATE_PATH.exists():
            return {
                "project_id": "P001",
                "current_cost": 0,
                "current_duration": 0,
                "variations": [],
                "rfis": [],
                "delays": []
            }
        with open(cls.WORLD_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def save_state(cls, state):
        cls.WORLD_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(cls.WORLD_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    @classmethod
    def handle_tool_call(cls, tool_json):
        state = cls.load_state()
        from ..logic import event_bus

        try:
            tool_data = json.loads(tool_json) if isinstance(tool_json, str) else tool_json
        except Exception as e:
            return {
                "completion_status": "FAILED",
                "executed_count": 0,
                "failed_count": 0,
                "total_calls": 0,
                "results": [],
                "error": f"invalid_tool_payload: {e}"
            }

        trace_id = tool_data.get("trace_id", "N/A")
        calls = tool_data.get("tool_calls", [])
        if not isinstance(calls, list) or len(calls) == 0:
            event_bus.emit_event("ACTION_BLOCKED", trace_id, metadata={
                "reason": "no_tool_calls",
                "completion_status": "FAILED"
            })
            return {
                "completion_status": "FAILED",
                "executed_count": 0,
                "failed_count": 0,
                "total_calls": 0,
                "results": [],
                "error": "no_tool_calls"
            }

        results = []
        executed_count = 0
        failed_count = 0
        scenarios = []
        statuses = []

        for call in calls:
            tool = call.get("tool")
            args = call.get("arguments", {})
            
            if tool == "update_entity":
                try:
                    entity_type = args.get("type", "variation")
                    entity_data = args.get("data", {})
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

                    # Support both legacy and new construction_ prefixed types
                    base_type = entity_type.replace("construction_", "")
                    state_key = base_type + "s"
                    state.setdefault(state_key, []).append(entry)
                    
                    if status == "approved" and base_type == "variation":
                        state["current_cost"] = float(state.get("current_cost", 0)) + float(cost)
                        state["current_duration"] = int(state.get("current_duration", 0)) + int(days)

                    executed_count += 1
                    scenarios.append(entity_type)
                    statuses.append(status)
                    results.append({
                        "tool": tool,
                        "success": True,
                        "scenario": entity_type,
                        "status": status
                    })
                except Exception as e:
                    failed_count += 1
                    results.append({
                        "tool": tool,
                        "success": False,
                        "error": str(e)
                    })
            elif tool == "file_write":
                try:
                    from ..tools import safe_file_write
                    path = args.get("path")
                    content = args.get("content")
                    if not path or content is None:
                        raise ValueError("Missing path or content for file_write")
                    
                    write_res = safe_file_write(path, content)
                    if write_res.startswith("Error"):
                        raise Exception(write_res)
                    
                    executed_count += 1
                    results.append({
                        "tool": tool,
                        "success": True,
                        "path": path
                    })
                except Exception as e:
                    failed_count += 1
                    results.append({
                        "tool": tool,
                        "success": False,
                        "error": str(e)
                    })
            else:
                failed_count += 1
                results.append({
                    "tool": tool,
                    "success": False,
                    "error": "unsupported_tool"
                })
                continue

        total_calls = len(calls)
        completion_status = "FAILED"
        if executed_count > 0 and failed_count == 0:
            completion_status = "EXECUTED"
        elif executed_count > 0 and failed_count > 0:
            completion_status = "PARTIALLY_EXECUTED"

        if executed_count > 0:
            cls.save_state(state)
            print(f"[OPERATOR] State updated.")
            mutation_metadata = {
                "scenario": scenarios[-1] if scenarios else "unknown",
                "status": statuses[-1] if statuses else "unknown",
                "completion_status": completion_status,
                "executed_count": executed_count,
                "failed_count": failed_count,
                "total_calls": total_calls
            }
            event_bus.emit_event("STATE_MUTATED", trace_id, metadata=mutation_metadata)
            event_bus.emit_event("ACTION_EXECUTED", trace_id, metadata=mutation_metadata)
        else:
            event_bus.emit_event("ACTION_BLOCKED", trace_id, metadata={
                "scenario": "unknown",
                "status": "unknown",
                "completion_status": completion_status,
                "executed_count": executed_count,
                "failed_count": failed_count,
                "total_calls": total_calls
            })

        return {
            "completion_status": completion_status,
            "executed_count": executed_count,
            "failed_count": failed_count,
            "total_calls": total_calls,
            "results": results,
            "error": "" if completion_status != "FAILED" else "no_supported_actions_executed"
        }

    @classmethod
    def log_to_sentinel(cls, step, agent, input_data, output_data):
        """
        Writes a formal audit entry for Sentinel to process or log.
        """
        cls.AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "step": step,
            "agent": agent,
            "input": input_data,
            "output": output_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        log_file = cls.AUDIT_LOG_DIR / f"sentinel_{datetime.utcnow().date()}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[SENTINEL] Logged step: {step} by {agent}")
