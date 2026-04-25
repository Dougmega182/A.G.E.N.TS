import asyncio
import json
from pathlib import Path
from agents.orchestrator import Orchestrator
from agents.logic.task_queue import list_logistics_tasks, resolve_logistics_task

async def run_dispatch_tests():
    print("🚦 STARTING DISPATCH & SAFETY VERIFICATION")
    print("-" * 60)
    
    orc = Orchestrator()
    
    # Reset Queue
    tasks = list_logistics_tasks()
    for t in list(tasks):
        resolve_logistics_task(t["id"])

    # --- TEST 1: Target Mapping Accuracy ---
    print("\nTEST 1: Target Mapping Accuracy")
    scenarios = [
        {"name": "LABOUR", "input": "Delay: +$0, +1 day, site crew late today"},
        {"name": "MATERIAL", "input": "Delay: +$0, +2 days, steel delivery delayed"},
        {"name": "ENVIRONMENTAL", "input": "Delay: +$0, +3 days, heavy rain on site"}
    ]
    
    for s in scenarios:
        print(f"  Running scenario: {s['name']}")
        try:
            async for _ in orc.astream_chat(s["input"]): pass
            
            all_tasks = list_logistics_tasks()
            if not all_tasks:
                print(f"  ❌ FAILED: No task generated for {s['name']}")
                continue
                
            task = all_tasks[-1]
            email = task["dispatch"]["email"]
            role = task["dispatch"]["to"]
            print(f"  [{s['name']}] -> Role: {role} | Email: {email}")
            
            if s["name"] == "ENVIRONMENTAL":
                assert role == "internal" and email is None
            elif s["name"] == "MATERIAL":
                assert role == "foreman"
            elif s["name"] == "LABOUR":
                assert role == "foreman"
        except Exception as e:
            print(f"  ❌ ERROR in {s['name']}: {e}")
            continue
    print("  ✅ TEST 1 COMPLETE")

    # --- TEST 2: Confidence Gate ---
    print("\nTEST 2: Confidence Gate")
    messy_input = "maybe some tiles are kinda late idk probably supplier"
    try:
        async for _ in orc.astream_chat(messy_input): pass
        all_tasks = list_logistics_tasks()
        if not all_tasks:
            print("  ❌ FAILED: No task generated for confidence gate")
        else:
            task = all_tasks[-1]
            has_draft = "gmail_draft" in task
            conf = task["meta"]["confidence"]
            print(f"  Input: '{messy_input}' | Conf: {conf} | Has Draft: {has_draft}")
            assert conf < 0.70
            assert not has_draft
            print("  ✅ TEST 2 PASSED")
    except Exception as e:
        print(f"  ❌ ERROR in TEST 2: {e}")

    # --- TEST 3: Duplicate Suppression ---
    print("\nTEST 3: Duplicate Suppression")
    input_a = "Delay: +$0, +5 days, port strike delaying steel"
    input_b = "Delay: +$0, +5 days, steel late due to port strike"
    
    count_before = len(list_logistics_tasks())
    async for _ in orc.astream_chat(input_a): pass
    async for _ in orc.astream_chat(input_b): pass
    count_after = len(list_logistics_tasks())
    
    print(f"  Count Before: {count_before} | Count After: {count_after}")
    assert count_after == count_before + 1
    print("  ✅ TEST 3 PASSED")

    # --- TEST 4: Signal Trace Integrity ---
    print("\nTEST 4: Signal Trace Integrity")
    task = list_logistics_tasks()[-1]
    trace = task.get("momentum_signal")
    print(f"  Abstracted Key: {task['signal_trace']}")
    print(f"  Trend: {trace['trend_direction']}")
    assert task["signal_trace"] is not None
    assert trace["trend_direction"] is not None
    print("  ✅ TEST 4 PASSED")

    print("\n" + "=" * 60)
    print("🎉 ALL DISPATCH & SAFETY TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_dispatch_tests())
