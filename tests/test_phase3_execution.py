import pytest
import os
import hashlib
from agents.state import AGENTSState
from agents.nodes import gatekeeper_node, execute_node
from agents.core import GovernanceEngine
from agents.leases import MissionLease
from agents.orchestrator import Orchestrator
from agents.operators.construction_op import ConstructionOperator

@pytest.mark.asyncio
async def test_end_to_end_governed_execution():
    """
    Simulates a full Phase 3 mission flow:
    1. Proposal with tool requests.
    2. Gatekeeper approval -> Lease issuance.
    3. execution_node -> Firewall check -> Secure file write.
    """
    # Cleanup any old test output
    test_file = "data/test_execution.txt"
    if os.path.exists(test_file):
        os.remove(test_file)
        
    # 1. Setup State
    state: AGENTSState = {
        "status": "pending_gatekeeper",
        "proposal": {
            "proposal_id": "PROP-P3-TEST",
            "created_by": "AGT-001",
            "domain": "OPS",
            "title": "Test Execution",
            "description": "Writing a test file."
        },
        "session_id": "SESS-P3-TEST",
        "tool_requests": [
            {
                "tool": "file_write",
                "target": test_file,
                "action": "write",
                "payload": "Governed Execution Active"
            }
        ],
        "gatekeeper_decision": "APPROVED",
        "gatekeeper_reasoning": "Test passed governance",
        "active_lease": None,
        "execution_results": []
    }
    
    # 2. Run Gatekeeper Node (Should issue lease)
    # We pass a real GovernanceEngine but it will load real configs (which is fine)
    updated_gatekeeper = gatekeeper_node(state)
    state.update(updated_gatekeeper)
    
    assert state["status"] == "APPROVED"
    assert state["active_lease"] is not None
    assert isinstance(state["active_lease"], MissionLease)
    assert state["active_lease"].agent_id == "AGT-001"
    
    # 3. Run Execute Node (Should write file via Firewall)
    updated_execution = await execute_node(state)
    state.update(updated_execution)
    
    assert state["status"] == "EXECUTED"
    assert len(state["execution_results"]) == 1
    assert state["execution_results"][0]["success"] is True
    assert "Successfully wrote" in state["execution_results"][0]["result"]
    assert state["active_lease"] is None # Atomic expiry verified
    
    # 4. Verify physical result
    assert os.path.exists(test_file)
    with open(test_file, "r") as f:
        assert f.read() == "Governed Execution Active"
        
    os.remove(test_file)

@pytest.mark.asyncio
async def test_execution_failure_on_missing_lease():
    """
    Ensures that execute_node fails if no lease is present.
    """
    state: AGENTSState = {
        "status": "APPROVED",
        "proposal": {"proposal_id": "FAIL-TEST", "created_by": "AGT-001", "domain": "OPS"},
        "tool_requests": [{"tool": "file_write", "target": "data/forbidden.txt", "payload": "evil"}],
        "active_lease": None, # Missing!
        "session_id": "SESS-FAIL"
    }

    updated = await execute_node(state)
    assert updated["execution_results"][0]["success"] is False
    assert "no_active_lease" in updated["execution_results"][0]["result"] or "Access Denied" in updated["execution_results"][0]["result"]


def test_orchestrator_normalize_completion_statuses():
    orc = Orchestrator()

    assert orc._normalize_completion_status({"completion_status": "EXECUTED"}) == "EXECUTED"
    assert orc._normalize_completion_status({"completion_status": "PARTIALLY_EXECUTED"}) == "PARTIALLY_EXECUTED"
    assert orc._normalize_completion_status({"completion_status": "FAILED"}) == "FAILED"

    assert orc._normalize_completion_status({"executed_count": 1, "failed_count": 0}) == "EXECUTED"
    assert orc._normalize_completion_status({"executed_count": 1, "failed_count": 1}) == "PARTIALLY_EXECUTED"
    assert orc._normalize_completion_status({"executed_count": 0, "failed_count": 1}) == "FAILED"
    assert orc._normalize_completion_status(None) == "FAILED"


def test_orchestrator_executor_tool_enforcement():
    orc = Orchestrator()
    trace_id = "TRACE-TOOL-ENFORCE"

    valid_payload = {
        "trace_id": trace_id,
        "tool_calls": [{"tool": "update_entity", "arguments": {"type": "variation", "data": {}}}]
    }
    ok, reason = orc._enforce_executor_tool_calls(valid_payload, trace_id, "variation")
    assert ok is True
    assert reason == ""

    invalid_payload = {
        "trace_id": trace_id,
        "tool_calls": [{"tool": "shell_command", "arguments": {"command": "dir"}}]
    }
    ok, reason = orc._enforce_executor_tool_calls(invalid_payload, trace_id, "variation")
    assert ok is False
    assert reason.startswith("unsupported_executor_tools")


def test_construction_operator_returns_terminal_status_dict():
    result = ConstructionOperator.handle_tool_call({"trace_id": "TRACE-EMPTY", "tool_calls": []})
    assert isinstance(result, dict)
    assert result.get("completion_status") == "FAILED"
    assert result.get("executed_count") == 0


def test_executor_phase_retries_on_no_execution(monkeypatch):
    orc = Orchestrator()
    attempts = {"count": 0}

    def fake_handle_tool_call(_payload):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return {
                "completion_status": "FAILED",
                "executed_count": 0,
                "failed_count": 1,
                "total_calls": 1,
                "results": [],
                "error": "simulated_no_execution"
            }
        return {
            "completion_status": "EXECUTED",
            "executed_count": 1,
            "failed_count": 0,
            "total_calls": 1,
            "results": [{"tool": "update_entity", "success": True}],
            "error": ""
        }

    monkeypatch.setattr(ConstructionOperator, "handle_tool_call", fake_handle_tool_call)

    payload = {
        "trace_id": "TRACE-RETRY",
        "tool_calls": [{"tool": "update_entity", "arguments": {"type": "variation", "data": {}}}]
    }

    result = orc._run_construction_executor_phase(
        scenario_type="variation",
        trace_id="TRACE-RETRY",
        task_payload=payload,
        status="approved",
        system_forced_escalation=False,
        max_attempts=2,
    )

    assert attempts["count"] == 2
    assert result.get("completion_status") == "EXECUTED"
    assert result.get("attempt") == 2

