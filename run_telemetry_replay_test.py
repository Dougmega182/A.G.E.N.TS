import asyncio
import sys
import json
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import Orchestrator
from agents.logic.event_analytics import get_trace_lineage, get_risk_trend_from_events

async def run_replay_test():
    orchestrator = Orchestrator()
    message = "Variation: +15k, +3 days, plumbing and drainage revision"
    
    print(f"--- STARTING TELEMETRY REPLAY TEST ---")
    print(f"Input: {message}\n")
    
    trace_id = None
    
    # 1. RUN THE LOOP
    async for chunk in orchestrator.astream_chat(message):
        if chunk.startswith("data: "):
            content = chunk.replace("data: ", "").strip()
            # Try to catch the Trace ID from the SYSTEM message
            if "[Trace:" in content:
                import re
                match = re.search(r"\[Trace:\s*([a-f0-9\-]+)\]", content)
                # Wait, the orchestrator prints the short trace in the UI but emits the full one to events.
                # Actually, I'll just find the most recent trace in the log after the run.
                pass
            
            # Print minimal progress
            if any(tag in content for tag in ["[SYSTEM]", "[ARIA]", "[SENTINEL]"]):
                if "START" not in content and "END" not in content:
                    print(content[:150] + "...")

    # 2. FETCH LATEST TRACE
    from agents.logic.event_analytics import _read_all_events
    events = _read_all_events()
    if not events:
        print("ERROR: No events found in log!")
        return
    
    latest_event = events[-1]
    trace_id = latest_event.get("trace_id")
    
    print(f"\n--- RECONSTRUCTING LINEAGE FOR TRACE: {trace_id} ---")
    lineage = get_trace_lineage(trace_id)
    
    for e in lineage:
        timestamp = e["timestamp"].split("T")[1].split(".")[0]
        print(f"[{timestamp}] {e['type']:<25} | Agent: {e['agent_id']:<10}")
        if e['type'] == "DECISION_MADE":
            print(f"    > Decision: {e['metadata'].get('decision')} | Risk: {e['metadata'].get('risk_score')}")
    
    # 3. VERIFY DERIVED TREND
    print(f"\n--- DERIVED PROJECT HEALTH (FROM EVENTS) ---")
    trend = get_risk_trend_from_events()
    print(f"Direction: {trend['direction'].upper()}")
    print(f"Last 5 Avg: {trend['avg_5']} | Last 10 Avg: {trend['avg_10']}")
    
    # 4. VERIFY STATE CLEANLINESS
    print(f"\n--- STATE INTEGRITY CHECK ---")
    with open("data/world_state.json", "r") as f:
        state = json.load(f)
        keys = list(state.keys())
        print(f"World State Keys: {keys}")
        if "decision_history" in keys or "risk_trend" in keys:
             print("FAILED: Legacy keys still present in state!")
        else:
             print("PASSED: World state is clean and derivative-free.")

if __name__ == "__main__":
    asyncio.run(run_replay_test())
