"""
Task Queue — Shared state for Phase 2.3 Logistics Intents.
Used to avoid circular imports between API and Orchestrator.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any

# Shared state
PENDING_LOGISTICS_TASKS: List[Dict[str, Any]] = []

# Phase 2.6: Concept Normalization (Clustering)
_CONCEPT_MAP = {
    "rain": "WEATHER_BLOCK",
    "wet": "WEATHER_BLOCK",
    "storm": "WEATHER_BLOCK",
    "weather": "WEATHER_BLOCK",
    "steel": "MATERIAL_FLOW",
    "concrete": "MATERIAL_FLOW",
    "crew": "LABOUR_FLOW",
    "labour": "LABOUR_FLOW",
}

def _get_concept(issue_key: str) -> str:
    """Map abstracted tokens to higher-level operational concepts."""
    tokens = set(issue_key.split())
    for token, concept in _CONCEPT_MAP.items():
        if token in tokens:
            return concept
    return "GENERAL_ISSUE"

def enqueue_logistics_task(task: Dict[str, Any]):
    """
    Adds a new logistics intent to the pending queue. 
    Enforces Phase 2.6 Conflict Resolver (Entity + Polarity + Recency).
    """
    global PENDING_LOGISTICS_TASKS
    
    entity = task.get("entity", "general")
    domain = task["dispatch"].get("domain", "LOGISTICS")
    polarity = task.get("polarity", "NEUTRAL")
    concept = _get_concept(task.get("signal_trace", ""))
    
    task["concept"] = concept

    # 1. Conflict Resolver (Entity + Domain match)
    # Rule: Fresh update overrides older conflicting or duplicate intent.
    existing_conflict = next(
        (t for t in PENDING_LOGISTICS_TASKS 
         if t.get("entity") == entity and t["dispatch"].get("domain") == domain), 
        None
    )

    if existing_conflict:
        # Check for polarity opposition (e.g. DELAY vs RESOLVED)
        if existing_conflict.get("polarity") != polarity:
            task["status"] = "CONFLICT_RESOLVED_NEWER"
            logger.info(f"Conflict detected for {entity}. Newer {polarity} signal overrides {existing_conflict.get('polarity')}.")
        
        # Recency Override: Remove the old stale intent
        resolve_logistics_task(existing_conflict["id"])

    task_id = f"TSK-{uuid.uuid4().hex[:8].upper()}"
    task["id"] = task_id
    
    # Standardize status if not already set by resolver
    if "status" not in task:
        task["status"] = "READY"
        
    task["created_at"] = datetime.utcnow().isoformat()
    PENDING_LOGISTICS_TASKS.append(task)
    return task_id

def list_logistics_tasks():
    """Returns all pending tasks."""
    return PENDING_LOGISTICS_TASKS

def get_logistics_task(task_id: str):
    """Retrieves a specific task."""
    return next((t for t in PENDING_LOGISTICS_TASKS if t["id"] == task_id), None)

def resolve_logistics_task(task_id: str):
    """Removes a task from the pending queue after decision."""
    global PENDING_LOGISTICS_TASKS
    PENDING_LOGISTICS_TASKS = [t for t in PENDING_LOGISTICS_TASKS if t["id"] != task_id]
