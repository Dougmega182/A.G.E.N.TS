import sys
import os
from pathlib import Path
import asyncio

# Ensure correct PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.graph import build_agents_graph

async def test_basic_pipeline():
    app = build_agents_graph(persist=False)
    
    test_proposal = {
        "proposal_id": "TEST-002",
        "title": "Valid Proposal",
        "description": "Testing the full pipeline flow",
        "domain": "cross-domain", # Case-matched to AGT-001 domain
        "created_by": "AGT-001",
        "impact": "low"
    }
    
    initial_state = {
        "proposal": test_proposal,
        "current_layer": 0,
        "violations": [],
        "audit_trail": [],
        "protocol_triggered": None,
        "gatekeeper_approved": None,
        "energy_state": "normal",
        "flow_state_active": False,
        "overwhelm_detected": False,
        "votes": {}
    }
    
    result = await app.ainvoke(initial_state)
    print(f"Pipeline result: {result.get('current_layer')}")
    print(f"Violations: {result.get('violations')}")
    print(f"Protocol: {result.get('protocol_triggered')}")
    assert result is not None

if __name__ == "__main__":
    asyncio.run(test_basic_pipeline())
