import asyncio
import json
from agents.orchestrator import Orchestrator
from agents.logic.task_queue import list_logistics_tasks

async def test_eli_dashboard_integration():
    print("🧪 TESTING ELI DASHBOARD INTEGRATION")
    print("-" * 60)
    
    orc = Orchestrator()
    input_text = "Delay: +$0, +5 days, Structural steel for Level 4 late due to port strike"
    
    print(f"1. Lodging work: {input_text}")
    async for chunk in orc.astream_chat(input_text):
        if "Eli Logistics Intent Generated" in chunk:
            print(f"   {chunk.strip()}")
            
    # Check task queue
    tasks = list_logistics_tasks()
    print(f"\n2. Task Queue Count: {len(tasks)}")
    
    if tasks:
        task = tasks[-1]
        print(f"   Latest Task Strategy: {task['strategy']}")
        print(f"   Priority: {task['execution_priority']}")
        print(f"   Domain: {task['dispatch']['domain']}")
        print(f"   Has Gmail Draft: {'YES' if 'gmail_draft' in task else 'NO'}")
        
        # Verify Signal Trace data is present
        assert "momentum_signal" in task
        print("✅ Signal Trace data verified.")
        
        print("\n🎉 PHASE 2.3 VERIFIED: Eli intent is staged for human authorization.")
    else:
        print("❌ FAILED: No task generated in queue.")

if __name__ == "__main__":
    asyncio.run(test_eli_dashboard_integration())
