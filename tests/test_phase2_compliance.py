import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Adjust path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator
from agents import firewall
from agents.operators.construction_op import ConstructionOperator
from agents.logic import event_bus

@pytest.fixture(autouse=True)
def setup_test_env(tmp_path):
    # Use an isolated engine for each test
    store_path = tmp_path / "preflight_approvals.json"
    engine = firewall.PreflightApprovalEngine(store_path=store_path)
    
    with patch('agents.firewall.DEFAULT_ENGINE', engine):
        ConstructionOperator.WORLD_STATE_PATH = tmp_path / "world_state.json"
        
        # Initialize mock world state
        world_state = {
            "project_id": "P001",
            "current_cost": 100000.0,
            "current_duration": 10,
            "variations": [],
            "delays": [],
            "rfis": []
        }
        with open(ConstructionOperator.WORLD_STATE_PATH, "w") as f:
            json.dump(world_state, f)
            
        if hasattr(event_bus, "_buffer"):
            event_bus._buffer.clear()
        yield

async def run_scenario(scenario_type: str, user_input: str, expected_cost: float, expected_duration: int):
    """Helper function to run a full construction loop scenario."""
    orc = Orchestrator()
    
    with patch('agents.orchestrator.CONTRACT_MODEL_MAP') as mock_map:
        mock_llm = MagicMock()
        mock_map.get.return_value = mock_llm
        
        # Mock the entire LLM chain
        plan_resp = MagicMock(); plan_resp.content = json.dumps({"goal": "g", "assumptions": [], "steps": [], "risks": [], "first_action": "a"})
        impl_resp = MagicMock(); impl_resp.content = json.dumps({"project_name": "p", "architecture": "a", "steps": [], "risks": []})
        critique_resp = MagicMock(); critique_resp.content = json.dumps({"critique": "c", "risk_flags": [], "logic_check": "PASS", "recommendation": "PROCEED"})
        vote_resp = MagicMock(); vote_resp.content = json.dumps({"request_id": "r", "voter_id": "v", "vote": "approve", "justification": "j"})
        decision_resp = MagicMock(); decision_resp.content = json.dumps({"decision": "APPROVE", "justification": "j", "conditions": [], "impact": {"cost": expected_cost - 100000, "days": expected_duration - 10, "risk_delta": 0}})
        email_resp = MagicMock(); email_resp.content = json.dumps({"to": "t", "subject": "s", "body": "b"})
        audit_resp = MagicMock(); audit_resp.content = json.dumps({"audit_entry": {"step": "s", "agent": "a", "input": "i", "output": "o", "timestamp": "t"}})
        
        mock_llm.invoke.side_effect = [plan_resp, impl_resp, critique_resp, vote_resp, decision_resp, email_resp, audit_resp]
        
        # Run loop to generate proposal
        chunks = [chunk async for chunk in orc.astream_chat(user_input)]
        
        # Approve and execute
        requests = firewall.list_requests(status="pending")
        assert len(requests) == 1
        req = requests[0]
        
        firewall.decide_request(req["request_id"], "approve")
        await firewall.execute_task(req["request_id"])
        
        # Verify state
        with open(ConstructionOperator.WORLD_STATE_PATH, "r") as f:
            new_state = json.load(f)
            
        assert new_state["current_cost"] == expected_cost
        assert new_state["current_duration"] == expected_duration
        assert len(new_state[scenario_type + "s"]) == 1
        assert new_state[scenario_type + "s"][0]["status"] == "approved"

@pytest.mark.asyncio
async def test_rfi_workflow_compliance():
    """AUDIT: Full RFI loop correctly mutates state."""
    await run_scenario(
        scenario_type="rfi",
        user_input="RFI: Clarification needed on foundation spec",
        expected_cost=100500.0, # 100k + 500
        expected_duration=11 # 10 + 1
    )

@pytest.mark.asyncio
async def test_delay_workflow_compliance():
    """AUDIT: Full Delay loop correctly mutates state."""
    await run_scenario(
        scenario_type="delay",
        user_input="Delay: 3 days due to weather",
        expected_cost=102000.0, # 100k + 2k
        expected_duration=13 # 10 + 3
    )
