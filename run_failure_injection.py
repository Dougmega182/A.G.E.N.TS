import asyncio
import json
from agents.orchestrator import Orchestrator
from agents.logic.task_queue import list_logistics_tasks, resolve_logistics_task, PENDING_LOGISTICS_TASKS
from agents.logic import eli_adapter_v1

async def run_failure_injection():
    print("🏚️ STARTING PHASE 2.5 FAILURE INJECTION")
    print("-" * 60)
    
    orc = Orchestrator()
    
    # Clean state
    tasks = list(PENDING_LOGISTICS_TASKS)
    for t in tasks:
        resolve_logistics_task(t["id"])

    scenarios = [
        {"id": "CONFLICT", "input": "Delay: +$0, +5 days, steel late due to port strike"},
        {"id": "CONFLICT_RES", "input": "Delay: +$0, +0 days, steel arriving today, strike resolved"},
        {"id": "KITCHEN_SINK", "input": "Variation: +$15k, +4 days, Rain delay and workers didn't show and material is late"},
        {"id": "EDGE_CONF", "input": "maybe some tiles are kinda late maybe 3 days idk"},
        {"id": "PANIC", "input": "Everything is f***ed, site is behind bad, urgent review needed!"},
        {"id": "FLOOD_1", "input": "Delay: +$0, +1 day, rain delay"},
        {"id": "FLOOD_2", "input": "Delay: +$0, +1 day, site is too wet to work"},
        {"id": "FLOOD_3", "input": "Delay: +$0, +1 day, raining on site"},
        {"id": "SATURATION", "input": "Variation: +$99m, +1000 days, client building space elevator"},
        {"id": "SUBJECTIVE", "input": "Variation: +$0, +0 days, i think the lobby would look better in neon pink"}
    ]

    print("\n[STEP 1] Running Multi-Scenario Injection...")
    for s in scenarios:
        print(f"  Injecting {s['id']}...")
        try:
            async for chunk in orc.astream_chat(s["input"]):
                if "format violation" in chunk:
                    print(f"    ⚠️ {chunk.strip()}")
        except Exception as e:
            print(f"    ❌ CRASH in {s['id']}: {e}")

    print("\n[STEP 2] Inspecting the Cracks...")
    all_tasks = list_logistics_tasks()
    print(f"Total Intents in Queue: {len(all_tasks)}")
    
    for t in all_tasks:
        has_draft = "YES" if "gmail_draft" in t else "NO"
        email = t['dispatch'].get('email', 'NONE')
        print(f"  Task: {t['id']} | Strategy: {t['strategy']} | Draft: {has_draft} | Recipient: {email}")
        print(f"    Trace: {t['signal_trace']}")

    # --- TEST: Stakeholder Failure ---
    print("\n[STEP 3] Injecting Stakeholder Blackout...")
    original_foreman = eli_adapter_v1._RECIPIENT_MAP["foreman"]
    eli_adapter_v1._RECIPIENT_MAP["foreman"] = None # Delete email
    
    try:
        async for _ in orc.astream_chat("Delay: +$0, +2 days, labour shortage on Zone A"): pass
        last_task = list_logistics_tasks()[-1]
        print(f"  Result: Strategy={last_task['strategy']}, Draft={'gmail_draft' in last_task}")
    except Exception as e:
        print(f"  ❌ CRASH on Stakeholder Failure: {e}")
    finally:
        eli_adapter_v1._RECIPIENT_MAP["foreman"] = original_foreman

if __name__ == "__main__":
    asyncio.run(run_failure_injection())
