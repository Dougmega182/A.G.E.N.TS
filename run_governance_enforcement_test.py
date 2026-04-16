import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import Orchestrator
from agents.logic.event_analytics import _read_all_events


async def _run_message(message: str):
    orchestrator = Orchestrator()
    streamed = []
    async for chunk in orchestrator.astream_chat(message):
        if chunk.startswith("data: "):
            streamed.append(chunk.replace("data: ", "").strip())
    return streamed


def _latest_trace_id() -> str:
    events = _read_all_events()
    if not events:
        raise RuntimeError("No events found in data/events.log.jsonl")
    return events[-1]["trace_id"]


def _trace_events(trace_id: str):
    events = _read_all_events()
    return [e for e in events if e.get("trace_id") == trace_id]


def _latest_state_entry(scenario_type: str):
    with open("data/world_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    bucket = f"{scenario_type}s"
    rows = state.get(bucket, [])
    if not rows:
        raise RuntimeError(f"No state entries found for {bucket}")
    return rows[-1]


def _assert_event_order(trace_events, expected):
    observed = [e.get("type") for e in trace_events]
    idx = 0
    for event_type in observed:
        if idx < len(expected) and event_type == expected[idx]:
            idx += 1
    if idx != len(expected):
        raise AssertionError(f"Expected sequence {expected} not found in order. Observed: {observed}")


async def scenario_a_happy_path():
    print("--- Scenario A (Happy Path) ---")
    message = "Variation: +8k, +1 day, electrical reroute"
    await _run_message(message)
    trace_id = _latest_trace_id()
    trace_events = _trace_events(trace_id)

    _assert_event_order(trace_events, ["ACTION_INTENT", "STATE_MUTATED", "ACTION_EXECUTED"])

    state_entry = _latest_state_entry("variation")
    if state_entry.get("status") not in {"approved", "rejected", "escalated"}:
        raise AssertionError(f"Unexpected state status: {state_entry.get('status')}")

    print(f"Trace: {trace_id}")
    print("PASS: ACTION_INTENT -> STATE_MUTATED -> ACTION_EXECUTED observed.")


async def scenario_b_enforcement_invalid_decision():
    print("--- Scenario B (Enforcement on Invalid Decision) ---")

    original = Orchestrator._execute_contract_turn

    async def broken_execute(self, agent_key, prompt_builder, input_message, contract_id, execution_context="", trace_id="N/A"):
        if agent_key == "aria" and contract_id == "decision_v1":
            return "{\"decision\":\"APPROVE\"", False, "invalid_json"
        return await original(self, agent_key, prompt_builder, input_message, contract_id, execution_context=execution_context, trace_id=trace_id)

    Orchestrator._execute_contract_turn = broken_execute
    try:
        message = "Variation: +12k, +2 days, excavation conflict"
        await _run_message(message)
    finally:
        Orchestrator._execute_contract_turn = original

    trace_id = _latest_trace_id()
    trace_events = _trace_events(trace_id)
    event_types = [e.get("type") for e in trace_events]

    if "CONTRACT_VALIDATION_FAILED" not in event_types:
        raise AssertionError("Expected CONTRACT_VALIDATION_FAILED event not found")

    decision_events = [e for e in trace_events if e.get("type") == "DECISION_MADE"]
    if not decision_events:
        raise AssertionError("DECISION_MADE event not found")
    latest_decision = decision_events[-1]
    if latest_decision.get("metadata", {}).get("decision") != "ESCALATE":
        raise AssertionError(f"Expected forced ESCALATE, got: {latest_decision.get('metadata', {}).get('decision')}")
    if latest_decision.get("metadata", {}).get("forced_by_system") != "true":
        raise AssertionError("Expected forced_by_system=true on DECISION_MADE")

    state_entry = _latest_state_entry("variation")
    if state_entry.get("status") != "escalated":
        raise AssertionError(f"Expected state status 'escalated', got: {state_entry.get('status')}")

    print(f"Trace: {trace_id}")
    print("PASS: Validation failure blocked approval and forced ESCALATE.")


async def main():
    await scenario_a_happy_path()
    await scenario_b_enforcement_invalid_decision()
    print("--- Governance enforcement test suite complete ---")


if __name__ == "__main__":
    asyncio.run(main())
