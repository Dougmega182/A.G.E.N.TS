import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# Adjust path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator
from agents import preflight_validator as firewall
from agents.preflight_validator import PreflightApprovalEngine
from agents.operators.construction_op import ConstructionOperator
from agents.logic import event_bus
from agents.roster import AGENTS

@pytest.fixture(autouse=True)
def setup_test_env(tmp_path):
    # Mock data paths
    store_path = tmp_path / "preflight_approvals.json"
    draft_store_path = tmp_path / "preflight_drafts.json"
    
    # Create an isolated engine
    test_engine = PreflightApprovalEngine(store_path=store_path, draft_store_path=draft_store_path)
    
    # Patch the global DEFAULT_ENGINE in the firewall module
    with patch('agents.preflight_validator.DEFAULT_ENGINE', test_engine):
        ConstructionOperator.WORLD_STATE_PATH = tmp_path / "world_state.json"
        
        # Initialize mock world state
        world_state = {
            "project_id": "P001",
            "current_cost": 100000.0,
            "current_duration": 10,
            "variation": {"cost": 0, "impact_days": 0, "reason": ""},
            "status": "pending",
            "risks": [],
            "history": [],
            "variations": [],
            "delays": [],
            "rfis": []
        }
        with open(ConstructionOperator.WORLD_STATE_PATH, "w") as f:
            json.dump(world_state, f)
            
        # Reset event bus
        if hasattr(event_bus, "_buffer"):
            event_bus._buffer.clear()
            
        yield test_engine

@pytest.mark.asyncio
async def test_phase1_full_workflow_compliance():
    """
    AUDIT: Full Phase 1 Loop Compliance
    1. Trigger Scenario -> 2. Proposal Created -> 3. Approved -> 4. Executed -> 5. State Mutated
    """
    orc = Orchestrator()
    trace_id = "test_audit_trace"
    user_input = "Variation: +10k, +2 days for site prep"
    
    # --- STEP 1 & 2: TRIGGER & PROPOSAL ---
    # We need to mock the LLM turns to return valid contract objects
    with (
        patch('agents.orchestrator.CONTRACT_MODEL_MAP') as mock_map,
        patch('agents.orchestrator.event_bus.emit_event') as mock_emit
    ):
        # Setup mock responses for the chain
        mock_llm = MagicMock()
        mock_map.get.return_value = mock_llm
        
        # Nadia Plan
        plan_resp = MagicMock()
        plan_resp.content = json.dumps({
            "goal": "Resolve site prep needs",
            "assumptions": ["Stable soil"],
            "steps": ["Step 1", "Step 2", "Step 3"],
            "risks": ["Weather"],
            "first_action": "Assess site"
        })
        # Atlas Implementation
        impl_resp = MagicMock()
        impl_resp.content = json.dumps({
            "technical_goal": "Excavate and level",
            "architecture_impact": "None",
            "implementation_steps": ["Dig", "Fill"],
            "validation_criteria": ["Level surface"]
        })
        # Sentinel Critique
        critique_resp = MagicMock()
        critique_resp.content = json.dumps({
            "critique": "The proposed plan is technically sound and the risks are manageable with the current budget.",
            "risk_flags": [],
            "logic_check": "PASS",
            "recommendation": "PROCEED"
        })
        # Owen Vote
        vote_resp = MagicMock()
        vote_resp.content = json.dumps({
            "request_id": "req123",
            "voter_id": "AGT-008",
            "vote": "approve",
            "justification": "Matches historical patterns."
        })
        # Aria Decision
        decision_resp = MagicMock()
        decision_resp.content = json.dumps({
            "decision": "APPROVE",
            "justification": "Budget within limits",
            "conditions": [],
            "impact": {"cost": 10000.0, "days": 2, "risk_delta": 0.1}
        })
        # Jenny Email
        email_resp = MagicMock()
        email_resp.content = json.dumps({
            "to": "client@example.com",
            "subject": "Variation Approval",
            "body": "Your variation has been approved."
        })
        
        # Sentinel Audit
        audit_resp = MagicMock()
        audit_resp.content = json.dumps({
            "audit_entry": {
                "step": "VARIATION_LOOP",
                "agent": "SENTINEL",
                "input": "...",
                "output": "...",
                "timestamp": "2026-04-16T10:00:00"
            }
        })
        
        # Chain the responses (Nadia, Atlas, Sentinel Critique, Owen Vote, Aria Decision, Jenny Email, Sentinel Audit)
        mock_llm.invoke.side_effect = [
            plan_resp, # Nadia
            impl_resp, # Atlas
            critique_resp, # Sentinel Critique
            vote_resp, # Owen Vote
            decision_resp, # Aria Decision
            email_resp, # Jenny Email
            audit_resp # Sentinel Audit
        ]
        
        # Run the loop
        chunks = []
        async for chunk in orc.astream_chat(user_input):
            chunks.append(chunk)
            
        combined_output = "".join(chunks)
        
        # COMPLIANCE CHECK: Was it paused for approval?
        assert "PROPOSAL CREATED" in combined_output
        assert "Awaiting human approval" in combined_output
        
        # COMPLIANCE CHECK: Did a request appear in the engine?
        requests = firewall.list_requests(status="pending")
        assert len(requests) == 1
        req = requests[0]
        assert req["action"] == "construction_variation"
        assert req["agent_id"] == "aria"
        
        # --- STEP 3: APPROVAL ---
        decided = firewall.decide_request(req["request_id"], "approve")
        assert decided["status"] == "approved"
        
        # --- STEP 4: EXECUTION ---
        exec_result = await firewall.execute_task(req["request_id"])
        assert exec_result["completion_status"] == "EXECUTED"
        
        # --- STEP 5: STATE PERSISTENCE ---
        with open(ConstructionOperator.WORLD_STATE_PATH, "r") as f:
            new_state = json.load(f)
            
        assert new_state["current_cost"] == 110000.0
        assert new_state["current_duration"] == 12
        assert len(new_state["variations"]) == 1
        assert new_state["variations"][0]["status"] == "approved"

@pytest.mark.asyncio
async def test_agent_roster_compliance():
    """
    AUDIT: Roster compliance with Phase 0/1 hard boundaries.
    """
    assert "aria" in AGENTS and AGENTS["aria"]["title"] == "Chief Executive Officer (CEO)"
    assert "nadia" in AGENTS and AGENTS["nadia"]["title"] == "Planner / System Designer"
    assert "atlas" in AGENTS and AGENTS["atlas"]["title"] == "Engineer"
    assert "jenny" in AGENTS and AGENTS["jenny"]["title"] == "Executive Personal Assistant (PA)"
    assert "sentinel" in AGENTS and AGENTS["sentinel"]["title"] == "System Auditor / Compliance"
    assert "owen" in AGENTS and AGENTS["owen"]["owns"] == ["intelligence"]

def test_contract_integrity_audit():
    """
    AUDIT: Ensure all required contracts are strictly enforced.
    """
    from agents.execution_mode import OutputContract
    contract = OutputContract()
    
    # Valid proposal check
    proposal = {
        "scenario_type": "variation",
        "user_input": "...",
        "plan": {},
        "implementation_plan": {},
        "decision": {},
        "email_draft": {},
        "risk_score": 0.5,
        "trace_id": "..."
    }
    res = contract.conforms_to_contract(proposal, "proposal_v1")
    assert res.ok, f"Proposal contract failed audit: {res.reason}"

    # Meta-language rejection check
    output_with_meta = json.dumps({
        "goal": "I am an AI assistant and I plan to build it.",
        "assumptions": ["None"],
        "steps": ["Step 1", "Step 2", "Step 3"],
        "risks": ["None"],
        "first_action": "Proceed"
    })
    res = contract.validate(output_with_meta, execution_mode=True, required_format="plan_v1")
    assert not res.ok
    assert res.reason == "meta_language_detected"
