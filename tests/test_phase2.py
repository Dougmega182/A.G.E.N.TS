import sys
import os
from pathlib import Path
import asyncio

# Ensure correct PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.sessions import SessionManager

async def test_persistence_and_interrupt():
    # Remove old DB for clean test
    if os.path.exists("data/agents_state.db"):
        os.remove("data/agents_state.db")
        
    manager = await SessionManager.create()
    thread_id = "TEST-THREAD-001"
    
    test_proposal = {
        "proposal_id": "RESUME-001",
        "title": "Persistence Test",
        "description": "Checking if interrupts save state",
        "domain": "cross-domain",
        "created_by": "AGT-001",
        "impact": "low"
    }
    
    print(f"--- Starting Session: {thread_id} ---")
    result = await manager.run_proposal(test_proposal, thread_id)
    
    # Check if it stopped at the interrupt
    state = await manager.get_state(thread_id)
    pending = state.next if state else []
    print(f"Pending after initial run: {pending}")
    
    if "gatekeeper" in pending:
        print("SUCCESS: Graph correctly paused BEFORE 'gatekeeper' node.")
        
        # Simulate human decision
        print("--- Providing Gatekeeper Decision: APPROVED ---")
        final_result = await manager.provide_decision(thread_id, "APPROVED", reasoning="Persistently verified.")
        
        # final_result is the final state after completion
        if isinstance(final_result, dict):
            status = final_result.get("status")
        elif hasattr(final_result, 'values'):
            status = final_result.values.get("status")
        else:
            status = str(final_result)
            
        print(f"Final status: {status}")
        assert status == "APPROVED"
        print("SUCCESS: Pipeline resumed and completed execution.")
    else:
        print("FAILURE: Graph did not stop at 'gatekeeper' interrupt.")

if __name__ == "__main__":
    asyncio.run(test_persistence_and_interrupt())
