
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Root path alignment
sys.path.append(str(Path(__file__).parent))

from agents.orchestrator import Orchestrator
from agents.logic.external_gateway import ExternalGateway
from agents.logic import event_bus
from agents.firewall import PreflightApprovalEngine

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("demo")

SCENARIO = {
    "scenario": "Concrete pour delay due to rain (Contact: operations-lead@construction.com)",
    "cost_impact": 8000,
    "delay_days": 2,
    "risk_score": 0.4
}

async def run_pass(orchestrator, gateway, approval_engine, pass_num):
    print(f"\n{'='*60}")
    print(f" DEMO PASS {pass_num}: {SCENARIO['scenario']}")
    print(f"{'='*60}\n")
    
    user_input = f"Incident: {SCENARIO['scenario']}. Cost impact: ${SCENARIO['cost_impact']}. Delay: {SCENARIO['delay_days']} days. Risk: {SCENARIO['risk_score']}"
    trace_id = f"DEMO-{pass_num}-{datetime.now().strftime('%M%S')}"
    
    # Pass 1 & 2: Run the full Orchestrator Loop
    print("[SYSTEM] Starting Orchestrator Loop...")
    last_request_id = None
    
    # We consume the SSE stream from the orchestrator
    async for data in orchestrator._run_generic_construction_loop("site_issue", user_input, trace_id):
        if "PROPOSAL CREATED" in data:
            # Extract request ID: [SYSTEM] PROPOSAL CREATED. Request ID: APR-XXXX
            last_request_id = data.split("Request ID: ")[1].strip()
        
        # Filter for cleaner CLI output (only show agent starts and system signals)
        if "START" in data or "[SYSTEM]" in data or "[ARIA]" in data or "[JENNY]" in data:
            print(f"  {data.replace('data: ', '').strip()}")

    if not last_request_id:
        print("[ERROR] Loop failed to produce a valid execution intent.")
        return

    # 1. RETRIEVE THE IMMUTABLE INTENT
    request = approval_engine.get_request(last_request_id)
    intent = request.get("original_action_intent")
    meta = intent.get("metadata", {})
    
    print(f"\n{'-'*40}")
    print(" [ANALYSIS] REASONING DISCLOSURE (The AI's Inner Monologue)")
    print(f"{'-'*40}")
    
    # Display Governance reasoning
    gov_flags = meta.get("governance_flags", [])
    if gov_flags:
        print(f" GOVERNANCE: !!! Flags raised: {', '.join([f['flag_type'] for f in gov_flags])}")
    else:
        print(" GOVERNANCE: [OK] No critical policy violations.")
        
    # Display Owen's intelligence
    owen = meta.get("owen_briefing", {})
    lessons = owen.get("lessons_learned", [])
    if lessons:
        print(f" OWEN: !!! Historical Lesson: \"{lessons[0]}\"")
    else:
        print(" OWEN: [INFO] No specific historical warnings for this scenario.")
        
    print(f" FINAL: {meta.get('final_decision')} -> {meta.get('final_justification')[:150]}...")
    print(f"{'-'*40}\n")

    # 2. HUMAN GATEKEEPER
    action_name = intent.get('action').upper()
    print(f"PROPOSED ACTION: {action_name}")
    
    if action_name == "GMAIL_DRAFT":
        print(f"TARGET: {intent.get('parameters', {}).get('to', 'Stakeholder')}")
        print(f"SUBJECT: {intent.get('parameters', {}).get('subject', 'No Subject')}")
    else:
        print(f"INFO: This is a system-level action ({action_name}) and cannot be executed as a side-effect in Phase 3A.")

    choice = input("\n[GATEKEEPER] Approve this action? (y/n): ").strip().lower()
    
    if choice == 'y':
        if action_name != "GMAIL_DRAFT":
            print("\n[SYSTEM] Cannot execute non-Gmail action in this demo mode. Loop complete.")
            return

        # 3. ATOMIC EXECUTION (Passing the exact same object)
        print("\n[SYSTEM] Execution authorized. Submitting to Hardened Gateway...")
        approval_engine.decide_request(last_request_id, "approved", decided_by="DEMO_USER")
        
        try:
            result = gateway.validate_and_execute(intent, last_request_id)
            print(f"\n[SUCCESS] Side-effect confirmed.")
            print(f"   Draft Created: {result.get('draft_id', 'N/A')}")
            print(f"   Trace: {result.get('execution_trace_id', 'N/A')}")
        except Exception as e:
            print(f"\n[BLOCKED] {e}")
    else:
        print("\n[SYSTEM] Action rejected by human gatekeeper.")

async def main():
    # 0. System Setup
    orchestrator = Orchestrator()
    gateway = ExternalGateway()
    approval_engine = PreflightApprovalEngine()
    
    # Pass 1: Fresh execution
    print("\n[STEP 1] FRESH EXECUTION PATH")
    await run_pass(orchestrator, gateway, approval_engine, 1)
    
    # Pass 2: REPLAY PROTECTION PROOF
    print(f"\n{'='*60}")
    print(f" DEMO PASS 2: REPLAY ATTACK / REDUNDANT APPROVAL")
    print(f"{'='*60}\n")
    print("[SYSTEM] Attempting to execute the EXACT same approved intent from Pass 1...")
    
    history = approval_engine.list_requests()
    if not history:
        print("[ERROR] No history found to replay.")
        return
        
    last_req = history[-1]
    intent = last_req["original_action_intent"]
    req_id = last_req["request_id"]
    
    print(f"  Replaying Request: {req_id}")
    print(f"  Target: {intent.get('parameters', {}).get('to')}")
    
    try:
        print("\n[SYSTEM] Authorized by 'Accidental Double Click' (DEMO_USER)...")
        result = gateway.validate_and_execute(intent, req_id)
        print(f"\n[FAIL] System allowed a duplicate execution!")
    except Exception as e:
        print(f"\n[SUCCESS] BLOCKED BY GATEWAY: {e}")
        print("  Reason: Replay protection correctly identified the redundant operation.")

if __name__ == "__main__":
    asyncio.run(main())
