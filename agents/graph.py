from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from agents.state import AGENTSState
from agents.nodes import (
    logic_layer_node,
    planning_layer_node,
    governance_layer_node,
    boardroom_node,
    gatekeeper_node,
    red_1_node,
    amber_1_node,
    green_1_node,
    execute_node
)
from agents.router import (
    route_after_logic,
    route_after_governance,
    route_after_boardroom,
    route_after_gatekeeper,
    route_energy_state
)
import os

def build_agents_graph(checkpointer=None):
    
    graph = StateGraph(AGENTSState)
    
    # ── Entry point ──────────────────────────────────────────
    graph.add_node("energy_check", 
        lambda s: s)  # G10 — check state before anything
    
    # ── 7 Layers ─────────────────────────────────────────────
    graph.add_node("logic_layer", logic_layer_node)
    graph.add_node("planning_layer", planning_layer_node)
    graph.add_node("architecture_layer", 
        lambda s: {**s, "current_layer": 3})  # stub Phase 1
    graph.add_node("execution_design_layer", 
        lambda s: {**s, "current_layer": 4})  # stub Phase 1
    graph.add_node("validation_layer", 
        lambda s: {**s, "current_layer": 5})  # stub Phase 1
    graph.add_node("governance_layer", governance_layer_node)
    graph.add_node("boardroom_layer", boardroom_node)
    
    # ── Gatekeeper ───────────────────────────────────────────
    graph.add_node("gatekeeper", gatekeeper_node)
    
    # ── Protocols ────────────────────────────────────────────
    graph.add_node("red_1_protocol", red_1_node)
    graph.add_node("blue_1_protocol", 
        lambda s: {**s, "protocol_triggered": "BLUE-1"})
    graph.add_node("amber_1_protocol", amber_1_node)
    graph.add_node("green_1_protocol", green_1_node)
    
    # ── Execution ────────────────────────────────────────────
    graph.add_node("execute", execute_node)
    
    # ── Edges ────────────────────────────────────────────────
    graph.set_entry_point("energy_check")
    
    # Energy check routes to protocol or pipeline
    graph.add_conditional_edges(
        "energy_check",
        route_energy_state,
        {
            "amber_1_protocol": "amber_1_protocol",
            "green_1_protocol": "green_1_protocol",
            "logic_layer": "logic_layer"
        }
    )
    
    # Layer sequence with protocol escape hatches
    graph.add_conditional_edges(
        "logic_layer",
        route_after_logic,
        {
            "red_1_protocol": "red_1_protocol",
            "planning_layer": "planning_layer"
        }
    )
    
    # Layers 2-5 are sequential in Phase 1
    graph.add_edge("planning_layer", "architecture_layer")
    graph.add_edge("architecture_layer", "execution_design_layer")
    graph.add_edge("execution_design_layer", "validation_layer")
    graph.add_edge("validation_layer", "governance_layer")
    
    # Governance can trigger BLUE-1
    graph.add_conditional_edges(
        "governance_layer",
        route_after_governance,
        {
            "blue_1_protocol": "blue_1_protocol",
            "boardroom_layer": "boardroom_layer"
        }
    )
    
    # Boardroom routes to gatekeeper or back to planning
    graph.add_conditional_edges(
        "boardroom_layer",
        route_after_boardroom,
        {
            "gatekeeper": "gatekeeper",
            "planning_layer": "planning_layer"
        }
    )
    
    # Gatekeeper is terminal decision point
    graph.add_conditional_edges(
        "gatekeeper",
        route_after_gatekeeper,
        {
            "execute": "execute",
            "end": END
        }
    )
    
    # Protocols terminate
    graph.add_edge("red_1_protocol", END)
    graph.add_edge("blue_1_protocol", END)
    graph.add_edge("amber_1_protocol", END)
    graph.add_edge("green_1_protocol", END)
    graph.add_edge("execute", END)
    
    # ── Compile ──────────────────────────────────────────────
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["gatekeeper"]
    )
