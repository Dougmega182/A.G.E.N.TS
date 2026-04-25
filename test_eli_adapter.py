import json
from agents.logic.decision_cache import build_cache_context
from agents.logic.momentum_engine import analyze_momentum
from agents.logic.eli_adapter_v1 import transform_signal_to_actions

def run_eli_handshake_test():
    print("🤖 ELI ADAPTER HANDSHAKE TEST")
    print("-" * 60)
    
    # Input: Abstracted issue from Layer 2.6
    input_text = "Delay: +$0, +5 days, Structural steel for Level 4 late due to port strike"
    
    # 1. Normalization & Context (Layer 2.6)
    ctx = build_cache_context(
        scenario_type="delay",
        user_input=input_text,
        cost=0,
        days=5,
        governance_flags=[]
    )
    print(f"1. NORMALIZED KEY: {ctx.normalized_issue}")
    
    # 2. Momentum Signal (Handshake)
    signal = analyze_momentum(ctx)
    print(f"2. MOMENTUM SIGNAL: {signal['trend_direction']} (Impact: {signal['velocity_impact']})")
    
    # 3. Eli Adapter (Deterministic Execution)
    actions = transform_signal_to_actions(signal)
    print(f"3. ACTION QUEUE OBJECT:")
    print(json.dumps(actions, indent=2))
    
    # Final assertion check
    assert actions["strategy"] == "STABILISE"
    assert actions["dispatch"]["to"] == "foreman"
    print("\n✅ HANDSHAKE VERIFIED: Deterministic execution locked.")

if __name__ == "__main__":
    run_eli_handshake_test()
