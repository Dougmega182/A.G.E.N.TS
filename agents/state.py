from typing import TypedDict, Annotated, List, Dict, Optional, Any
import operator
from .leases import MissionLease

class AGENTSState(TypedDict):
    # Schema Versioning
    schema_version: str # e.g. "1.0.0"
    
    # Session Identity
    session_id: str
    status: str # PENDING, WAITING_FOR_GATEKEEPER, APPROVED, REJECTED, TERMINATED
    
    # Proposal being processed
    proposal: dict
    current_layer: int
    
    # Governance tracking
    violations: Annotated[list, operator.add]
    audit_trail: Annotated[list, operator.add]
    protocol_triggered: str | None
    
    # Layer outputs
    logic_result: dict
    planning_result: dict
    architecture_result: dict
    execution_result: dict
    validation_result: dict
    governance_result: dict
    votes: dict
    
    # Gatekeeper decision context
    board_votes: Dict[str, str] # agent_id -> "APPROVED"/"REJECTED"
    gatekeeper_reasoning: Optional[str]
    
    # Phase 3: Governed Execution
    active_lease: Optional[MissionLease]
    tool_requests: List[Dict[str, Any]] # [{"tool": str, "target": str, "action": str, "payload": str}]
    execution_results: List[Dict[str, Any]] # [{"tool": str, "result": str, "success": bool}] | None
    
    # ADHD support (G8, G10, G11)
    energy_state: str
    flow_state_active: bool
    overwhelm_detected: bool
