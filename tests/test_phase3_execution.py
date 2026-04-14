import pytest
import os
import hashlib
from agents.state import AGENTSState
from agents.nodes import gatekeeper_node, execute_node
from agents.core import GovernanceEngine
from agents.leases import MissionLease

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
