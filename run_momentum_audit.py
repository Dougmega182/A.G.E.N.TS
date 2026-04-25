import json
import asyncio
from agents.logic.decision_cache import build_cache_context
from agents.logic.momentum_engine import analyze_momentum
from agents.logic.eli_adapter_v1 import transform_signal_to_actions

SCENARIOS = [
    {"input": "Delay: +$0, +3 days, Rain delay to slab pour", "cost": 0, "days": 3},
    {"input": "Variation: +$12k, +0 days, upgraded acoustic tiles in lobby", "cost": 12000, "days": 0},
    {"input": "RFI: +$0, +0 days, 150mm gap on A-102 vs 200mm on S-304", "cost": 0, "days": 0},
    {"input": "Site issue: +$5000, +2 days, Unidentified buried service in Zone B", "cost": 5000, "days": 2},
    {"input": "Variation: +$2500, +0 days, paint colour Midnight Teal", "cost": 2500, "days": 0},
    {"input": "Site issue: +$0, +1 day, Crane grinding noise, inspection needed", "cost": 0, "days": 1},
    {"input": "Delay: +$0, +5 days, Structural steel Level 4 delayed, port strike", "cost": 0, "days": 5}
]

def run_momentum_audit():
    print("📈 MOMENTUM SIGNAL AUDIT (Handshake Phase)")
    print("-" * 75)
    print("| Input (Truncated) | Abstracted Key | Velocity | Trend | Conf | Draft? |")
    print("|---|---|---|---|---|---|")
    
    for s in SCENARIOS:
        # Build context (simulates Layer 2.6 output)
        ctx = build_cache_context(
            scenario_type="variation", # Placeholder
            user_input=s["input"],
            cost=s["cost"],
            days=s["days"],
            governance_flags=[]
        )
        
        # 1. Analyze momentum (The Handshake)
        signal = analyze_momentum(ctx)
        
        # 2. Eli Adapter (Deterministic Execution)
        actions = transform_signal_to_actions(signal)
        
        inp_trunc = (s["input"][:18] + "..") if len(s["input"]) > 18 else s["input"]
        key_trunc = (ctx.normalized_issue[:18] + "..") if len(ctx.normalized_issue) > 18 else ctx.normalized_issue
        has_draft = "YES" if "gmail_draft" in actions else "NO"
        
        print(f"| {inp_trunc} | {key_trunc} | {signal['velocity_impact']} | {signal['trend_direction']} | {signal['confidence']} | {has_draft} |")
        
        if "gmail_draft" in actions:
            print(f"   DRAFT SUBJECT: {actions['gmail_draft']['subject']}")

if __name__ == "__main__":
    run_momentum_audit()
