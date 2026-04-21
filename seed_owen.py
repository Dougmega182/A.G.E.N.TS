
import os
import sys
from pathlib import Path

# Add root to path
sys.path.append(str(Path(__file__).parent))

from agents.logic import memory_db
from agents.logic.owen_engine import OwenEngine

def seed():
    print("Seeding Owen Intelligence with historical weather lessons...")
    
    # Lesson 1: Rain delays compound
    summary = "Past delays compound when weather ignored. Rain-affected concrete pours require immediate catch-up schedules to avoid subcontractor backlog."
    scenario = "site_issue"
    
    # Use OwenEngine's internal write logic
    owen = OwenEngine()
    det_key = owen._generate_deterministic_key(summary, scenario)
    
    insight_id = memory_db.write_owen_insight(
        "owen_engine",
        insight_type="lesson_learned",
        summary=summary,
        scenario_type=scenario,
        evidence=["historical_manual_seed"],
        confidence=0.95,
        deterministic_key=det_key
    )
    
    print(f"Success! Seeded Owen Insight ID: {insight_id}")

if __name__ == "__main__":
    seed()
