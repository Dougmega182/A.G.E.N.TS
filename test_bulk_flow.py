import asyncio
import json
from agents.orchestrator import Orchestrator
from agents.logic.task_queue import list_logistics_tasks, PENDING_LOGISTICS_TASKS

async def test_bulk_authorization_flow():
    print("🧪 TESTING PHASE 3.1: BULK AUTHORIZATION FLOW")
    print("-" * 60)
    
    # Reset queue
    global PENDING_LOGISTICS_TASKS
    PENDING_LOGISTICS_TASKS.clear()
    
    orc = Orchestrator()
    
    # Burst of 3 similar weather signals (should cluster into WEATHER_BLOCK)
    inputs = [
        "Delay: +$0, +1 day, rain delay on site",
        "Delay: +$0, +1 day, too wet to work today",
        "Delay: +$0, +1 day, ground is muddy after storm"
    ]
    
    print(f"1. Injecting burst of {len(inputs)} weather signals...")
    for inp in inputs:
        async for _ in orc.astream_chat(inp): pass
            
    # Check queue clustering
    tasks = list_logistics_tasks()
    print(f"\n2. Total ACTIVE Tasks in Queue: {len(tasks)}")
    
    concepts = [t.get("concept") for t in tasks]
    print(f"   Concepts in Queue: {concepts}")
    
    weather_tasks = [t for t in tasks if t.get("concept") == "WEATHER_BLOCK"]
    print(f"   Weather Tasks clustered: {len(weather_tasks)}")
    
    if len(weather_tasks) == 3:
        print("\n✅ SUCCESS: Concepts correctly clustered for bulk action.")
        
        # Verify safety data for UI logic
        first_recips = json.dumps(weather_tasks[0]["dispatch_plan"]["recipients"])
        all_same_recips = all(json.dumps(t["dispatch_plan"]["recipients"]) == first_recips for t in weather_tasks)
        print(f"   Safety Check: All same recipients? {all_same_recips}")
        
        if all_same_recips:
            print("✅ SAFETY VERIFIED: UI will permit 'Approve All' for this group.")
        else:
            print("❌ SAFETY FAILED: Recipients differ within concept cluster.")
    else:
        print(f"❌ CLUSTERING FAILED: Expected 3 WEATHER_BLOCK items, got {len(weather_tasks)}.")

if __name__ == "__main__":
    asyncio.run(test_bulk_authorization_flow())
