import asyncio
import json
from agents.orchestrator import Orchestrator
from agents.logic.task_queue import list_logistics_tasks, resolve_logistics_task, PENDING_LOGISTICS_TASKS

async def test_multi_draft_generation():
    print("🧪 TESTING PHASE 2.8: MULTI-DRAFT GENERATION")
    print("-" * 60)
    
    # Reset queue
    global PENDING_LOGISTICS_TASKS
    PENDING_LOGISTICS_TASKS.clear()
    
    orc = Orchestrator()
    # Scenario: Critical Steel Delay (Impact -0.80+)
    input_text = "Delay: +$0, +21 days, major steel supplier bankrupt, delivery stalled indefinitely"
    
    print(f"1. Lodging CRITICAL work: {input_text}")
    async for _ in orc.astream_chat(input_text): pass
            
    # Check latest task
    tasks = list_logistics_tasks()
    if not tasks:
        print("❌ FAILED: No task generated.")
        return

    task = tasks[0]
    print(f"\n2. Task ID: {task['id']} | Strategy: {task['strategy']} | Severity: {task['momentum_signal']['severity']}")
    
    # Verify Draft Count
    drafts = task.get("drafts", {})
    print(f"   Drafts generated: {list(drafts.keys())}")
    
    if "primary" in drafts and "secondary" in drafts:
        print("\n✅ SUCCESS: Distinct Primary and Secondary drafts generated.")
        print(f"\nPRIMARY SUBJECT (Foreman): {drafts['primary']['subject']}")
        print(f"PRIMARY BODY SNIPPET: {drafts['primary']['body'][:80]}...")
        
        print(f"\nSECONDARY SUBJECT (PM): {drafts['secondary']['subject']}")
        print(f"SECONDARY BODY SNIPPET: {drafts['secondary']['body'][:80]}...")
        
        # Verify action-oriented vs awareness-oriented keywords
        assert "REQUIRED ACTION" in drafts["primary"]["body"]
        assert "No direct action required" in drafts["secondary"]["body"]
        print("\n✅ CONTENT ROLE VERIFIED: Action Required vs Awareness Only.")
    else:
        print(f"❌ FAILED: Drafts missing. Primary: {'YES' if 'primary' in drafts else 'NO'}, Secondary: {'YES' if 'secondary' in drafts else 'NO'}")

if __name__ == "__main__":
    asyncio.run(test_multi_draft_generation())
