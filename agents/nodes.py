import os
import json
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

from agents.state import AGENTSState
from agents.core import GovernanceEngine
from agents.firewall import ToolFirewall, FirewallViolation
from agents.tools import safe_file_write, safe_file_read, safe_list_files, safe_shell_command
from agents.llm import LLMProvider

load_dotenv()

gov = GovernanceEngine()

# Use the project's native LLMProvider (configured via .env, e.g., Ollama)
# This ensures Phase 1 can run immediately using local resources.
llm_backend = LLMProvider(provider=os.getenv("LLM_PROVIDER", "ollama"))

# Mapping tiers for future flexibility
senior_llm = llm_backend
fast_llm = llm_backend

def load_profile_prompt(agent_id: str) -> str:
    """Load system prompt from approved agent profile"""
    profiles = {
        "AGT-001": "Onboarding/profiles/AGT-001-PROFILE-1.0.0.md",
        "AGT-002": "Onboarding/profiles/AGT-002-PROFILE-1.0.0.md",
        "AGT-003": "Onboarding/profiles/AGT-003-PROFILE-1.0.0.md",
    }
    path = profiles.get(agent_id, "")
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return f"You are agent {agent_id}. Respond accordingly."
    return ""

def log_event(agent_id: str, event_type: str, summary: dict, state: dict = None):
    """ALRMF compliant logging with partial state capture"""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent_id": agent_id,
        "event_type": event_type,
        "session_id": state.get("session_id") if state else None,
        "prev_status": state.get("status") if state else None,
        **summary
    }
    os.makedirs("data/audit_logs", exist_ok=True)
    with open(
        f"data/audit_logs/{datetime.utcnow().date()}.jsonl", 
        "a", encoding="utf-8"
    ) as f:
        f.write(json.dumps(entry) + "\n")
    return entry

def validate_output(text: str) -> dict:
    """G3 — Zero hallucination check"""
    flags = []
    hallucination_markers = [
        "I think", "probably", "maybe", "I'm not sure",
        "I believe", "approximately", "roughly"
    ]
    for marker in hallucination_markers:
        if marker.lower() in text.lower():
            flags.append(f"Uncertainty marker detected: {marker}")
    
    return {
        "content": text,
        "valid": len(flags) == 0,
        "flags": flags
    }

# ── LAYER 1: LOGIC ──────────────────────────────────────────

async def logic_layer_node(state: AGENTSState) -> dict:
    log_event("AGT-003", "activation", {
        "layer": 1,
        "context": "Logic validation"
    }, state=state)
    
    validation = gov.validate_proposal(state["proposal"])
    
    log_event("AGT-003", "decision", {
        "valid": validation["valid"],
        "violations": validation["violations"]
    }, state=state)
    
    return {
        "logic_result": validation,
        "violations": validation["violations"],
        "current_layer": 1,
        "audit_trail": [log_event("AGT-003", "layer_complete", {
            "layer": 1, "passed": validation["valid"]
        })]
    }

# ── LAYER 2: PLANNING ────────────────────────────────────────

async def planning_layer_node(state: AGENTSState) -> dict:
    log_event("AGT-001", "activation", {
        "layer": 2, "context": "Planning"
    })
    
    prompt = load_profile_prompt("AGT-001")
    
    # Using the project's sync chat method
    response = senior_llm.chat(
        system_prompt=prompt,
        user_message=f"""
        Evaluate this proposal for the planning layer.
        Return a structured plan with steps, owner, 
        risks, and outcome.
        
        Proposal: {json.dumps(state['proposal'], indent=2)}
        """
    )
    
    validated = validate_output(response)
    
    return {
        "planning_result": validated,
        "current_layer": 2,
        "audit_trail": [log_event("AGT-001", "planning_complete", {
            "valid": validated["valid"]
        })]
    }

# ── LAYER 6: GOVERNANCE/AUDIT ────────────────────────────────

async def governance_layer_node(state: AGENTSState) -> dict:
    log_event("AGT-003", "activation", {
        "layer": 6, "context": "Governance audit"
    })
    
    prompt = load_profile_prompt("AGT-003")
    
    response = senior_llm.chat(
        system_prompt=prompt,
        user_message=f"""
        Conduct a governance audit of this proposal.
        Check: constitutional compliance, risk level,
        ethical alignment, audit trail completeness.
        
        Proposal: {json.dumps(state['proposal'], indent=2)}
        Layer results so far: {json.dumps({
            'logic': state.get('logic_result'),
            'validation': state.get('validation_result')
        }, indent=2)}
        
        Return: approved (bool), compliance_risk (0-1),
        findings (list), recommendation (str)
        """
    )
    
    validated = validate_output(response)
    
    return {
        "governance_result": {
            "content": validated["content"],
            "compliance_risk": 0.1,  # mock parse from response
            "valid": validated["valid"]
        },
        "current_layer": 6,
        "audit_trail": [log_event("AGT-003", "audit_complete", {})]
    }

# ── LAYER 7: BOARDROOM ───────────────────────────────────────

async def boardroom_node(state: AGENTSState) -> dict:
    """Your existing boardroom.py logic, rewired as a node"""
    from agents.boardroom import Boardroom
    from agents.llm import LLMProvider as NativeLLMProvider
    
    provider_name = os.getenv("LLM_PROVIDER", "ollama")
    llm_provider = NativeLLMProvider(provider=provider_name)
    boardroom = Boardroom(gov, llm_provider)
    result = boardroom.debate_proposal(state["proposal"])
    
    log_event("BOARDROOM", "vote_complete", {
        "decision": result["decision"],
        "yes_weight": result["yes_weight"],
        "no_weight": result["no_weight"]
    })
    
    return {
        "votes": result,
        "current_layer": 7,
        "audit_trail": [result]
    }

# ── GATEKEEPER (Human in the loop) ──────────────────────────

def gatekeeper_node(state: AGENTSState) -> dict:
    """
    Final decision point for the human Gatekeeper.
    This node is PURE: it reads the decision from state and routes.
    It does NOT pause internally (pause happens via checkpoint before entry).
    """
    decision = state.get("gatekeeper_decision")
    
    if not decision:
        # This shouldn't happen if resumed correctly, but for safety:
        return {"status": "WAITING_FOR_GATEKEEPER"}
    
    log_event("AGT-000", "gatekeeper_decision", {
        "decision": decision,
        "proposal_id": state["proposal"].get("proposal_id"),
        "reasoning": state.get("gatekeeper_reasoning"),
        "new_status": "APPROVED" if decision == "APPROVED" else "REJECTED"
    }, state=state)
    
    status = "APPROVED" if decision == "APPROVED" else "REJECTED"
    
    # Phase 3: Issue Mission Lease upon approval
    lease = None
    if decision == "APPROVED":
        # Extract intended tool calls from the plan
        # In a real run, these would be extracted from the planning_result or proposal.description
        # For this implementation, we use a placeholder or check the proposal for a specialized field.
        intents = state.get("tool_requests", [])
        if intents:
            lease = gov.generate_lease(
                agent_id=state["proposal"].get("created_by", "SYSTEM"),
                domain=state["proposal"].get("domain", "OPS"),
                execution_id=state.get("session_id", "GLOBAL-EXEC"),
                approved_intents=intents
            )
            log_event("SYSTEM", "lease_issued", {
                "lease_id": lease.lease_id,
                "agent_id": lease.agent_id,
                "domain": lease.domain
            }, state=state)

    return {
        "status": status,
        "gatekeeper_decision": decision,
        "active_lease": lease
    }

# ── PROTOCOL NODES ───────────────────────────────────────────

async def red_1_node(state: AGENTSState) -> dict:
    log_event("PROTOCOL", "RED-1", {
        "violations": state.get("violations"),
        "triggered_at_layer": state.get("current_layer")
    })
    return {
        "protocol_triggered": "RED-1",
        "current_layer": -1
    }

async def amber_1_node(state: AGENTSState) -> dict:
    """G8 — ADHD overwhelm response"""
    log_event("AGT-002", "AMBER-1", {
        "overwhelm_detected": True,
        "energy_state": state.get("energy_state")
    })
    return {
        "protocol_triggered": "AMBER-1",
        "overwhelm_detected": True
    }

async def green_1_node(state: AGENTSState) -> dict:
    """G11 — Flow state protection"""
    log_event("AGT-002", "GREEN-1", {
        "flow_state_active": True
    })
    return {
        "protocol_triggered": "GREEN-1",
        "flow_state_active": True
    }

async def execute_node(state: AGENTSState) -> dict:
    """Terminal execution — Governed via Firewall and Mission Lease"""
    log_event("SYSTEM", "execution_start", {
        "proposal_id": state["proposal"].get("proposal_id"),
        "approved_by": "Gatekeeper",
        "lease_id": state.get("active_lease").lease_id if state.get("active_lease") else None
    }, state=state)

    results = []
    agent_id = state["proposal"].get("created_by", "SYSTEM")
    agent_domain = state["proposal"].get("domain", "OPS")
    lease = state.get("active_lease")
    requests = state.get("tool_requests", [])
    session_id = state.get("session_id", "GLOBAL-EXEC")

    for req in requests:
        tool = req.get("tool")
        target = req.get("target")
        action = req.get("action", "")
        payload = req.get("payload", "").encode("utf-8")
        
        try:
            # 1. Fireall Validation
            ToolFirewall.validate(
                agent_id=agent_id,
                agent_domain=agent_domain,
                lease=lease,
                tool=tool,
                target=target,
                action=action,
                payload=payload,
                current_execution_id=session_id
            )
            
            # 2. Execution (Surgical)
            res_val = "Error: Tool not implemented"
            if tool == "file_write":
                res_val = safe_file_write(target, req.get("payload", ""))
            elif tool == "file_read":
                res_val = safe_file_read(target)
            elif tool == "list_files":
                res_val = str(safe_list_files(target))
            elif tool == "shell_command":
                res_val = safe_shell_command(target, req.get("args", []))
            
            results.append({"tool": tool, "target": target, "result": res_val, "success": True})
            
        except FirewallViolation as e:
            results.append({"tool": tool, "target": target, "result": str(e), "success": False})
            log_event("FIREWALL", "violation", {
                "reason": e.reason,
                "tool": tool,
                "target": target
            }, state=state)
            # Halt further execution on violation
            break
        except Exception as e:
            results.append({"tool": tool, "target": target, "result": f"System Error: {str(e)}", "success": False})
            break

    # Final cleanup: Auto-expire lease on completion
    log_event("SYSTEM", "execution_complete", {
        "actions_count": len(results),
        "status": "COMPLETED"
    }, state=state)

    return {
        "execution_results": results,
        "status": "EXECUTED",
        "active_lease": None # Atomic expiry
    }
