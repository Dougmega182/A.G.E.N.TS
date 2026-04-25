"""
Task Queue — Shared state for Phase 2.3 Logistics Intents.
Used to avoid circular imports between API and Orchestrator.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger("agents.task_queue")

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
    Enforces Phase 2.6 Conflict Resolver and Recency Rule.
    """
    global PENDING_LOGISTICS_TASKS
    
    entity = task.get("entity", "general")
    domain = task["dispatch"].get("domain", "LOGISTICS")
    polarity = task.get("polarity", "NEUTRAL")
    concept = _get_concept(task.get("signal_trace", ""))
    
    task["concept"] = concept
    task["lifecycle"] = "ACTIVE"

    # 1. Conflict Resolver (Entity + Domain match)
    # Rule: Fresh update supersedes older conflicting or duplicate active intents.
    existing_active = [
        t for t in PENDING_LOGISTICS_TASKS 
        if t.get("entity") == entity 
        and t["dispatch"].get("domain") == domain
        and t.get("lifecycle") == "ACTIVE"
    ]

    for existing in existing_active:
        # Check for polarity opposition
        if existing.get("polarity") != polarity:
            task["status"] = "CONFLICT_RESOLVED_NEWER"
            logger.info(f"Conflict detected for {entity}. Newer {polarity} signal supersedes {existing.get('polarity')}.")
        
        # Recency Rule: Mark the old intent as SUPERSEDED
        existing["lifecycle"] = "SUPERSEDED"

    task_id = f"TSK-{uuid.uuid4().hex[:8].upper()}"
    task["id"] = task_id
    
    # Standardize status if not already set by resolver
    if "status" not in task:
        task["status"] = "READY"
        
    task["created_at"] = datetime.utcnow().isoformat()
    PENDING_LOGISTICS_TASKS.append(task)
    return task_id

def list_logistics_tasks():
    """Returns pending tasks sorted by Impact Score (DESC) then Recency (DESC)."""
    # Filter for only ACTIVE or pending tasks for the primary display
    active_tasks = [t for t in PENDING_LOGISTICS_TASKS if t.get("lifecycle") in {None, "ACTIVE", "pending"}]
    
    return sorted(
        active_tasks,
        key=lambda x: (
            x.get("momentum_signal", {}).get("impact_score", 0), 
            x.get("created_at", "")
        ),
        reverse=True
    )

def get_logistics_task(task_id: str):
    """Retrieves a specific task."""
    return next((t for t in PENDING_LOGISTICS_TASKS if t["id"] == task_id), None)

def resolve_logistics_task(task_id: str, lifecycle_state: str = "RESOLVED"):
    """Update a task's lifecycle state and remove it from memory if needed."""
    global PENDING_LOGISTICS_TASKS
    task = get_logistics_task(task_id)
    if task:
        task["lifecycle"] = lifecycle_state
        task["resolved_at"] = datetime.utcnow().isoformat()
    
    # For Phase 2.3 parity, we actually remove from active list if it's no longer pending
    # but we'll keep the record in memory for now. 
    # To keep list_logistics_tasks clean, we use the filter above.
