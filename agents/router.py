from agents.state import AGENTSState

def route_after_logic(state: AGENTSState) -> str:
    if state.get("violations"):
        return "red_1_protocol"
    return "planning_layer"

def route_after_validation(state: AGENTSState) -> str:
    if state.get("protocol_triggered") == "GOLD-1":
        return "planning_layer"  # failed quality — return to start
    return "governance_layer"

def route_after_governance(state: AGENTSState) -> str:
    audit = state.get("governance_result", {})
    if audit.get("compliance_risk", 0) > 0.75:
        return "blue_1_protocol"
    return "boardroom_layer"

def route_after_boardroom(state: AGENTSState) -> str:
    votes = state.get("votes", {})
    if votes.get("decision") == "AUDIT_VETO":
        return "gatekeeper"  # veto always escalates
    if votes.get("decision") == "APPROVED":
        return "gatekeeper"
    return "planning_layer"  # rejected — return to planning

def route_after_gatekeeper(state: AGENTSState) -> str:
    if state.get("gatekeeper_approved"):
        return "execute"
    return "end"

def route_energy_state(state: AGENTSState) -> str:
    """G10 — Energy-aware routing"""
    if state.get("overwhelm_detected"):
        return "amber_1_protocol"
    if state.get("flow_state_active"):
        return "green_1_protocol"
    return "logic_layer"
