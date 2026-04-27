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

def _get_concept(issue_key: str) -> str:
    """Map abstracted tokens to higher-level operational concepts."""
    tokens = set(issue_key.split())
    # Concepts now have suffixes (e.g. WEATHER_BLOCK_rain)
    known_prefixes = ["WEATHER_BLOCK", "MATERIAL_FLOW", "LABOUR_FLOW", "RFI_CLASH", "BURIED_SERVICE", "EQUIPMENT_FAULT"]
    
    for token in tokens:
        for prefix in known_prefixes:
            if token.startswith(prefix):
                return prefix
    return "GENERAL_ISSUE"

def list_logistics_tasks():
    """Returns pending tasks sorted by Impact Score (DESC) then Recency (DESC)."""
    # Return all tasks for auditing, but the UI should filter ACTIVE if it wants.
    # For now, let's return ACTIVE tasks only for the primary operator flow.
    active_tasks = [t for t in PENDING_LOGISTICS_TASKS if t.get("lifecycle") == "ACTIVE"]
    
    return sorted(
        active_tasks,
        key=lambda x: (
            x.get("momentum_signal", {}).get("impact_score", 0), 
            x.get("created_at", "")
        ),
        reverse=True
    )

def enqueue_logistics_task(task: Dict[str, Any]):
    """
    Adds a new logistics intent to the pending queue. 
    Enforces Phase 2.6 Conflict Resolver and Recency Rule.
    """
    global PENDING_LOGISTICS_TASKS
    
    entity = task.get("entity", "GENERAL_SITE")
    domain = task["dispatch"].get("domain", "LOGISTICS")
    role = task["dispatch"].get("to", "unknown")
    polarity = task.get("polarity", "NEUTRAL")
    concept = _get_concept(task.get("signal_trace", ""))
    
    task["concept"] = concept
    task["lifecycle"] = "ACTIVE"

    # 1. Conflict Resolver (Entity + Role match)
    # Rule: Fresh update supersedes older conflicting intents for the same role/entity.
    # CRITICAL: For concepts like WEATHER_BLOCK, we allow coexistence UNLESS:
    #   - The signal_trace is an exact duplicate
    #   - The polarity is a direct conflict (DELAY vs RESOLVED)
    existing_active = [
        t for t in PENDING_LOGISTICS_TASKS 
        if t.get("entity") == entity 
        and t["dispatch"].get("to") == role
        and t.get("lifecycle") == "ACTIVE"
    ]

    for existing in existing_active:
        # Check if the signal trace is effectively the same (duplicate)
        is_exact_duplicate = existing.get("signal_trace") == task.get("signal_trace")
        
        # Phase 3.1: Only trigger conflict if polarities are directly OPPOSITE (DELAY vs RESOLVED)
        e_pol = existing.get("polarity", "NEUTRAL")
        is_polarity_conflict = (
            (e_pol == "DELAY" and polarity == "RESOLVED") or 
            (e_pol == "RESOLVED" and polarity == "DELAY")
        )
        
        if is_exact_duplicate or is_polarity_conflict:
            if is_polarity_conflict:
                task["status"] = "CONFLICT_RESOLVED_NEWER"
            existing["lifecycle"] = "SUPERSEDED"

    task_id = f"TSK-{uuid.uuid4().hex[:8].upper()}"
    task["id"] = task_id
    
    if "status" not in task:
        task["status"] = "READY"
        
    task["created_at"] = datetime.utcnow().isoformat()
    PENDING_LOGISTICS_TASKS.append(task)
    return task_id

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
