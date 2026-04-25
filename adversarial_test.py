import asyncio
import json
import os
import traceback
from pathlib import Path
from agents.orchestrator import Orchestrator
from agents.logic.decision_cache import _normalize_issue
from agents import firewall

SCENARIOS = [
    "Delay: +$0, +3 days, Rain delay to slab pour",
    "Delay: +$0, +3 days, Rain delays on slab pour", # Expected HIT
    "Variation: +$12k, +0 days, upgraded acoustic tiles in lobby",
    "Variation: +$12,000, +0 days, upgraded acoustic tiles in lobby", # Expected HIT
    "RFI: +$0, +0 days, 150mm gap on A-102 vs 200mm on S-304",
    "Site issue: +$5000, +2 days, Unidentified buried service in Zone B",
    "Variation: +$2500, +0 days, paint colour Midnight Teal",
    "Site issue: +$0, +1 day, Crane grinding noise, inspection needed",
    "Delay: +$0, +5 days, Structural steel Level 4 delayed, port strike",
    "Delay: +$0, +5 days, Structural steel for Level 4 late due to port strike" # Expected HIT
]

async def run_adversarial_test():
    print("🛡️ STARTING ADVERSARIAL VERIFICATION (V4)")
    print("-" * 50)
    
    # 1. Hard Reset
    db_paths = [
        Path("agents_memory.db"),
        Path("data/agents_memory.db"),
        Path("data/agents_state.db")
    ]
    log_paths = [
        Path("Agent logs/events.log.jsonl")
    ]
    
    for p in db_paths:
        if p.exists():
            print(f"🗑️ Deleting {p}...")
            for _ in range(5):
                try:
                    p.unlink()
                    break
                except PermissionError:
                    await asyncio.sleep(1)
                    
    for p in log_paths:
        if p.exists():
            print(f"🧹 Clearing {p}...")
            p.write_text("")

    # 2. Execute
    results = []
    orc = Orchestrator()

    for i, user_input in enumerate(SCENARIOS):
        print(f"\n[{i+1}/10] INPUT: {user_input}")
        
        # Manually normalize for reporting
        normalized = _normalize_issue(user_input)
        print(f"   NORM:  '{normalized}'")
        
        # Run loop
        outcome = "MISS" 
        proposal_id = None
        
        try:
            async for chunk in orc.astream_chat(user_input):
                if "Decision served from cache" in chunk or "CACHE_HIT" in chunk:
                    outcome = "HIT"
                if "Request ID: APR-" in chunk:
                    proposal_id = chunk.split("Request ID: ")[1].strip()
        except Exception as e:
            print(f"   ERROR in astream_chat: {e}")
            traceback.print_exc()
        
        # Inspect firewall if proposal was created
        decision = "N/A"
        if proposal_id:
            req = firewall.get_request(proposal_id)
            params = req.get("parameters", {})
            decision = params.get("decision", {}).get("decision", "PENDING")
            
        print(f"   RESULT: {outcome} | DECISION: {decision}")
        
        results.append({
            "input": user_input,
            "normalized": normalized,
            "outcome": outcome,
            "decision": decision
        })
        
        # Simulated approval to populate cache for subsequent runs
        if proposal_id and outcome == "MISS":
            firewall.decide_request(proposal_id, "approve")

    print("\n" + "=" * 50)
    print("      ADVERSARIAL VERIFICATION COMPLETE")
    print("=" * 50)
    
    # Summary
    hits = sum(1 for r in results if r["outcome"] == "HIT")
    print(f"\nFinal Hit Rate: {hits/len(SCENARIOS)*100:.2f}% ({hits}/{len(SCENARIOS)})")
    
    # Detailed table
    print("\n| # | Input | Normalized | Result | Decision |")
    print("|---|---|---|---|---|")
    for i, r in enumerate(results):
        inp_trunc = (r["input"][:30] + "..") if len(r["input"]) > 30 else r["input"]
        print(f"| {i+1} | {inp_trunc} | {r['normalized']} | {r['outcome']} | {r['decision']} |")

if __name__ == "__main__":
    asyncio.run(run_adversarial_test())
